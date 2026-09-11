"""Admin data-management routes (PRD sections 5 and 6.6).

Every route here verifies the caller's role server-side, in this process,
against a hashed token. Route protection in the frontend is a convenience for
the person clicking; it is not a security boundary, and nothing in this module
assumes the request came through it.

Scope is deliberately narrow: catalogue maintenance, plus a read-only audit view.
There is no beneficiary-facing surface here and no route that returns a
transcript.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.config import get_settings
from app.models import schemas
from app.services import db, schemes, pipeline, taxonomy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

ROLE_RANK = {"viewer": 0, "editor": 1, "owner": 2}


class AdminIdentity(BaseModel):
    email: str
    role: str


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def require_admin(
    authorization: Annotated[str | None, Header()] = None,
) -> AdminIdentity:
    """Resolve the caller to an admin identity, or say why not.

    Order matters: the database is the source of truth, and the bootstrap
    token is honoured only when no admin rows exist. Otherwise a leaked
    bootstrap value would stay a permanent backdoor after real admins are
    provisioned.

    Three ways this ends, and the third is the one worth separating:

    * **401** -- no bearer token was sent. The caller's own omission.
    * **403** -- a token was sent and is not accepted. Identical whether real
      admins are provisioned or only a bootstrap token is configured, because
      telling those apart would leak how the deployment is set up.
    * **503** -- no admin users exist *and* no bootstrap token is set. The
      server cannot accept any token from anyone. This used to answer 403 as
      well, which reads as "you got it wrong" and sends an operator hunting
      for a typo in a value that was never going to work.
    """
    settings = get_settings()

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin token required."
        )

    digest = _hash_token(token)

    if db.is_available():
        row = await db.fetchrow(
            "select email, role from admin_users "
            "where token_hash = $1 and is_active",
            digest,
        )
        if row is not None:
            return AdminIdentity(email=row["email"], role=row["role"])

        any_admin = await db.fetchval(
            "select exists (select 1 from admin_users where is_active)"
        )
        if any_admin:
            # Real admins exist and this was not one of them.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised."
            )

    if settings.admin_bootstrap_token:
        # compare_digest, so a wrong token cannot be narrowed down by timing.
        if hmac.compare_digest(
            _hash_token(settings.admin_bootstrap_token), digest
        ):
            return AdminIdentity(email="bootstrap@local", role="owner")

        # A bootstrap token exists and this was not it. The same answer a
        # provisioned deployment gives a wrong token, deliberately: which of
        # the two a server is running is not a fact an unauthenticated caller
        # may probe for.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised."
        )

    # Nothing can authorise anyone: no active admin row matched, none exists,
    # and no bootstrap token is set. That is a configuration fault, not a
    # refusal -- no value the caller types will ever be accepted, and
    # answering 403 invites them to keep trying. 503 matches how
    # _require_database already reports "admin needs something this deployment
    # has not been given".
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "Admin access is not configured on this server. No admin users "
            "exist and ADMIN_BOOTSTRAP_TOKEN is not set, so no token can be "
            "accepted. Set it in the backend environment, or add a row to "
            "admin_users."
        ),
    )


def require_role(minimum: str):
    async def dependency(
        identity: Annotated[AdminIdentity, Depends(require_admin)],
    ) -> AdminIdentity:
        if ROLE_RANK.get(identity.role, -1) < ROLE_RANK[minimum]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action needs the {minimum} role.",
            )
        return identity

    return dependency


def _require_database() -> None:
    if not db.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin writes need a database. Set DATABASE_URL.",
        )


# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------


class SchemeWrite(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    organization: str = Field(min_length=1, max_length=300)
    location: str = Field(min_length=1, max_length=200)
    district: str | None = None
    type: str
    minimum_experience: float = 0
    certifications_required: list[str] = Field(default_factory=list)
    salary_min: int | None = None
    salary_max: int | None = None
    nsqf_level: str | None = None
    source_reference: str | None = None
    # The government's own page for this scheme. Pattern-checked here as
    # well as in the database: rejected at the edge it names the field,
    # where a constraint violation would surface as a 500.
    official_url: str | None = Field(default=None, pattern=r"^https?://\S+$")
    description: str | None = None
    is_active: bool = True
    skill_ids: list[int] = Field(default_factory=list)


class TaxonomyWrite(BaseModel):
    code: str = Field(pattern=r"^SK\d{3,}$")
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    hint: str | None = None
    aliases: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Schemes
# ---------------------------------------------------------------------------


@router.get("/schemes", response_model=list[schemas.SchemeDetail])
async def list_schemes(
    _: Annotated[AdminIdentity, Depends(require_role("viewer"))],
) -> list[schemas.SchemeDetail]:
    catalogue = await schemes.list_active()
    return [pipeline.scheme_to_detail(o) for o in catalogue]


@router.post("/schemes", response_model=schemas.SchemeDetail, status_code=201)
async def create_scheme(
    payload: SchemeWrite,
    _: Annotated[AdminIdentity, Depends(require_role("editor"))],
) -> schemas.SchemeDetail:
    _require_database()
    async with db.transaction() as conn:
        row = await conn.fetchrow(
            "insert into schemes "
            "(title, organization, location, district, type, minimum_experience, "
            " certifications_required, salary_min, salary_max, nsqf_level, "
            " source_reference, official_url, description, is_active) "
            "values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14) returning id",
            payload.title, payload.organization, payload.location, payload.district,
            payload.type, payload.minimum_experience, payload.certifications_required,
            payload.salary_min, payload.salary_max, payload.nsqf_level,
            payload.source_reference, payload.official_url, payload.description,
            payload.is_active,
        )
        for skill_id in payload.skill_ids:
            await conn.execute(
                "insert into scheme_skills (scheme_id, skill_id) "
                "values ($1, $2) on conflict do nothing",
                row["id"], skill_id,
            )
    schemes.reset_memory_cache()
    created = await schemes.get(row["id"])
    assert created is not None
    return pipeline.scheme_to_detail(created)


@router.put("/schemes/{scheme_id}", response_model=schemas.SchemeDetail)
async def update_scheme(
    scheme_id: int,
    payload: SchemeWrite,
    _: Annotated[AdminIdentity, Depends(require_role("editor"))],
) -> schemas.SchemeDetail:
    _require_database()
    async with db.transaction() as conn:
        updated = await conn.fetchrow(
            "update schemes set title=$2, organization=$3, location=$4, "
            "district=$5, type=$6, minimum_experience=$7, certifications_required=$8, "
            "salary_min=$9, salary_max=$10, nsqf_level=$11, source_reference=$12, "
            "official_url=$13, description=$14, is_active=$15 "
            "where id=$1 returning id",
            scheme_id, payload.title, payload.organization, payload.location,
            payload.district, payload.type, payload.minimum_experience,
            payload.certifications_required, payload.salary_min, payload.salary_max,
            payload.nsqf_level, payload.source_reference, payload.official_url,
            payload.description, payload.is_active,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Not found.")
        await conn.execute(
            "delete from scheme_skills where scheme_id = $1", scheme_id
        )
        for skill_id in payload.skill_ids:
            await conn.execute(
                "insert into scheme_skills (scheme_id, skill_id) "
                "values ($1, $2) on conflict do nothing",
                scheme_id, skill_id,
            )
    schemes.reset_memory_cache()
    result = await schemes.get(scheme_id)
    assert result is not None
    return pipeline.scheme_to_detail(result)


@router.delete(
    "/schemes/{scheme_id}", status_code=204, response_model=None
)
async def deactivate_scheme(
    scheme_id: int,
    _: Annotated[AdminIdentity, Depends(require_role("editor"))],
) -> None:
    """Deactivate rather than delete.

    Matches reference schemes, and hard-deleting one would take the audit
    trail with it.
    """
    _require_database()
    result = await db.execute(
        "update schemes set is_active = false where id = $1", scheme_id
    )
    if result.endswith("0"):
        raise HTTPException(status_code=404, detail="Not found.")
    schemes.reset_memory_cache()


# ---------------------------------------------------------------------------
# Sources (PRD section 18)
#
# The review workflow. A page fetched from a domain we do not already trust is
# stored but not answerable, and stays that way until someone here says
# otherwise. The point is that searching the web cannot silently widen what the
# system will assert to a beneficiary.
# ---------------------------------------------------------------------------


@router.get("/sources")
async def list_sources(
    _: Annotated[AdminIdentity, Depends(require_admin)],
    status_filter: str | None = Query(default=None, alias="status"),
) -> list[dict]:
    _require_database()
    rows = await db.fetch(
        """
        select d.id, d.title, d.source, d.source_url, d.source_domain,
               d.trust_tier, d.status, d.retrieved_at, d.last_verified,
               count(c.id) as chunks
        from scheme_documents d
        left join document_chunks c on c.document_id = d.id
        where ($1::text is null or d.status = $1)
        group by d.id
        order by d.retrieved_at desc nulls last, d.id desc
        """,
        status_filter,
    )
    return [dict(row) for row in rows]


@router.post("/sources/{document_id}/verify")
async def verify_source(
    document_id: int,
    _: Annotated[AdminIdentity, Depends(require_role("editor"))],
) -> dict:
    """Make a source answerable, and record who decided that and when."""
    _require_database()
    row = await db.fetchrow(
        "update scheme_documents set status = 'active', last_verified = now() "
        "where id = $1 returning id, source, status",
        document_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Not found.")
    return dict(row)


@router.post("/sources/{document_id}/reject")
async def reject_source(
    document_id: int,
    _: Annotated[AdminIdentity, Depends(require_role("editor"))],
) -> dict:
    """Refuse a source. Re-fetching the page will not undo this."""
    _require_database()
    row = await db.fetchrow(
        "update scheme_documents set status = 'rejected', last_verified = now() "
        "where id = $1 returning id, source, status",
        document_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Not found.")
    return dict(row)


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------


@router.get("/taxonomy", response_model=list[schemas.SkillCandidate])
async def list_taxonomy(
    _: Annotated[AdminIdentity, Depends(require_role("viewer"))],
) -> list[schemas.SkillCandidate]:
    skills = await taxonomy.list_all()
    return [
        schemas.SkillCandidate(
            id=s.id, code=s.code, name=s.name, category=s.category,
            hint=s.hint, similarity=1.0,
            display_names=dict(s.display_names or {}),
        )
        for s in skills
    ]


@router.post("/taxonomy", response_model=schemas.SkillCandidate, status_code=201)
async def upsert_taxonomy(
    payload: TaxonomyWrite,
    _: Annotated[AdminIdentity, Depends(require_role("editor"))],
) -> schemas.SkillCandidate:
    """Add or update a taxonomy entry.

    The embedding is left null: writing it here would mean loading the model
    into the request path. Run ``python -m app.scripts.embed_taxonomy`` after a
    batch of edits -- until then the new entry is invisible to normalization,
    which is the safe failure (it cannot be matched incorrectly).
    """
    _require_database()
    row = await db.fetchrow(
        "insert into skill_taxonomy (code, name, category, hint, aliases) "
        "values ($1,$2,$3,$4,$5) "
        "on conflict (code) do update set name=excluded.name, "
        "category=excluded.category, hint=excluded.hint, aliases=excluded.aliases "
        "returning id, code, name, category, hint",
        payload.code, payload.name, payload.category, payload.hint, payload.aliases,
    )
    taxonomy.reset_memory_cache()
    schemes.reset_memory_cache()
    return schemas.SkillCandidate(
        id=row["id"], code=row["code"], name=row["name"],
        category=row["category"], hint=row["hint"], similarity=1.0,
    )


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


@router.get("/sessions")
async def audit_sessions(
    _: Annotated[AdminIdentity, Depends(require_role("viewer"))],
    limit: int = Query(default=50, le=200),
) -> list[dict[str, Any]]:
    """Read-only QA view over matches and questions.

    Deliberately does not return transcripts. QA needs to see whether the
    matching engine and the explanation layer are behaving; it does not need to
    read what people said about their lives.
    """
    _require_database()
    rows = await db.fetch(
        "select s.id, s.created_at, s.language_detected, s.audio_retained, "
        "  count(distinct m.id) as match_count, "
        "  count(distinct q.id) as question_count, "
        "  max(m.overall_score) as best_score "
        "from sessions s "
        "left join matches m on m.session_id = s.id "
        "left join assistant_queries q on q.session_id = s.id "
        "group by s.id order by s.created_at desc limit $1",
        limit,
    )
    return [
        {
            "id": str(r["id"]),
            "created_at": r["created_at"].isoformat(),
            "language_detected": r["language_detected"],
            "audio_retained": r["audio_retained"],
            "match_count": r["match_count"],
            "question_count": r["question_count"],
            "best_score": float(r["best_score"]) if r["best_score"] is not None else None,
        }
        for r in rows
    ]


@router.get("/whoami", response_model=AdminIdentity)
async def whoami(
    identity: Annotated[AdminIdentity, Depends(require_admin)],
) -> AdminIdentity:
    return identity

"""Opportunity catalogue access.

Postgres when configured, the in-process catalogue otherwise. The required-skill
sets are fetched for the whole active catalogue in one query
(``opportunity_skill_vectors``) rather than per opportunity -- matching needs
all of them, and the per-row version is the N+1 that would dominate the
request.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from app.data.catalogue import OPPORTUNITIES
from app.services import db, taxonomy

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RequiredSkill:
    skill_id: int
    code: str
    name: str
    weight: float
    is_essential: bool
    embedding: list[float] | None = None


@dataclass
class Opportunity:
    id: int
    title: str
    organization: str
    location: str
    district: str | None
    type: str
    minimum_experience: float
    certifications_required: list[str]
    salary_min: int | None
    salary_max: int | None
    nsqf_level: str | None
    source_reference: str | None
    description: str | None
    required_skills: list[RequiredSkill] = field(default_factory=list)


_memory_cache: list[Opportunity] | None = None
_memory_lock = asyncio.Lock()


def reset_memory_cache() -> None:
    global _memory_cache
    _memory_cache = None


async def _memory_opportunities() -> list[Opportunity]:
    global _memory_cache
    if _memory_cache is not None:
        return _memory_cache
    async with _memory_lock:
        if _memory_cache is not None:
            return _memory_cache

        skills = await taxonomy.list_all()
        by_code = {s.code: s for s in skills}
        vectors = await taxonomy.embedding_for_skill_ids([s.id for s in skills])

        built: list[Opportunity] = []
        for index, entry in enumerate(OPPORTUNITIES):
            required = []
            for code, weight, essential in entry["skills"]:
                skill = by_code.get(code)
                if skill is None:
                    logger.warning("Catalogue references unknown skill code %s", code)
                    continue
                required.append(
                    RequiredSkill(
                        skill_id=skill.id,
                        code=skill.code,
                        name=skill.name,
                        weight=float(weight),
                        is_essential=bool(essential),
                        embedding=vectors.get(skill.id),
                    )
                )
            built.append(
                Opportunity(
                    id=index + 1,
                    title=entry["title"],
                    organization=entry["organization"],
                    location=entry["location"],
                    district=entry["district"],
                    type=entry["type"],
                    minimum_experience=float(entry["minimum_experience"]),
                    certifications_required=list(entry["certifications_required"]),
                    salary_min=entry["salary_min"],
                    salary_max=entry["salary_max"],
                    nsqf_level=entry["nsqf_level"],
                    source_reference=entry["source_reference"],
                    description=entry["description"],
                    required_skills=required,
                )
            )
        _memory_cache = built
        return _memory_cache


_SELECT = """
select id, title, organization, location, district, type, minimum_experience,
       certifications_required, salary_min, salary_max, nsqf_level,
       source_reference, description
from opportunities
"""


def _row_to_opportunity(row) -> Opportunity:
    return Opportunity(
        id=row["id"],
        title=row["title"],
        organization=row["organization"],
        location=row["location"],
        district=row["district"],
        type=row["type"],
        minimum_experience=float(row["minimum_experience"]),
        certifications_required=list(row["certifications_required"] or []),
        salary_min=row["salary_min"],
        salary_max=row["salary_max"],
        nsqf_level=row["nsqf_level"],
        source_reference=row["source_reference"],
        description=row["description"],
    )


async def list_active(district: str | None = None) -> list[Opportunity]:
    """The full active catalogue, with required skills and their embeddings."""
    if not db.is_available():
        items = await _memory_opportunities()
        if district:
            return [o for o in items if o.district == district]
        return list(items)

    if district:
        rows = await db.fetch(
            _SELECT + " where is_active and district = $1 order by id", district
        )
    else:
        rows = await db.fetch(_SELECT + " where is_active order by id")

    opportunities = {r["id"]: _row_to_opportunity(r) for r in rows}
    if not opportunities:
        return []

    skill_rows = await db.fetch(
        "select opportunity_id, skill_id, skill_code, skill_name, weight, "
        "is_essential, embedding::text as embedding "
        "from opportunity_skill_vectors($1)",
        district,
    )
    for row in skill_rows:
        target = opportunities.get(row["opportunity_id"])
        if target is None:
            continue
        raw = row["embedding"]
        vector = (
            [float(x) for x in raw.strip("[]").split(",") if x] if raw else None
        )
        target.required_skills.append(
            RequiredSkill(
                skill_id=row["skill_id"],
                code=row["skill_code"],
                name=row["skill_name"],
                weight=float(row["weight"]),
                is_essential=bool(row["is_essential"]),
                embedding=vector,
            )
        )
    return list(opportunities.values())


async def get(opportunity_id: int) -> Opportunity | None:
    if not db.is_available():
        for item in await _memory_opportunities():
            if item.id == opportunity_id:
                return item
        return None

    row = await db.fetchrow(_SELECT + " where id = $1", opportunity_id)
    if row is None:
        return None
    opportunity = _row_to_opportunity(row)
    skill_rows = await db.fetch(
        "select os.skill_id, t.code, t.name, os.weight, os.is_essential "
        "from opportunity_skills os "
        "join skill_taxonomy t on t.id = os.skill_id "
        "where os.opportunity_id = $1 "
        "order by os.is_essential desc, os.weight desc",
        opportunity_id,
    )
    opportunity.required_skills = [
        RequiredSkill(
            skill_id=r["skill_id"],
            code=r["code"],
            name=r["name"],
            weight=float(r["weight"]),
            is_essential=bool(r["is_essential"]),
        )
        for r in skill_rows
    ]
    return opportunity

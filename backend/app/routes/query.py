"""Query understanding (PRD section 6).

One question: what was this person doing when they said that? Describing work
that should be turned into skills, asking something a scheme document can
answer, or both at once.

It decides and nothing else. The steps it routes to keep their own guarantees:
extraction verifies every quote against the transcript, and the guidelines
answer cites a passage or refuses. Putting a guarantee behind a classifier
would be putting it behind a guess.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.models import schemas
from app.services import intent
from app.services.ratelimit import default_limit

router = APIRouter(prefix="/api/query", tags=["query"])


@router.post(
    "/understand",
    response_model=schemas.QueryUnderstandResponse,
    dependencies=[Depends(default_limit)],
)
async def understand(
    payload: schemas.QueryUnderstandRequest,
) -> schemas.QueryUnderstandResponse:
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="There was nothing to read.",
        )

    result = await intent.classify(text)
    return schemas.QueryUnderstandResponse(
        describes_work=result.describes_work,
        asks_question=result.asks_question,
        question=result.question,
        provider=result.provider,
    )

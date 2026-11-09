"""Jobs, training and schemes: three kinds of record in one table (2026-11-09).

Everything VoicePath lists used to be a "scheme" with a free-text ``type``, so
a job and a training course were told apart only by that label, scored with
the same weights, and carried the same fields. Decided 2026-11-09: keep one
table (every link, match and id keeps working), add a ``kind``, give each kind
the details that matter for it, and score each with its own weights.

The kind follows from the type, which admins already choose, so the two can
never disagree.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Literal

Kind = Literal["job", "training", "scheme"]
KINDS: tuple[str, ...] = ("job", "training", "scheme")

_KIND_BY_TYPE: dict[str, str] = {
    "Full-time": "job",
    "Part-time": "job",
    "Training": "training",
    # Paid learning on the job: it is training, though the explanation still
    # words it as an apprenticeship (it reads ``type`` for that).
    "Apprenticeship": "training",
    "Self-employment support": "scheme",
}


def kind_for_type(scheme_type: str | None) -> str:
    return _KIND_BY_TYPE.get(scheme_type or "", "scheme")


# ---------------------------------------------------------------------------
# Weights per kind
# ---------------------------------------------------------------------------
#
# Decided 2026-11-09. Each sums to 1, as the single set before did (skill 0.50,
# experience 0.25, eligibility 0.15, location 0.10).
#
# * A job asks what you have done: experience weighs more.
# * Training is for learning, so experience barely counts -- but you have to
#   get there every day, so distance counts most after skill.
# * A scheme is a matter of who qualifies: eligibility weighs most after skill.

WEIGHTS: dict[str, dict[str, float]] = {
    "job":      {"skill": 0.50, "experience": 0.30, "eligibility": 0.10, "location": 0.10},
    "training": {"skill": 0.40, "experience": 0.05, "eligibility": 0.20, "location": 0.35},
    "scheme":   {"skill": 0.45, "experience": 0.15, "eligibility": 0.30, "location": 0.10},
}


def weights_for(kind: str | None) -> dict[str, float]:
    return dict(WEIGHTS.get(kind or "", WEIGHTS["scheme"]))


# ---------------------------------------------------------------------------
# Details per kind
# ---------------------------------------------------------------------------
#
# Only what a listing states. Structured -- numbers, dates, yes or no, a fixed
# choice -- so the screen can say each in Tamil and Hindi; the one free-text
# field, how to apply, is quoted from the official source.

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DETAIL_FIELDS: dict[str, dict[str, str]] = {
    "job": {
        "openings": "int",          # how many people are wanted
        "apply_by": "date",         # last day to apply
        "days_per_week": "int",
        "shift_work": "bool",
    },
    "training": {
        "duration_months": "number",
        "stipend_monthly": "int",   # rupees a month paid to the trainee
        "course_fee": "int",        # rupees; 0 means free
        "next_batch": "date",
        "mode": "in_person|online",
    },
    "scheme": {
        "benefit_max": "int",       # rupees, the most the scheme gives
        "installments": "int",      # paid in this many parts
        "how_to_apply": "text",     # quoted from the official source
    },
}


def clean_details(kind: str, details: dict[str, Any] | None) -> dict[str, Any]:
    """Keep the fields this kind has, in the shapes they must have.

    Raises ValueError naming the first field that is wrong, so an admin form
    says what to fix instead of silently dropping it.
    """
    allowed = DETAIL_FIELDS.get(kind, {})
    out: dict[str, Any] = {}
    for name, value in (details or {}).items():
        if value is None or value == "":
            continue
        shape = allowed.get(name)
        if shape is None:
            raise ValueError(f"'{name}' is not a detail a {kind} has")
        if shape == "int":
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 \
                    or int(value) != value:
                raise ValueError(f"'{name}' must be a whole number of 0 or more")
            out[name] = int(value)
        elif shape == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(f"'{name}' must be a number above 0")
            out[name] = float(value) if int(value) != value else int(value)
        elif shape == "bool":
            if not isinstance(value, bool):
                raise ValueError(f"'{name}' must be true or false")
            out[name] = value
        elif shape == "date":
            if not isinstance(value, str) or not _DATE.match(value):
                raise ValueError(f"'{name}' must be a date, YYYY-MM-DD")
            date.fromisoformat(value)  # a real date, not 2026-02-31
            out[name] = value
        elif shape == "text":
            if not isinstance(value, str) or len(value.strip()) > 600:
                raise ValueError(f"'{name}' must be text of at most 600 characters")
            out[name] = value.strip()
        else:  # a fixed choice, written "a|b"
            if value not in shape.split("|"):
                raise ValueError(f"'{name}' must be one of {shape.replace('|', ', ')}")
            out[name] = value
    return out

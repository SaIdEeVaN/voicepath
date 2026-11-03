"""The map: what is near a person (openings, and offices that can help).

Reads only. Nothing about a request here is written anywhere -- not the
place, not the coordinates -- and a device location is coarsened before the
service does anything with it.

Both lookups are POST so a location travels in the body: query strings end
up in access logs, and a location is exactly what should not.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.models import schemas
from app.services import places, schemes
from app.services.ratelimit import default_limit

router = APIRouter(prefix="/api/places", tags=["places"])


@router.post(
    "/nearby",
    response_model=schemas.NearbyResponse,
    dependencies=[Depends(default_limit)],
)
async def nearby(payload: schemas.NearbyRequest) -> schemas.NearbyResponse:
    """Where the map centres, and the openings by town, nearest first.

    Answered from the catalogue and the gazetteer alone, so it is instant and
    works with no network. Offices are ``/support``, asked for separately.
    """
    catalogue = await schemes.list_active()
    centre = places.resolve_centre(
        place=payload.place,
        latitude=payload.latitude,
        longitude=payload.longitude,
        catalogue=catalogue,
    )
    groups, unplaced = places.scheme_places(catalogue, centre)

    return schemas.NearbyResponse(
        centre=schemas.NearbyCentre(
            latitude=centre.latitude,
            longitude=centre.longitude,
            source=centre.source,
            key=centre.key,
            names=centre.names,
        ),
        scheme_places=[
            schemas.NearbySchemePlace(
                key=group.key,
                names=group.names,
                latitude=group.latitude,
                longitude=group.longitude,
                distance_km=group.distance_km,
                schemes=[
                    schemas.NearbySchemeRef(
                        id=s.id, title=s.title, organization=s.organization, type=s.type
                    )
                    for s in group.schemes
                ],
            )
            for group in groups
        ],
        unplaced_schemes=[
            schemas.NearbySchemeRef(
                id=s.id, title=s.title, organization=s.organization, type=s.type
            )
            for s in unplaced
        ],
    )


@router.post(
    "/support",
    response_model=schemas.SupportResponse,
    dependencies=[Depends(default_limit)],
)
async def support(payload: schemas.SupportRequest) -> schemas.SupportResponse:
    """Training centres, employment and government offices, and banks nearby.

    From OpenStreetMap. ``support_status`` separates "nothing is mapped here"
    from "could not look just now" -- an empty list means different things in
    each, and the person is told which.
    """
    offices, status = await places.support_places(
        latitude=payload.latitude,
        longitude=payload.longitude,
        radius_km=payload.radius_km,
        categories=payload.categories,
    )
    return schemas.SupportResponse(
        support_places=[
            schemas.SupportPlace(
                id=p.id,
                category=p.category,
                name=p.name,
                names=p.names,
                latitude=p.latitude,
                longitude=p.longitude,
                distance_km=p.distance_km,
                address=p.address,
                opening_hours=p.opening_hours,
                osm_url=p.osm_url,
            )
            for p in offices
        ],
        support_status=status,
        radius_km=payload.radius_km,
        provider=places.provider_name(),
        degraded=status != "ok",
        attribution=places.ATTRIBUTION,
    )


@router.get("/known", response_model=list[schemas.KnownPlace])
async def known() -> list[schemas.KnownPlace]:
    """Towns the map can centre on, for someone whose place we did not catch."""
    return [
        schemas.KnownPlace(
            key=key,
            district=entry["district"],
            names=dict(entry["names"]),
            latitude=entry["latitude"],
            longitude=entry["longitude"],
        )
        for key, entry in places.known_places()
    ]


"""API for the Job Hunt Intelligence System."""

from typing import Any, Literal

import psycopg
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.application_lifecycle import record_application_event
from src.database.connection import get_connection


app = FastAPI(
    title="Job Hunt Intelligence System",
    description="Jobs, applications, and application lifecycle tracking.",
    version="0.3.0",
)


class ApplicationEventRequest(BaseModel):
    event_type: Literal[
        "APPLICATION_STARTED",
        "APPLICATION_SUBMITTED",
        "APPLICATION_VIEWED",
        "RECRUITER_CONTACTED",
        "ASSESSMENT_RECEIVED",
        "ASSESSMENT_COMPLETED",
        "INTERVIEW_SCHEDULED",
        "INTERVIEW_COMPLETED",
        "REJECTED",
        "OFFER_RECEIVED",
        "WITHDRAWN",
    ]
    notes: str | None = Field(default=None, max_length=2000)


def fetch_all_as_dicts(cur: Any) -> list[dict[str, Any]]:
    columns = [column.name for column in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


@app.get("/", tags=["Health"])
def root() -> dict[str, str]:
    return {
        "name": "Job Hunt Intelligence System",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/database", tags=["Health"])
def database_health() -> dict[str, str]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        return {"status": "ok", "database": "connected"}
    except (psycopg.Error, RuntimeError):
        raise HTTPException(
            status_code=503,
            detail="Database connection unavailable.",
        )


@app.get("/api/v1/jobs", tags=["Jobs"])
def list_jobs(
    search: str | None = Query(default=None, max_length=200),
    location: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    conditions = []
    params: list[Any] = []

    if search:
        conditions.append(
            "(j.company ILIKE %s OR j.job_title ILIKE %s)"
        )
        term = f"%{search}%"
        params.extend([term, term])

    if location:
        conditions.append("j.location ILIKE %s")
        params.append(f"%{location}%")

    where_clause = (
        "WHERE " + " AND ".join(conditions)
        if conditions
        else ""
    )

    sql = f"""
        SELECT
            j.job_id, j.company, j.job_title, j.location,
            j.employment_type, j.job_url, j.salary_min,
            j.salary_max, j.description, j.discovered_at
        FROM jobs j
        {where_clause}
        ORDER BY j.discovered_at DESC NULLS LAST, j.job_id DESC
        LIMIT %s OFFSET %s;
    """

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params + [limit, offset])
                items = fetch_all_as_dicts(cur)

        return {
            "count": len(items),
            "limit": limit,
            "offset": offset,
            "items": items,
        }
    except (psycopg.Error, RuntimeError):
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve jobs.",
        )


@app.get("/api/v1/applications", tags=["Applications"])
def list_applications(
    status: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    conditions = []
    params: list[Any] = []

    if status:
        conditions.append("a.current_status ILIKE %s")
        params.append(status)

    where_clause = (
        "WHERE " + " AND ".join(conditions)
        if conditions
        else ""
    )

    sql = f"""
        SELECT
            a.application_id, a.user_id, a.job_id, a.resume_id,
            a.source, a.applied_at, a.current_status,
            j.company, j.job_title, j.location, j.job_url
        FROM applications a
        JOIN jobs j ON j.job_id = a.job_id
        {where_clause}
        ORDER BY a.applied_at DESC NULLS LAST,
                 a.application_id DESC
        LIMIT %s OFFSET %s;
    """

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params + [limit, offset])
                items = fetch_all_as_dicts(cur)

        return {
            "count": len(items),
            "limit": limit,
            "offset": offset,
            "items": items,
        }
    except (psycopg.Error, RuntimeError):
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve applications.",
        )


@app.get(
    "/api/v1/applications/{application_id}/events",
    tags=["Applications"],
)
def get_application_events(
    application_id: int,
) -> dict[str, Any]:
    if application_id < 1:
        raise HTTPException(
            status_code=422,
            detail="application_id must be positive.",
        )

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT application_id
                    FROM applications
                    WHERE application_id = %s;
                    """,
                    (application_id,),
                )
                if cur.fetchone() is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Application not found.",
                    )

                cur.execute(
                    """
                    SELECT event_id, application_id,
                           event_type, event_at, notes
                    FROM application_events
                    WHERE application_id = %s
                    ORDER BY event_at DESC, event_id DESC;
                    """,
                    (application_id,),
                )
                items = fetch_all_as_dicts(cur)

        return {
            "application_id": application_id,
            "count": len(items),
            "items": items,
        }
    except (psycopg.Error, RuntimeError):
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve application events.",
        )


@app.post(
    "/api/v1/applications/{application_id}/events",
    tags=["Applications"],
    status_code=201,
)
def create_application_event(
    application_id: int,
    event: ApplicationEventRequest,
) -> dict[str, Any]:
    if application_id < 1:
        raise HTTPException(
            status_code=422,
            detail="application_id must be positive.",
        )

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT application_id
                    FROM applications
                    WHERE application_id = %s;
                    """,
                    (application_id,),
                )
                if cur.fetchone() is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Application not found.",
                    )

        event_id = record_application_event(
            application_id=application_id,
            event_type=event.event_type,
            notes=event.notes,
        )

        return {
            "message": "Application event recorded.",
            "application_id": application_id,
            "event_id": event_id,
            "event_type": event.event_type,
        }

    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )
    except (psycopg.Error, RuntimeError):
        raise HTTPException(
            status_code=503,
            detail="Unable to record application event.",
        )

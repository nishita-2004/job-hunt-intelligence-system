"""Record application lifecycle events and keep application status synchronized."""

from typing import Optional

from src.database.connection import get_connection


SUPPORTED_EVENT_TYPES = {
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
}

# Only events that establish a meaningful application status update it.
EVENT_TO_STATUS = {
    "APPLICATION_SUBMITTED": "APPLIED",
    "RECRUITER_CONTACTED": "RECRUITER_CONTACTED",
    "ASSESSMENT_RECEIVED": "ASSESSMENT_RECEIVED",
    "ASSESSMENT_COMPLETED": "ASSESSMENT_COMPLETED",
    "INTERVIEW_SCHEDULED": "INTERVIEW_SCHEDULED",
    "INTERVIEW_COMPLETED": "INTERVIEW_COMPLETED",
    "REJECTED": "REJECTED",
    "OFFER_RECEIVED": "OFFER_RECEIVED",
    "WITHDRAWN": "WITHDRAWN",
}

# These statuses must not be overwritten by later events.
TERMINAL_STATUSES = {
    "REJECTED",
    "OFFER_RECEIVED",
    "WITHDRAWN",
}


def record_application_event(
    application_id: int,
    event_type: str,
    notes: Optional[str] = None,
) -> int:
    """Record an application event and synchronize its status atomically.

    Returns the new event ID. If validation or a database operation fails,
    no partial event/status update is committed.
    """
    if isinstance(application_id, bool) or not isinstance(application_id, int):
        raise ValueError("application_id must be a positive integer.")

    if application_id <= 0:
        raise ValueError("application_id must be a positive integer.")

    if not isinstance(event_type, str) or event_type not in SUPPORTED_EVENT_TYPES:
        raise ValueError(
            f"Unsupported application event type: {event_type!r}"
        )

    if notes is not None and not isinstance(notes, str):
        raise ValueError("notes must be a string or None.")

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Lock the application while its event and status are updated.
            cur.execute(
                """
                SELECT current_status
                FROM applications
                WHERE application_id = %s
                FOR UPDATE;
                """,
                (application_id,),
            )

            application = cur.fetchone()

            if application is None:
                raise ValueError(
                    f"Application {application_id} does not exist."
                )

            current_status = application[0]

            cur.execute(
                """
                INSERT INTO application_events (
                    application_id,
                    event_type,
                    notes
                )
                VALUES (%s, %s, %s)
                RETURNING event_id;
                """,
                (application_id, event_type, notes),
            )
            event_id = cur.fetchone()[0]

            new_status = EVENT_TO_STATUS.get(event_type)

            if (
                new_status is not None
                and current_status not in TERMINAL_STATUSES
            ):
                cur.execute(
                    """
                    UPDATE applications
                    SET current_status = %s
                    WHERE application_id = %s;
                    """,
                    (new_status, application_id),
                )

        # The connection context commits on success and rolls back on error.
        return event_id

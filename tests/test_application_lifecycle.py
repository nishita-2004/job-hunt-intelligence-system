
"""Tests for application lifecycle event recording and status synchronization."""

from unittest.mock import MagicMock, patch

import pytest

from src.application_lifecycle import record_application_event


@pytest.fixture
def db():
    """Provide a mocked database connection and cursor."""
    conn = MagicMock()
    cur = MagicMock()

    conn.__enter__.return_value = conn
    conn.cursor.return_value.__enter__.return_value = cur

    with patch(
        "src.application_lifecycle.get_connection",
        return_value=conn,
    ):
        yield conn, cur


def test_record_event_returns_event_id(db):
    conn, cur = db
    cur.fetchone.side_effect = [(101,), (501,)]

    event_id = record_application_event(
        application_id=101,
        event_type="APPLICATION_SUBMITTED",
        notes="Applied through company website",
    )

    assert event_id == 501
    assert cur.execute.call_count == 3
    assert conn.cursor.return_value.__enter__.called


def test_event_is_inserted_with_correct_values(db):
    _, cur = db
    cur.fetchone.side_effect = [(101,), (501,)]

    record_application_event(
        101,
        "APPLICATION_SUBMITTED",
        "Applied online",
    )

    insert_call = cur.execute.call_args_list[1]

    assert "INSERT INTO application_events" in insert_call.args[0]
    assert insert_call.args[1] == (
        101,
        "APPLICATION_SUBMITTED",
        "Applied online",
    )


def test_submission_updates_status_to_applied(db):
    _, cur = db
    cur.fetchone.side_effect = [(101,), (501,)]

    record_application_event(101, "APPLICATION_SUBMITTED")

    update_call = cur.execute.call_args_list[2]

    assert "UPDATE applications" in update_call.args[0]
    assert update_call.args[1] == ("APPLIED", 101)


def test_non_status_event_does_not_update_status(db):
    _, cur = db
    cur.fetchone.side_effect = [(101,), (501,)]

    record_application_event(101, "APPLICATION_VIEWED")

    assert cur.execute.call_count == 2


def test_missing_application_raises_error(db):
    _, cur = db
    cur.fetchone.return_value = None

    with pytest.raises(ValueError, match="does not exist"):
        record_application_event(999, "APPLICATION_SUBMITTED")

    assert cur.execute.call_count == 1


@pytest.mark.parametrize(
    "application_id",
    [0, -1, True, False, None, "101", 1.5],
)
def test_invalid_application_id_is_rejected(application_id, db):
    _, cur = db

    with pytest.raises(ValueError, match="positive integer"):
        record_application_event(
            application_id,
            "APPLICATION_SUBMITTED",
        )

    cur.execute.assert_not_called()


@pytest.mark.parametrize(
    "event_type",
    ["", "UNKNOWN_EVENT", "applied", None, 123],
)
def test_invalid_event_type_is_rejected(event_type, db):
    _, cur = db

    with pytest.raises(
        ValueError,
        match="Unsupported application event type",
    ):
        record_application_event(101, event_type)

    cur.execute.assert_not_called()


@pytest.mark.parametrize("notes", [123, True, [], {}])
def test_invalid_notes_are_rejected(notes, db):
    _, cur = db

    with pytest.raises(
        ValueError,
        match="notes must be a string or None",
    ):
        record_application_event(
            101,
            "APPLICATION_SUBMITTED",
            notes,
        )

    cur.execute.assert_not_called()


def test_database_insert_failure_prevents_status_update(db):
    _, cur = db
    cur.fetchone.return_value = (101,)
    cur.execute.side_effect = [
        None,
        RuntimeError("Simulated insert failure"),
    ]

    with pytest.raises(
        RuntimeError,
        match="Simulated insert failure",
    ):
        record_application_event(101, "APPLICATION_SUBMITTED")

    assert cur.execute.call_count == 2


@pytest.mark.parametrize(
    "terminal_status",
    ["REJECTED", "OFFER_RECEIVED", "WITHDRAWN"],
)
def test_terminal_status_is_not_overwritten(terminal_status, db):
    _, cur = db
    cur.fetchone.side_effect = [
        (terminal_status,),
        (501,),
    ]

    event_id = record_application_event(
        101,
        "INTERVIEW_SCHEDULED",
        "Late-arriving interview event",
    )

    assert event_id == 501
    assert cur.execute.call_count == 2

    insert_call = cur.execute.call_args_list[1]

    assert "INSERT INTO application_events" in insert_call.args[0]
    assert insert_call.args[1] == (
        101,
        "INTERVIEW_SCHEDULED",
        "Late-arriving interview event",
    )

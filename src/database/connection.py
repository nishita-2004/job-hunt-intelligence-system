
import os
import psycopg


def get_connection():
    """Create a connection to the Career Intelligence database."""
    password = os.environ.get("PGPASSWORD")

    if not password:
        raise RuntimeError(
            "PGPASSWORD is not set in this terminal."
        )

    database = os.environ.get(
        "PGDATABASE",
        "job_hunt_intelligence",
    )

    return psycopg.connect(
        host="localhost",
        dbname=database,
        user="postgres",
        password=password,
    )

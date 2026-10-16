
from urllib.parse import urlsplit, urlunsplit

from src.database.connection import get_connection


def normalize_job_url(job_url):
    """
    Normalize a job URL for duplicate comparison.

    Returns None for a missing or blank URL.
    Preserves query parameters and removes fragments.
    Removes default HTTP (80) and HTTPS (443) ports.
    """
    if job_url is None:
        return None

    if not isinstance(job_url, str):
        raise ValueError("job_url must be a string or None.")

    job_url = job_url.strip()

    if not job_url:
        return None

    parts = urlsplit(job_url)
    scheme = parts.scheme.lower()
    hostname = parts.hostname
    port = parts.port

    if hostname is None:
        netloc = parts.netloc.lower()
    else:
        userinfo = ""
        if "@" in parts.netloc:
            userinfo = parts.netloc.rsplit("@", 1)[0] + "@"

        if ":" in hostname:
            normalized_hostname = f"[{hostname.lower()}]"
        else:
            normalized_hostname = hostname.lower()

        if (scheme == "https" and port == 443) or (
            scheme == "http" and port == 80
        ):
            port = None

        port_suffix = f":{port}" if port is not None else ""
        netloc = f"{userinfo}{normalized_hostname}{port_suffix}"

    path = parts.path.rstrip("/") or "/"

    return urlunsplit((scheme, netloc, path, parts.query, ""))


def find_possible_duplicates(
    company,
    job_title,
    location=None,
    job_url=None,
):
    """
    Find possible duplicate jobs without changing the database.

    URL matches are high-confidence candidates.
    Company/title matches require review.
    """
    if not isinstance(company, str) or not company.strip():
        raise ValueError("company must be a non-empty string.")

    if not isinstance(job_title, str) or not job_title.strip():
        raise ValueError("job_title must be a non-empty string.")

    if job_url is not None and not isinstance(job_url, str):
        raise ValueError("job_url must be a string or None.")

    if location is not None and not isinstance(location, str):
        raise ValueError("location must be a string or None.")

    company_key = company.strip().casefold()
    title_key = job_title.strip().casefold()
    location_key = location.strip().casefold() if location else None
    normalized_url = normalize_job_url(job_url)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT job_id, company, job_title, location, job_url
                FROM jobs
                ORDER BY job_id;
                """
            )
            existing_jobs = cur.fetchall()

    possible_duplicates = []

    for job in existing_jobs:
        (
            existing_id,
            existing_company,
            existing_title,
            existing_location,
            existing_url,
        ) = job

        existing_normalized_url = normalize_job_url(existing_url)

        if (
            normalized_url is not None
            and existing_normalized_url == normalized_url
        ):
            possible_duplicates.append(
                {
                    "job_id": existing_id,
                    "company": existing_company,
                    "job_title": existing_title,
                    "location": existing_location,
                    "job_url": existing_url,
                    "match_type": "URL_MATCH",
                    "confidence": "HIGH",
                }
            )
            continue

        same_company_title = (
            existing_company.strip().casefold() == company_key
            and existing_title.strip().casefold() == title_key
        )

        if same_company_title:
            existing_location_key = (
                existing_location.strip().casefold()
                if existing_location
                else None
            )

            same_location = (
                location_key is not None
                and existing_location_key == location_key
            )

            possible_duplicates.append(
                {
                    "job_id": existing_id,
                    "company": existing_company,
                    "job_title": existing_title,
                    "location": existing_location,
                    "job_url": existing_url,
                    "match_type": (
                        "COMPANY_TITLE_LOCATION_MATCH"
                        if same_location
                        else "COMPANY_TITLE_MATCH"
                    ),
                    "confidence": "REVIEW",
                }
            )

    return possible_duplicates


def preview_job(
    user_id,
    company,
    job_title,
    location=None,
    job_url=None,
):
    """
    Preview a job before insertion.

    Finds possible duplicates without inserting or modifying records.
    """
    if (
        isinstance(user_id, bool)
        or not isinstance(user_id, int)
        or user_id <= 0
    ):
        raise ValueError("user_id must be a positive integer.")

    duplicates = find_possible_duplicates(
        company=company,
        job_title=job_title,
        location=location,
        job_url=job_url,
    )

    return {
        "user_id": user_id,
        "company": company.strip(),
        "job_title": job_title.strip(),
        "location": location,
        "job_url": job_url,
        "has_possible_duplicates": bool(duplicates),
        "possible_duplicates": duplicates,
        "requires_review": bool(duplicates),
    }


def add_job(
    user_id,
    company,
    job_title,
    source=None,
    notes=None,
    location=None,
    employment_type=None,
    job_url=None,
    salary_min=None,
    salary_max=None,
    description=None,
):
    """Insert a job and its JOB_FOUND event atomically."""
    import math

    if (
        isinstance(user_id, bool)
        or not isinstance(user_id, int)
        or user_id <= 0
    ):
        raise ValueError("user_id must be a positive integer.")

    if not isinstance(company, str) or not company.strip():
        raise ValueError("company must be a non-empty string.")

    if not isinstance(job_title, str) or not job_title.strip():
        raise ValueError("job_title must be a non-empty string.")

    if job_url is not None and not isinstance(job_url, str):
        raise ValueError("job_url must be a string or None.")

    if source is not None and not isinstance(source, str):
        raise ValueError("source must be a string or None.")

    if notes is not None and not isinstance(notes, str):
        raise ValueError("notes must be a string or None.")

    if location is not None and not isinstance(location, str):
        raise ValueError("location must be a string or None.")

    if employment_type is not None and not isinstance(
        employment_type, str
    ):
        raise ValueError("employment_type must be a string or None.")

    if description is not None and not isinstance(description, str):
        raise ValueError("description must be a string or None.")

    for field_name, value in (
        ("salary_min", salary_min),
        ("salary_max", salary_max),
    ):
        if value is None:
            continue

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field_name} must be a number or None.")

        if not math.isfinite(value):
            raise ValueError(f"{field_name} must be a number or None.")

        if value < 0:
            raise ValueError(f"{field_name} cannot be negative.")

    if (
        salary_min is not None
        and salary_max is not None
        and salary_min > salary_max
    ):
        raise ValueError("salary_min cannot exceed salary_max.")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO jobs (
                    company,
                    job_title,
                    location,
                    employment_type,
                    job_url,
                    salary_min,
                    salary_max,
                    description
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING job_id;
                """,
                (
                    company.strip(),
                    job_title.strip(),
                    location.strip() if location else None,
                    (
                        employment_type.strip()
                        if employment_type
                        else None
                    ),
                    (
                        job_url.strip()
                        if job_url and job_url.strip()
                        else None
                    ),
                    salary_min,
                    salary_max,
                    description,
                ),
            )

            job_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO job_events (
                    user_id,
                    job_id,
                    event_type,
                    source,
                    notes
                )
                VALUES (%s, %s, 'JOB_FOUND', %s, %s);
                """,
                (
                    user_id,
                    job_id,
                    source.strip() if source and source.strip() else None,
                    notes.strip() if notes and notes.strip() else None,
                ),
            )

    return job_id

# Job Hunt Intelligence System — Data Dictionary

## Core Principle

Store observed facts and events.
Derived metrics and insights should be calculated from those facts.

---

## Users

Represents a person using the system.

| Field | Meaning |
| user_id | Unique identifier for the user |
| created_at | When the user was created |

---

## Jobs

Represents a job opportunity.

| Field | Meaning |
| job_id | Unique identifier |
| company | Company offering the job |
| job_title | Job title |
| location | Job location |
| employment_type | Full-time, internship, contract, etc. |
| job_url | Original job posting |
| salary_min | Minimum advertised salary |
| salary_max | Maximum advertised salary |
| description | Job description |
| discovered_at | When the system/user discovered the job |

---

## Resumes

Represents a version of a user's resume.

| Field | Meaning |
| resume_id | Unique identifier |
| user_id | Owner of the resume |
| resume_name | Human-readable name |
| version | Resume version |
| created_at | Creation timestamp |

---

## Applications

Represents a user's application to a specific job.

| Field | Meaning |
| application_id | Unique identifier |
| user_id | Applicant |
| job_id | Job being applied to |
| resume_id | Resume version used |
| source | Where the job/application came from |
| applied_at | Application timestamp |
| current_status | Current known application status |

---

## Application Events

Represents something that actually happened during an application journey.

| Field | Meaning |
| event_id | Unique identifier |
| application_id | Related application |
| event_type | Type of event |
| event_at | When the event happened |
| notes | Optional additional information |

---

## Event Types

Allowed event types initially include:

- JOB_FOUND
- JOB_SAVED
- APPLICATION_STARTED
- APPLICATION_SUBMITTED
- APPLICATION_VIEWED
- RECRUITER_CONTACTED
- ASSESSMENT_RECEIVED
- ASSESSMENT_COMPLETED
- INTERVIEW_SCHEDULED
- INTERVIEW_COMPLETED
- REJECTED
- OFFER_RECEIVED
- WITHDRAWN

---

## Derived Concepts

The following should NOT initially be stored as raw events.

Examples:

- NO_RESPONSE
- RESPONSE_RATE
- INTERVIEW_RATE
- OFFER_RATE
- TIME_TO_RESPONSE
- TIME_TO_INTERVIEW
- APPLICATION_FUNNEL
- JOB_SEARCH_LEAK
- RECOMMENDED_ACTION

These should be calculated from observed data.

---

## Data Quality Principles

1. Store facts rather than assumptions.
2. Do not treat missing data as zero.
3. Do not automatically treat missing events as negative outcomes.
4. Keep original/raw data separate from transformed data.
5. Derived metrics should be reproducible from source data.
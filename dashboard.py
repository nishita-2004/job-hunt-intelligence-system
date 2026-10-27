import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Job Hunt Intelligence System",
    page_icon="🎯",
    layout="wide",
)

st.title("🎯 Job Hunt Intelligence System")
st.caption("Your personal job search and application tracker")

page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Jobs", "Applications"],
)

@st.cache_data(ttl=15)
def fetch_data(endpoint, params=None):
    response = requests.get(
        f"{API_URL}{endpoint}",
        params=params,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()

try:
    fetch_data("/health/database")
    st.sidebar.success("Database connected")
except requests.RequestException:
    st.sidebar.error("API unavailable")
    st.error("Start the API in another terminal: python -m uvicorn src.api:app --reload")
    st.stop()

if page == "Dashboard":
    jobs = fetch_data("/api/v1/jobs").get("items", [])
    applications = fetch_data("/api/v1/applications").get("items", [])

    col1, col2, col3 = st.columns(3)
    col1.metric("Jobs Available", len(jobs))
    col2.metric("Applications Tracked", len(applications))
    col3.metric(
        "Interviews",
        sum("INTERVIEW" in str(a.get("current_status", "")).upper()
            for a in applications),
    )

    st.subheader("Recent Jobs")
    if jobs:
        st.dataframe(jobs, use_container_width=True)
    else:
        st.info("No jobs found yet.")

elif page == "Jobs":
    search = st.text_input("Search company or job title")
    location = st.text_input("Filter by location")

    params = {}
    if search.strip():
        params["search"] = search.strip()
    if location.strip():
        params["location"] = location.strip()

    try:
        jobs = fetch_data("/api/v1/jobs", params).get("items", [])
        st.write(f"Found {len(jobs)} jobs")
        st.dataframe(jobs, use_container_width=True)
    except requests.RequestException:
        st.error("Unable to load jobs.")

elif page == "Applications":
    status = st.selectbox(
        "Filter by status",
        ["All", "APPLIED", "INTERVIEW_SCHEDULED",
         "OFFER_RECEIVED", "REJECTED", "WITHDRAWN"],
    )

    params = {} if status == "All" else {"status": status}

    try:
        applications = fetch_data(
            "/api/v1/applications", params
        ).get("items", [])
        st.write(f"Showing {len(applications)} applications")
        st.dataframe(applications, use_container_width=True)
    except requests.RequestException:
        st.error("Unable to load applications.")

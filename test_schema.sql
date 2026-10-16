--
-- PostgreSQL database dump
--

\restrict LPhhWF3gDqUNkc7ra7YnwWM2QObPvOplRAfibiJK0IFN1ieFWUjZkhXVMA5TE7K

-- Dumped from database version 18.6
-- Dumped by pg_dump version 18.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: application_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.application_events (
    event_id bigint NOT NULL,
    application_id bigint NOT NULL,
    event_type text NOT NULL,
    event_at timestamp with time zone DEFAULT now() NOT NULL,
    notes text
);


--
-- Name: application_events_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.application_events ALTER COLUMN event_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.application_events_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: applications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.applications (
    application_id bigint NOT NULL,
    user_id bigint NOT NULL,
    job_id bigint NOT NULL,
    resume_id bigint NOT NULL,
    source text,
    applied_at timestamp with time zone DEFAULT now() NOT NULL,
    current_status text
);


--
-- Name: applications_application_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.applications ALTER COLUMN application_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.applications_application_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.jobs (
    job_id bigint NOT NULL,
    company text NOT NULL,
    job_title text NOT NULL,
    location text,
    employment_type text,
    job_url text,
    salary_min numeric,
    salary_max numeric,
    description text,
    discovered_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: applications_needing_attention; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.applications_needing_attention AS
 SELECT a.application_id,
    j.company,
    j.job_title,
    a.source,
    (a.applied_at)::date AS applied_date,
    (CURRENT_DATE - (a.applied_at)::date) AS days_waiting,
    'No qualifying response or outcome event recorded'::text AS attention_reason
   FROM (public.applications a
     JOIN public.jobs j ON ((j.job_id = a.job_id)))
  WHERE (((CURRENT_DATE - (a.applied_at)::date) >= 3) AND (NOT (EXISTS ( SELECT 1
           FROM public.application_events e
          WHERE ((e.application_id = a.application_id) AND (e.event_type = ANY (ARRAY['RECRUITER_CONTACTED'::text, 'ASSESSMENT_RECEIVED'::text, 'ASSESSMENT_COMPLETED'::text, 'INTERVIEW_SCHEDULED'::text, 'INTERVIEW_COMPLETED'::text, 'OFFER_RECEIVED'::text, 'REJECTED'::text, 'WITHDRAWN'::text])))))));


--
-- Name: job_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.job_events (
    job_event_id bigint NOT NULL,
    user_id bigint NOT NULL,
    job_id bigint NOT NULL,
    event_type text NOT NULL,
    event_at timestamp with time zone DEFAULT now() NOT NULL,
    source text,
    notes text,
    CONSTRAINT chk_job_event_type CHECK ((event_type = ANY (ARRAY['JOB_FOUND'::text, 'JOB_SAVED'::text, 'JOB_UNSAVED'::text])))
);


--
-- Name: job_events_job_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.job_events ALTER COLUMN job_event_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.job_events_job_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: job_save_status; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.job_save_status AS
 WITH latest_save_action AS (
         SELECT DISTINCT ON (je.user_id, je.job_id) je.user_id,
            je.job_id,
            je.event_type,
            je.event_at
           FROM public.job_events je
          WHERE (je.event_type = ANY (ARRAY['JOB_SAVED'::text, 'JOB_UNSAVED'::text]))
          ORDER BY je.user_id, je.job_id, je.event_at DESC, je.job_event_id DESC
        )
 SELECT j.job_id,
    j.company,
    j.job_title,
    lsa.user_id,
        CASE
            WHEN (lsa.event_type = 'JOB_SAVED'::text) THEN 'SAVED'::text
            WHEN (lsa.event_type = 'JOB_UNSAVED'::text) THEN 'UNSAVED'::text
            ELSE 'UNKNOWN'::text
        END AS save_status,
    lsa.event_at AS last_save_action_at
   FROM (public.jobs j
     LEFT JOIN latest_save_action lsa ON ((lsa.job_id = j.job_id)));


--
-- Name: jobs_job_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.jobs ALTER COLUMN job_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.jobs_job_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: resumes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.resumes (
    resume_id bigint NOT NULL,
    user_id bigint NOT NULL,
    resume_name text NOT NULL,
    version integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: resumes_resume_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.resumes ALTER COLUMN resume_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.resumes_resume_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    user_id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: users_user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.users ALTER COLUMN user_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.users_user_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: application_events application_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application_events
    ADD CONSTRAINT application_events_pkey PRIMARY KEY (event_id);


--
-- Name: applications applications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT applications_pkey PRIMARY KEY (application_id);


--
-- Name: job_events job_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_events
    ADD CONSTRAINT job_events_pkey PRIMARY KEY (job_event_id);


--
-- Name: jobs jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_pkey PRIMARY KEY (job_id);


--
-- Name: resumes resumes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resumes
    ADD CONSTRAINT resumes_pkey PRIMARY KEY (resume_id);


--
-- Name: applications uq_applications_user_job; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT uq_applications_user_job UNIQUE (user_id, job_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);


--
-- Name: uq_job_events_job_found; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_job_events_job_found ON public.job_events USING btree (user_id, job_id) WHERE (event_type = 'JOB_FOUND'::text);


--
-- Name: applications fk_applications_job; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT fk_applications_job FOREIGN KEY (job_id) REFERENCES public.jobs(job_id);


--
-- Name: applications fk_applications_resume; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT fk_applications_resume FOREIGN KEY (resume_id) REFERENCES public.resumes(resume_id);


--
-- Name: applications fk_applications_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT fk_applications_user FOREIGN KEY (user_id) REFERENCES public.users(user_id);


--
-- Name: application_events fk_events_application; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application_events
    ADD CONSTRAINT fk_events_application FOREIGN KEY (application_id) REFERENCES public.applications(application_id);


--
-- Name: job_events fk_job_events_job; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_events
    ADD CONSTRAINT fk_job_events_job FOREIGN KEY (job_id) REFERENCES public.jobs(job_id);


--
-- Name: job_events fk_job_events_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_events
    ADD CONSTRAINT fk_job_events_user FOREIGN KEY (user_id) REFERENCES public.users(user_id);


--
-- Name: resumes fk_resumes_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resumes
    ADD CONSTRAINT fk_resumes_user FOREIGN KEY (user_id) REFERENCES public.users(user_id);


--
-- PostgreSQL database dump complete
--

\unrestrict LPhhWF3gDqUNkc7ra7YnwWM2QObPvOplRAfibiJK0IFN1ieFWUjZkhXVMA5TE7K

"""Durable PostgreSQL jobs; completion is fenced by a renewable lease token."""
import os
from uuid import uuid4
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import configuration as cfg

SCHEMA = """
CREATE TABLE IF NOT EXISTS da_jobs (
 id uuid PRIMARY KEY, principal text NOT NULL, request jsonb NOT NULL,
 status text NOT NULL DEFAULT 'queued', created_at timestamptz NOT NULL DEFAULT now(),
 started_at timestamptz, finished_at timestamptz, lease_until timestamptz,
 lease_token uuid, cancel_requested boolean NOT NULL DEFAULT false,
 result jsonb, error text
);
CREATE INDEX IF NOT EXISTS da_jobs_queue ON da_jobs(status, created_at);
"""

def connect():
    return psycopg.connect(os.environ[cfg.QUEUE_DSN_ENV], row_factory=dict_row, connect_timeout=10)

def initialize():
    with connect() as conn:
        conn.execute(SCHEMA)

def submit(principal, request):
    job_id = str(uuid4())
    with connect() as conn:
        # Bound admitted work globally; internal API should also be rate-limited.
        conn.execute("SELECT pg_advisory_xact_lock(723194)")
        count = conn.execute("SELECT count(*) AS n FROM da_jobs WHERE status IN ('queued','running')").fetchone()["n"]
        if count >= 100:
            raise ValueError("Queue capacity reached.")
        conn.execute("INSERT INTO da_jobs(id,principal,request) VALUES (%s,%s,%s)",
                     (job_id, principal, Jsonb(request)))
    return job_id

def get(job_id, principal):
    with connect() as conn:
        return conn.execute("SELECT * FROM da_jobs WHERE id=%s AND principal=%s", (job_id, principal)).fetchone()

def claim():
    lease = str(uuid4())
    with connect() as conn:
        # Expired jobs fail instead of being executed twice against a changing DB snapshot.
        conn.execute("UPDATE da_jobs SET status='failed', error='Worker lease expired', finished_at=now() "
                     "WHERE status='running' AND lease_until < now()")
        job = conn.execute("SELECT * FROM da_jobs WHERE status='queued' AND NOT cancel_requested "
                           "ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1").fetchone()
        if not job:
            return None
        conn.execute("UPDATE da_jobs SET status='running',started_at=now(),lease_until=now()+interval '30 seconds',"
                     "lease_token=%s WHERE id=%s", (lease, job["id"]))
        return {**job, "lease_token": lease}

def heartbeat(job):
    with connect() as conn:
        row = conn.execute("UPDATE da_jobs SET lease_until=now()+interval '30 seconds' WHERE id=%s "
            "AND lease_token=%s AND status='running' AND lease_until>=now() AND NOT cancel_requested RETURNING id",
            (job["id"], job["lease_token"])).fetchone()
        return bool(row)

def finish(job, result=None, error=None):
    with connect() as conn:
        return conn.execute("UPDATE da_jobs SET status=CASE WHEN cancel_requested THEN 'cancelled' "
            "WHEN %s THEN 'failed' ELSE 'completed' END, result=CASE WHEN cancel_requested THEN NULL ELSE %s::jsonb END,error=%s,finished_at=now() "
            "WHERE id=%s AND lease_token=%s AND status='running' RETURNING id",
            (error is not None, Jsonb(result) if result is not None else None, error, job["id"], job["lease_token"])).fetchone()

def cancel(job_id, principal):
    with connect() as conn:
        return conn.execute("UPDATE da_jobs SET cancel_requested=true,finished_at=CASE WHEN status='queued' THEN now() ELSE finished_at END,"
            "status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END "
            "WHERE id=%s AND principal=%s AND status IN ('queued','running') RETURNING id", (job_id, principal)).fetchone()

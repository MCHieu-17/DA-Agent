"""Opt in with DA_TEST_POSTGRES_DSN pointing only to a disposable test database."""
import os
from uuid import uuid4
import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DA_TEST_POSTGRES_DSN"), reason="Disposable PostgreSQL not configured")

@pytest.fixture
def database(monkeypatch):
    import psycopg
    schema = "test_" + uuid4().hex
    dsn = os.environ["DA_TEST_POSTGRES_DSN"]
    monkeypatch.setenv("DA_REPORTING_TEST_DSN", dsn)
    from psycopg import sql
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        conn.execute(sql.SQL("CREATE TABLE {}.sales(city text, amount integer, secret text)").format(sql.Identifier(schema)))
        conn.execute(sql.SQL("INSERT INTO {}.sales VALUES ('A',10,'hidden'),('B',20,'private')").format(sql.Identifier(schema)))
    yield {"dsn_env": "DA_REPORTING_TEST_DSN", "schema": schema, "table": "sales", "columns": ["city", "amount"]}
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))

def test_postgres_projection_aggregation_and_snapshot(database, tmp_path):
    from graph.postgres import analysis_session, execute, profile
    import psycopg
    from psycopg import sql
    from graph.runtime import read_result
    expected = {"type": "scalar", "columns": []}
    with analysis_session():
        assert profile(database, "dataset_1")["column_count"] == 2
        with psycopg.connect(os.environ["DA_TEST_POSTGRES_DSN"], autocommit=True) as conn:
            conn.execute(sql.SQL("INSERT INTO {}.sales VALUES ('C',99,'secret')").format(sql.Identifier(database["schema"])))
        execute("SELECT SUM(amount) FROM dataset_1", {"dataset_1": database}, tmp_path, expected)
        assert read_result(tmp_path, expected)["value"] == 30
        with pytest.raises(Exception):
            execute("SELECT secret FROM dataset_1", {"dataset_1": database}, tmp_path, expected)
        # Savepoint restores the transaction after an invalid column.
        execute("SELECT SUM(amount) FROM dataset_1", {"dataset_1": database}, tmp_path, expected)
        assert read_result(tmp_path, expected)["value"] == 30

def test_postgres_table(database, tmp_path):
    from graph.postgres import analysis_session, execute
    from graph.runtime import read_result
    expected = {"type": "table", "columns": ["city", "total"]}
    with analysis_session():
        execute("SELECT city, SUM(amount) AS total FROM dataset_1 GROUP BY city ORDER BY city",
                {"dataset_1": database}, tmp_path, expected)
    assert read_result(tmp_path, expected)["preview"] == [{"city": "A", "total": 10}, {"city": "B", "total": 20}]

def test_postgres_null_first_batch_and_exact_decimal(database, tmp_path):
    import psycopg
    from psycopg import sql
    from graph.postgres import analysis_session, execute
    import pyarrow.parquet as pq
    with psycopg.connect(os.environ["DA_TEST_POSTGRES_DSN"], autocommit=True) as conn:
        conn.execute(sql.SQL("INSERT INTO {}.sales SELECT 'N', NULL, '' FROM generate_series(1,10001)").format(sql.Identifier(database["schema"])))
    with analysis_session():
        execute("SELECT city, amount FROM dataset_1 ORDER BY amount NULLS FIRST", {"dataset_1": database}, tmp_path,
                {"type": "table", "columns": ["city", "amount"]})
        assert pq.read_table(tmp_path / "result.parquet")["amount"].to_pylist()[-2:] == [10, 20]

def test_queue_auth_lease_and_cancel(monkeypatch):
    from service import queue
    monkeypatch.setenv("DA_QUEUE_DSN", os.environ["DA_TEST_POSTGRES_DSN"])
    queue.initialize()
    user = "user-" + uuid4().hex
    job_id = queue.submit(user, {"messages": [], "source_refs": []})
    assert queue.get(job_id, "other") is None
    job = queue.claim()
    assert str(job["id"]) == job_id
    assert queue.heartbeat(job)
    stale = {**job, "lease_token": str(uuid4())}
    assert queue.finish(stale, {"final_answer": "wrong"}) is None
    queue.cancel(job_id, user)
    assert not queue.heartbeat(job)
    queue.finish(job, error="cancelled")
    assert queue.get(job_id, user)["status"] == "cancelled"

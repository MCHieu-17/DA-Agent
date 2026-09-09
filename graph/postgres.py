"""Trusted query broker. Credentials never enter prompts or execution containers."""
from contextlib import contextmanager
from contextvars import ContextVar
import os
import time
import pyarrow as pa
import pyarrow.parquet as pq
from sqlglot import exp
from graph.sql_policy import validate_sql
import configuration as cfg

def arrow_type(column):
    types = {16: pa.bool_(), 20: pa.int64(), 21: pa.int16(), 23: pa.int32(),
             700: pa.float32(), 701: pa.float64(), 1082: pa.date32(),
             1114: pa.timestamp("us"), 1184: pa.timestamp("us", tz="UTC"),
             1083: pa.time64("us"), 17: pa.binary()}
    # Unbounded NUMERIC is encoded as exact decimal text, never silently rounded to float.
    return types.get(column.type_code, pa.string())

_session = ContextVar("postgres_session", default=None)

@contextmanager
def analysis_session():
    session = {}
    token = _session.set(session)
    try:
        yield
    finally:
        for connection in session.values():
            try:
                connection.rollback()
            finally:
                connection.close()
        _session.reset(token)

def connection(spec):
    import psycopg
    session = _session.get()
    if session is None:
        raise RuntimeError("PostgreSQL analysis requires analysis_session().")
    key = spec["dsn_env"]
    if key not in session:
        conn = psycopg.connect(os.environ[key], connect_timeout=10, autocommit=True)
        conn.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '300s'")
        conn.execute("SET LOCAL lock_timeout = '5s'")
        conn.execute("SET LOCAL idle_in_transaction_session_timeout = '900s'")
        conn.execute("SET LOCAL search_path = pg_catalog")
        conn.execute("SET LOCAL work_mem = '64MB'")
        conn.execute("SET LOCAL max_parallel_workers_per_gather = 2")
        session[key] = conn
    return session[key]

def profile(spec, dataset_id):
    from psycopg import sql
    conn = connection(spec)
    query = sql.SQL("SELECT {} FROM {} LIMIT 0").format(
        sql.SQL(",").join(map(sql.Identifier, spec["columns"])), sql.Identifier(spec["schema"], spec["table"]))
    cursor = conn.execute(query)
    return {"dataset_id": dataset_id, "kind": "postgres", "row_count": None,
            "column_count": len(spec["columns"]), "read_options": {}, "path": "",
            "broker_source": spec, "columns": [{"name": c.name, "suggested_type": "database",
                "postgres_type_oid": c.type_code, "null_count": None} for c in cursor.description],
            "warnings": ["Catalog only; exact statistics require a query."], "sample": {"scope": "none"}}

def execute(sql_text, sources, directory, expected):
    validate_sql(sql_text, sources, "postgres")
    conn = connection(next(iter(sources.values())))
    # A rejected query rolls back only its savepoint, preserving the run snapshot.
    with conn.transaction():
        return _execute(sql_text, sources, directory, expected)

def _execute(sql_text, sources, directory, expected):
    tree = validate_sql(sql_text, sources, "postgres")
    connections = {spec["dsn_env"] for spec in sources.values()}
    if len(connections) != 1:
        raise ValueError("A PostgreSQL step must use one connection; join extracted tables with DuckDB.")
    from sqlglot.optimizer.scope import traverse_scope
    for scope in traverse_scope(tree):
        for table in list(scope.sources.values()):
            if not isinstance(table, exp.Table):
                continue
            spec = sources[table.name]
            alias = table.alias_or_name
            projection = exp.select(*[exp.column(c, quoted=True) for c in spec["columns"]]).from_(
                exp.Table(this=exp.to_identifier(spec["table"], quoted=True), db=exp.to_identifier(spec["schema"], quoted=True)))
            table.replace(projection.subquery(exp.to_identifier(alias, quoted=True)))
    conn = connection(next(iter(sources.values())))
    writer = None
    from uuid import uuid4
    try:
        with conn.cursor(name="da_" + uuid4().hex) as cursor:
            cursor.execute(tree.sql(dialect="postgres"))
            names = [col.name for col in cursor.description]
            if expected["type"] == "scalar":
                rows = cursor.fetchmany(2)
                if len(rows) != 1 or len(names) != 1:
                    raise ValueError("Scalar query must return exactly one row and column.")
                from graph.runtime import StepRuntime
                value = rows[0][0]
                from decimal import Decimal
                StepRuntime({}, directory).save_scalar(str(value) if isinstance(value, Decimal) else value)
                return
            schema = pa.schema([(column.name, arrow_type(column)) for column in cursor.description])
            while rows := cursor.fetchmany(10_000):
                records = [{field.name: (str(value) if value is not None and pa.types.is_string(field.type) else value)
                            for field, value in zip(schema, row)} for row in rows]
                table = pa.Table.from_pylist(records, schema=schema)
                if writer is None:
                    writer = pq.ParquetWriter(directory / "result.parquet", schema)
                writer.write_table(table)
                if (directory / "result.parquet").stat().st_size > cfg.SANDBOX_DISK_MB * 1024 ** 2:
                    raise ValueError("PostgreSQL result exceeds output quota.")
            if writer is None:
                pq.write_table(pa.Table.from_batches([], schema=schema), directory / "result.parquet")
        import json
        (directory / "result.json").write_text(json.dumps({"type": "table", "file": "result.parquet"}), encoding="utf-8")
    except Exception:
        conn.cancel()
        raise
    finally:
        if writer:
            writer.close()

"""Reap expired jobs and their private containers/volumes; retain outputs for seven days."""
import shutil
from pathlib import Path
import configuration as cfg
from service.queue import connect
from graph.executors import cleanup_job

def sweep():
    with connect() as conn:
        conn.execute("UPDATE da_jobs SET status='failed',error='Worker lease expired',finished_at=now() "
                     "WHERE status='running' AND lease_until < now()")
        jobs = conn.execute("SELECT id,result, finished_at < now()-interval '7 days' AS expired FROM da_jobs "
                            "WHERE status IN ('completed','failed','cancelled')").fetchall()
    root = Path(cfg.ARTIFACTS_DIR).resolve()
    for job in jobs:
        cleanup_job(job["id"])
        if job["expired"]:
            # Only unlink explicitly recorded artifacts; never recurse through user-provided paths.
            for name in (job.get("result") or {}).get("artifact_paths", {}).values():
                file = Path(name)
                if file.resolve().is_relative_to(root) and not file.is_symlink():
                    file.unlink(missing_ok=True)

if __name__ == "__main__":
    sweep()

"""Run with python -m service.worker. Only this service controls the container runtime."""
import json
import multiprocessing
import os
from pathlib import Path
import time
from uuid import uuid4
import configuration as cfg
from service import queue

def perform(job, result_path):
    os.environ["DA_JOB_ID"] = str(job["id"])
    from langchain_core.messages import HumanMessage, AIMessage
    from main import app
    from graph.postgres import analysis_session
    request = job["request"]
    history = [HumanMessage(content=m["content"]) if m["role"] == "human" else AIMessage(content=m["content"])
               for m in request.get("history", [])]
    messages = [*history, *[HumanMessage(content=m["content"]) for m in request["messages"]]]
    with analysis_session():
        state = app.invoke({"messages": messages, "source_refs": request["source_refs"], "principal": job["principal"],
                            "analysis_memory": request.get("analysis_memory", "")})
    paths = {str(uuid4()): path for path in state.get("artifacts", [])}
    answer = state.get("final_answer") or ""
    artifacts = []
    for ref, path in paths.items():
        url = f"/runs/{job['id']}/artifacts/{ref}"
        answer = answer.replace(path, url)
        artifacts.append({"id": ref, "name": Path(path).name, "url": url})
    # Internal exceptions stay in worker diagnostics, not in public replies.
    if state["workflow_status"] == "failed":
        answer = "Phân tích chưa hoàn tất. Vui lòng liên hệ quản trị viên với mã lượt chạy."
    result = {"final_answer": answer, "workflow_status": state["workflow_status"],
              "analysis_request": state.get("analysis_request", ""),
              "metrics": state.get("metrics", []), "artifacts": artifacts, "artifact_paths": paths,
              "conversation": [{"role": m.type, "content": m.content} for m in messages[-5:]] + [{"role": "ai", "content": answer}]}
    Path(result_path).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")

def stop_tree(process):
    import psutil
    try:
        parent = psutil.Process(process.pid)
        for child in parent.children(recursive=True):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        parent.kill()
    except psutil.NoSuchProcess:
        pass
    process.join(timeout=10)

def run_job(job):
    root = Path(cfg.ARTIFACTS_DIR).resolve() / "jobs" / str(job["id"])
    root.mkdir(parents=True, exist_ok=True)
    path = root / "completion.json"
    process = multiprocessing.get_context("spawn").Process(target=perform, args=(job, str(path)))
    process.start()
    deadline = time.monotonic() + cfg.RUN_TIMEOUT_SECONDS
    try:
        while process.is_alive():
            process.join(timeout=5)
            if time.monotonic() >= deadline or not queue.heartbeat(job):
                stop_tree(process)
                queue.finish(job, error="Run cancelled or deadline exceeded")
                return
        if process.exitcode or not path.exists():
            queue.finish(job, error="Analysis worker failed")
        else:
            queue.finish(job, json.loads(path.read_text(encoding="utf-8")))
    finally:
        if process.is_alive():
            stop_tree(process)
        from graph.executors import cleanup_job
        cleanup_job(job["id"])

def main():
    from graph.executors import preflight
    preflight()
    from service.janitor import sweep
    sweep()
    next_sweep = time.monotonic() + 60
    while True:
        if time.monotonic() >= next_sweep:
            sweep()
            next_sweep = time.monotonic() + 60
        job = queue.claim()
        if job:
            run_job(job)
        else:
            time.sleep(1)

if __name__ == "__main__":
    main()

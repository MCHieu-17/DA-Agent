"""Production input/output boundary. Never expose arbitrary graph state or file paths."""
import hashlib
import hmac
import json
from pathlib import Path
from uuid import UUID
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
import configuration as cfg
from graph.sources import authorized_sources
from service import queue

app = FastAPI(title="DA Agent internal API")
bearer = HTTPBearer()

def principal(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    digest = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    users = json.loads(Path(cfg.AUTH_REGISTRY_PATH).read_text(encoding="utf-8"))
    for name, spec in users.items():
        if hmac.compare_digest(digest, spec["token_sha256"]):
            return name
    raise HTTPException(401, "Invalid credentials")

class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1, max_length=8000)

class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: list[Message] = Field(min_length=1, max_length=6)
    source_refs: list[str] = Field(default_factory=list, max_length=10)
    previous_job_id: UUID | None = None

@app.post("/runs", status_code=202)
def submit(request: Request, user=Depends(principal)):
    try:
        authorized_sources({"source_refs": request.source_refs, "principal": user})
    except (PermissionError, ValueError):
        raise HTTPException(403, "Invalid or unauthorized source")
    payload = request.model_dump(mode="json")
    if request.previous_job_id:
        previous = queue.get(request.previous_job_id, user)
        if not previous or previous["status"] != "completed":
            raise HTTPException(404, "Completed previous run not found")
        # History comes from server-held messages/results; clients cannot forge AI replies.
        payload["history"] = (previous.get("result") or {}).get("conversation", [])[-5:]
        payload["analysis_memory"] = (previous.get("result") or {}).get("analysis_request", "")
        if not payload["source_refs"]:
            payload["source_refs"] = previous["request"]["source_refs"]
        try:
            authorized_sources({"source_refs": payload["source_refs"], "principal": user})
        except (PermissionError, ValueError):
            raise HTTPException(403, "Source permission changed")
    try:
        return {"id": queue.submit(user, payload), "status": "queued"}
    except ValueError:
        raise HTTPException(429, "Queue capacity reached")

@app.get("/runs/{job_id}")
def get_run(job_id: UUID, user=Depends(principal)):
    job = queue.get(job_id, user)
    if not job:
        raise HTTPException(404, "Run not found")
    result = job.get("result") or {}
    return {"id": str(job_id), "status": job["status"], "error": job["error"],
            **{k: result[k] for k in ("final_answer", "workflow_status", "metrics", "artifacts") if k in result}}

@app.delete("/runs/{job_id}", status_code=202)
def cancel_run(job_id: UUID, user=Depends(principal)):
    if not queue.cancel(job_id, user):
        raise HTTPException(404, "Active run not found")
    return {"status": "cancellation_requested"}

@app.get("/runs/{job_id}/artifacts/{artifact_id}")
def artifact(job_id: UUID, artifact_id: UUID, user=Depends(principal)):
    job = queue.get(job_id, user)
    if not job or job["status"] != "completed":
        raise HTTPException(404, "Artifact not found")
    result = job.get("result") or {}
    path = result.get("artifact_paths", {}).get(str(artifact_id))
    if result.get("workflow_status") != "success" or not path:
        raise HTTPException(404, "Artifact not found")
    file = Path(path)
    if not file.is_file() or file.is_symlink() or not file.resolve().is_relative_to(Path(cfg.ARTIFACTS_DIR).resolve()):
        raise HTTPException(404, "Artifact unavailable")
    return FileResponse(file, filename=file.name, media_type="application/octet-stream",
                        headers={"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox; default-src 'none'"})

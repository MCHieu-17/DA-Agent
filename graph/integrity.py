"""Hash sealed evidence without loading untrusted tables into the agent process."""
import hashlib
from pathlib import Path

def verify_files(result):
    root = Path(result["directory"]).resolve()
    checks = {str(root / "result.json"): result["manifest_hash"], **result.get("artifact_hashes", {})}
    if result.get("path"):
        checks[result["path"]] = result["content_hash"]
    for name, expected in checks.items():
        path = Path(name)
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("Evidence path escaped the attempt.")
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            raise ValueError("Output changed after execution.")

import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from blackbox.models.claim import Claim
from blackbox.models.error_loop import ErrorLoop
from blackbox.models.evidence import EvidenceSet
from blackbox.models.score import LieScore


class RunMetadata(BaseModel):
    run_id: str
    created_at: datetime
    agent_type: str = "claude-code"
    task: str | None = None
    event_count: int = 0
    status: Literal["recorded", "analyzed", "reported"] = "recorded"


class RunStore:
    def __init__(self, base_dir: Path | None = None) -> None:
        if base_dir is None:
            base_dir = Path.cwd() / ".blackbox" / "runs"
        self.base_dir = base_dir

    _RUN_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')

    def _run_path(self, run_id: str) -> Path:
        if not self._RUN_ID_PATTERN.match(run_id):
            raise ValueError(f"Invalid run_id: {run_id}")
        return self.base_dir / run_id

    def _atomic_write_json(self, filepath: Path, data: dict) -> None:
        tmp_path = filepath.with_suffix(
            f".{filepath.stem}_{uuid.uuid4().hex}.tmp"
        )
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, filepath)
        except OSError:
            if tmp_path.exists():
                tmp_path.unlink()
            raise

    def _read_json(self, filepath: Path) -> dict:
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        with open(filepath) as f:
            return json.load(f)

    def create_run(self, metadata: RunMetadata) -> Path:
        run_dir = self._run_path(metadata.run_id)
        run_dir.mkdir(parents=True, exist_ok=False)
        meta_path = run_dir / "metadata.json"
        self._atomic_write_json(meta_path, metadata.model_dump())
        events_path = run_dir / "events.jsonl"
        events_path.touch()
        return run_dir

    def load_metadata(self, run_id: str) -> dict:
        run_dir = self._run_path(run_id)
        if not run_dir.exists():
            raise FileNotFoundError(f"No run at {run_dir}")
        return self._read_json(run_dir / "metadata.json")

    def append_event(self, run_id: str, event: dict) -> None:
        run_dir = self._run_path(run_id)
        events_path = run_dir / "events.jsonl"
        with open(events_path, "a") as f:
            f.write(json.dumps(event, default=str) + "\n")
        meta = self.load_metadata(run_id)
        meta["event_count"] = meta.get("event_count", 0) + 1
        self._atomic_write_json(run_dir / "metadata.json", meta)

    def list_runs(self) -> list[dict]:
        if not self.base_dir.exists():
            return []
        runs = []
        for entry in self.base_dir.iterdir():
            if not entry.is_dir():
                continue
            meta_path = entry / "metadata.json"
            if not meta_path.exists():
                continue
            try:
                meta = self._read_json(meta_path)
                runs.append(meta)
            except (json.JSONDecodeError, FileNotFoundError):
                continue
        runs.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return runs

    def run_exists(self, run_id: str) -> bool:
        return self._run_path(run_id).exists()

    def save_claims(self, run_id: str, claims: list[Claim]) -> Path:
        run_dir = self._run_path(run_id)
        filepath = run_dir / "claims.json"
        self._atomic_write_json(filepath, [c.model_dump() for c in claims])
        return filepath

    def load_claims(self, run_id: str) -> list[dict]:
        run_dir = self._run_path(run_id)
        return self._read_json(run_dir / "claims.json")

    def save_evidence(self, run_id: str, evidence: EvidenceSet) -> Path:
        run_dir = self._run_path(run_id)
        filepath = run_dir / "evidence.json"
        self._atomic_write_json(filepath, evidence.model_dump())
        return filepath

    def load_evidence(self, run_id: str) -> dict:
        run_dir = self._run_path(run_id)
        return self._read_json(run_dir / "evidence.json")

    def save_score(self, run_id: str, score: LieScore) -> Path:
        run_dir = self._run_path(run_id)
        filepath = run_dir / "score.json"
        self._atomic_write_json(filepath, score.model_dump())
        return filepath

    def load_score(self, run_id: str) -> dict:
        run_dir = self._run_path(run_id)
        return self._read_json(run_dir / "score.json")

    def save_error_loops(self, run_id: str, loops: list[ErrorLoop]) -> Path:
        run_dir = self._run_path(run_id)
        filepath = run_dir / "error_loops.json"
        self._atomic_write_json(filepath, [l.model_dump() for l in loops])
        return filepath

    def load_error_loops(self, run_id: str) -> list[dict]:
        run_dir = self._run_path(run_id)
        return self._read_json(run_dir / "error_loops.json")

    def save_report(self, run_id: str, report: dict) -> Path:
        run_dir = self._run_path(run_id)
        filepath = run_dir / "report.json"
        self._atomic_write_json(filepath, report)
        return filepath

    def load_report(self, run_id: str) -> dict:
        run_dir = self._run_path(run_id)
        return self._read_json(run_dir / "report.json")

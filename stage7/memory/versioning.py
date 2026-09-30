from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import tempfile

from stage4.memory.memory_store import MemoryStore
from stage4.memory.models import MemoryRecord

from .schema import MemoryCandidate


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MemoryVersion:
    claim_id: str
    version: int
    action: str  # created | reinforced | updated | conflict
    content: str
    record_id: str
    candidate_id: str
    source_session_id: str
    timestamp: str = field(default_factory=_now_iso)
    previous_content: str | None = None
    evidence: list[dict[str, Any]] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ClaimState:
    claim_id: str
    record_id: str
    current_version: int
    content: str
    memory_type: str
    status: str = "active"
    first_seen_at: str = field(default_factory=_now_iso)
    last_seen_at: str = field(default_factory=_now_iso)
    evidence_count: int = 0
    source_sessions: list[str] = field(default_factory=list)
    versions: list[int] = field(default_factory=lambda: [1])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClaimState":
        return cls(**data)


class MemoryVersionStore:
    """稳定 claim + 历史 version；claim_id 默认复用 Durable Memory record_id。"""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.claim_dir = self.root / "claims"
        self.version_dir = self.root / "versions"
        self.conflict_dir = self.root / "conflicts"
        for path in (self.claim_dir, self.version_dir, self.conflict_dir):
            path.mkdir(parents=True, exist_ok=True)

    def _claim_path(self, claim_id: str) -> Path:
        return self.claim_dir / f"{claim_id}.json"

    def _version_path(self, claim_id: str) -> Path:
        return self.version_dir / f"{claim_id}.jsonl"

    def load(self, claim_id: str) -> ClaimState | None:
        path = self._claim_path(claim_id)
        if not path.exists():
            return None
        return ClaimState.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, state: ClaimState) -> None:
        path = self._claim_path(state.claim_id)
        _atomic_json(path, state.to_dict())

    def append_version(self, version: MemoryVersion) -> None:
        with self._version_path(version.claim_id).open("a", encoding="utf-8") as f:
            f.write(json.dumps(version.to_dict(), ensure_ascii=False, default=str) + "\n")

    def append_conflict(self, conflict: dict[str, Any]) -> None:
        path = self.conflict_dir / f"{conflict['claim_id']}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(conflict, ensure_ascii=False, default=str) + "\n")

    def versions(self, claim_id: str) -> list[MemoryVersion]:
        path = self._version_path(claim_id)
        if not path.exists():
            return []
        return [MemoryVersion(**json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def inspect(self, claim_id: str) -> dict[str, Any] | None:
        state = self.load(claim_id)
        if not state:
            return None
        return {
            "claim": state.to_dict(),
            "versions": [v.to_dict() for v in self.versions(claim_id)],
        }

    def apply(
        self,
        memory: MemoryStore,
        candidate: MemoryCandidate,
        *,
        action: str,
        matched_record_id: str | None,
        reason: str,
    ) -> tuple[str, int, ClaimState]:
        if action == "new":
            record = memory.capture_fact(
                session_id=candidate.source_session_id,
                content=candidate.content,
                confidence=candidate.confidence,
                importance=candidate.importance,
                memory_type=candidate.memory_type,
                metadata={
                    **candidate.metadata,
                    "stage7_candidate_id": candidate.candidate_id,
                    "claim_version": 1,
                    "claim_status": "active",
                    "evidence": [e.to_dict() for e in candidate.evidence],
                    "source_sessions": [candidate.source_session_id],
                    "evidence_count": len(candidate.evidence),
                    "consolidation_stage": "stage7-b",
                },
            )
            state = ClaimState(
                claim_id=record.record_id,
                record_id=record.record_id,
                current_version=1,
                content=record.content,
                memory_type=record.memory_type,
                evidence_count=len(candidate.evidence),
                source_sessions=[candidate.source_session_id],
            )
            self.save(state)
            self.append_version(MemoryVersion(
                claim_id=state.claim_id,
                version=1,
                action="created",
                content=record.content,
                record_id=record.record_id,
                candidate_id=candidate.candidate_id,
                source_session_id=candidate.source_session_id,
                evidence=[e.to_dict() for e in candidate.evidence],
                reason="new stable claim",
            ))
            return record.record_id, 1, state

        if not matched_record_id:
            raise ValueError(f"action {action} requires matched_record_id")
        record = memory._records.get(matched_record_id)
        if record is None:
            raise KeyError(f"memory record not found: {matched_record_id}")

        state = self.load(matched_record_id)
        if state is None:
            state = self._bootstrap_state(memory, record)

        now = _now_iso()
        existing_sessions = list(dict.fromkeys([*state.source_sessions, candidate.source_session_id]))
        existing_evidence = list((record.metadata or {}).get("evidence") or [])
        incoming_evidence = [e.to_dict() for e in candidate.evidence]
        merged_evidence = _merge_evidence(existing_evidence, incoming_evidence)
        evidence_count = len(merged_evidence)

        if action == "conflict":
            self.append_conflict({
                "claim_id": state.claim_id,
                "record_id": record.record_id,
                "candidate_id": candidate.candidate_id,
                "source_session_id": candidate.source_session_id,
                "timestamp": now,
                "content": candidate.content,
                "current_content": record.content,
                "reason": reason,
            })
            return record.record_id, state.current_version, state

        previous = record.content
        if action == "reinforce":
            state.last_seen_at = now
            state.evidence_count = evidence_count
            state.source_sessions = existing_sessions
            record.confidence = max(record.confidence, candidate.confidence)
            record.importance = max(record.importance, candidate.importance)
            record.metadata = {
                **(record.metadata or {}),
                "evidence": merged_evidence,
                "evidence_count": evidence_count,
                "source_sessions": existing_sessions,
                "last_reinforced_at": now,
                "claim_version": state.current_version,
                "claim_status": state.status,
            }
            _persist_existing_record(memory, record)
            self.save(state)
            self.append_version(MemoryVersion(
                claim_id=state.claim_id,
                version=state.current_version,
                action="reinforced",
                content=record.content,
                record_id=record.record_id,
                candidate_id=candidate.candidate_id,
                source_session_id=candidate.source_session_id,
                evidence=incoming_evidence,
                reason=reason,
            ))
            return record.record_id, state.current_version, state

        if action == "update":
            state.current_version += 1
            state.content = candidate.content
            state.last_seen_at = now
            state.evidence_count = evidence_count
            state.source_sessions = existing_sessions
            state.versions.append(state.current_version)
            record.content = candidate.content
            record.confidence = max(record.confidence, candidate.confidence)
            record.importance = max(record.importance, candidate.importance)
            record.metadata = {
                **(record.metadata or {}),
                "evidence": merged_evidence,
                "evidence_count": evidence_count,
                "source_sessions": existing_sessions,
                "claim_version": state.current_version,
                "claim_status": state.status,
                "previous_content": previous,
                "last_updated_at": now,
            }
            _persist_existing_record(memory, record)
            memory.bm25.add(record.record_id, record.content)
            if memory.vector:
                memory.vector.add(record.record_id, record.content)
            self.save(state)
            self.append_version(MemoryVersion(
                claim_id=state.claim_id,
                version=state.current_version,
                action="updated",
                content=record.content,
                previous_content=previous,
                record_id=record.record_id,
                candidate_id=candidate.candidate_id,
                source_session_id=candidate.source_session_id,
                evidence=incoming_evidence,
                reason=reason,
            ))
            return record.record_id, state.current_version, state

        raise ValueError(f"unsupported action: {action}")

    def _bootstrap_state(self, memory: MemoryStore, record: MemoryRecord) -> ClaimState:
        meta = record.metadata or {}
        sessions = list(dict.fromkeys([str(record.session_id), *(meta.get("source_sessions") or [])]))
        version = int(meta.get("claim_version", 1) or 1)
        state = ClaimState(
            claim_id=record.record_id,
            record_id=record.record_id,
            current_version=version,
            content=record.content,
            memory_type=record.memory_type,
            status=meta.get("claim_status", record.status),
            evidence_count=int(meta.get("evidence_count", len(meta.get("evidence") or []) or 1)),
            source_sessions=sessions,
            versions=list(range(1, version + 1)),
        )
        self.save(state)
        existing_versions = self.versions(record.record_id)
        if not existing_versions:
            self.append_version(MemoryVersion(
                claim_id=record.record_id,
                version=version,
                action="created",
                content=record.content,
                record_id=record.record_id,
                candidate_id=str(meta.get("stage7_candidate_id") or "bootstrap"),
                source_session_id=record.session_id,
                evidence=list(meta.get("evidence") or []),
                reason="bootstrap existing Stage4 durable memory into Stage7-B version history",
            ))
        return state


def _merge_evidence(old: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    out = []
    for item in [*old, *new]:
        key = (
            str(item.get("source_id")),
            str(item.get("role")),
            str(item.get("content")),
            str(item.get("timestamp")),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(item))
    return out


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent), text=True)
    try:
        with open(fd, "w", encoding="utf-8", closefd=True) as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
            f.flush()
        Path(tmp_name).replace(path)
    finally:
        tmp = Path(tmp_name)
        if tmp.exists():
            tmp.unlink()


def _persist_existing_record(memory: MemoryStore, record: MemoryRecord) -> None:
    path = memory.durable_dir / f"{record.session_id}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"durable memory file missing: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    replaced = False
    payload = json.dumps(record.to_dict(), ensure_ascii=False, default=str)
    updated = []
    for line in lines:
        if not line.strip():
            continue
        data = json.loads(line)
        if data.get("record_id") == record.record_id:
            updated.append(payload)
            replaced = True
        else:
            updated.append(line)
    if not replaced:
        updated.append(payload)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("\n".join(updated) + "\n", encoding="utf-8")
    tmp.replace(path)
    memory._records[record.record_id] = record

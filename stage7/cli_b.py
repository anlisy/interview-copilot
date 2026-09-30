from __future__ import annotations

import argparse
import json
from pathlib import Path

from stage4.memory.memory_store import MemoryStore

from .memory.checkpoint import CheckpointStore
from .memory.consolidator_b import VersionedMemoryConsolidator
from .memory.extractor import RuleMemoryExtractor, ZhipuMemoryExtractor
from .memory.versioning import MemoryVersionStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage7-B cross-session evidence aggregation + memory versioning")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--root", default=".agent_memory")
    parser.add_argument("--mode", choices=["rule", "glm"], default="rule")
    parser.add_argument("--checkpoint-root", default=None)
    parser.add_argument("--version-root", default=None)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--inspect-claim", default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    memory = MemoryStore(args.root)
    versions = MemoryVersionStore(args.version_root or str(Path(args.root) / "versioned"))
    if args.inspect_claim:
        payload = versions.inspect(args.inspect_claim)
        print(json.dumps(payload or {"error": "claim not found"}, ensure_ascii=False, indent=2))
        return 0 if payload else 1

    checkpoints = CheckpointStore(args.checkpoint_root or str(Path(args.root) / "checkpoints"))
    consolidator = VersionedMemoryConsolidator(memory, checkpoints=checkpoints, versions=versions)
    extractor = RuleMemoryExtractor() if args.mode == "rule" else ZhipuMemoryExtractor()
    result = consolidator.consolidate(args.session_id, extractor, resume=not args.no_resume)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

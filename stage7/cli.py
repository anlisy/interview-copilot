from __future__ import annotations

import argparse
import json
from pathlib import Path

from stage4.memory.memory_store import MemoryStore

from .memory.checkpoint import CheckpointStore
from .memory.consolidator import MemoryConsolidator
from .memory.extractor import RuleMemoryExtractor, ZhipuMemoryExtractor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage7 memory consolidation")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--root", default=".agent_memory")
    parser.add_argument("--mode", choices=["rule", "glm"], default="rule")
    parser.add_argument("--checkpoint-root", default=None)
    parser.add_argument("--no-resume", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    memory = MemoryStore(args.root)
    checkpoints = CheckpointStore(args.checkpoint_root or str(Path(args.root) / "checkpoints"))
    consolidator = MemoryConsolidator(memory, checkpoints=checkpoints)
    extractor = RuleMemoryExtractor() if args.mode == "rule" else ZhipuMemoryExtractor()
    result = consolidator.consolidate(args.session_id, extractor, resume=not args.no_resume)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json

from stage3.agent_runtime.default_tools import build_default_registry
from stage3.agent_runtime.tool_executor import ToolExecutor
from stage3.agent_runtime.tool_models import ToolCallContext
from stage3.agent_runtime.tool_policy import ToolPolicy


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 3 Tool Policy/Registry smoke test")
    parser.add_argument("--agent", default="interviewer")
    parser.add_argument("--eval", action="store_true")
    parser.add_argument("--tool", default="nowcoder_search")
    parser.add_argument("--action", default=None)
    parser.add_argument("--execute", action="store_true", help="仅在 Registry 已绑定 handler 时执行；否则安全返回，不会伪造调用")
    args = parser.parse_args()

    registry = build_default_registry()
    print("🧰 Stage 3 Tool Runtime")
    print(f"Agent: {args.agent}")
    print(f"Eval: {args.eval}")
    ctx = ToolCallContext(agent=args.agent, eval_mode=args.eval, action=args.action)
    policy = ToolPolicy()
    visible = policy.visible_tools(registry, ctx)
    print(f"Visible tools: {', '.join(visible) or '<none>'}")

    decision = policy.decide(registry.get(args.tool), ctx)
    print(json.dumps({
        "tool": args.tool,
        "allowed": decision.allowed,
        "reason_code": decision.reason_code,
        "message": decision.message,
        "bound": registry.has_handler(args.tool),
    }, ensure_ascii=False, indent=2))

    if not args.execute:
        if decision.allowed and not registry.has_handler(args.tool):
            print("ℹ️ Tool 已获授权但当前默认 Registry 只保存 MCP 元数据，未绑定 handler；本次仅做权限验证，不执行 Tool。")
        return 0 if decision.allowed else 1

    result = ToolExecutor(registry, policy).call(
        args.tool,
        {"query": "Redis 缓存击穿", "limit": 3},
        ctx,
    )
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

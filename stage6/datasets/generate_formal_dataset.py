from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parent
DEFAULT_SPEC = ROOT / "decision_dataset_spec.json"
DEFAULT_OUT = ROOT / "formal"

SKILL_OPTIONS = {
    "question-design": "设计新的主问题，围绕简历、JD和项目事实生成面试题",
    "question-followup": "根据当前回答继续递进追问，深入原理、边界和异常场景",
    "question-intent": "判断当前题目重点考察的能力和面试意图",
    "answer-evaluation": "按照评分标准评价回答，识别能力覆盖和缺口",
    "interview-review": "复盘整场面试，总结薄弱项、能力覆盖和改进建议",
    "difficulty-control": "根据上一题表现控制下一题难度，避免难度突变",
}

SKILL_CASES = [
    ("question-design", "根据候选人的简历和JD设计一道 Redis 缓存相关主问题，要求能够继续深挖", ["主问题", "简历", "JD", "设计"]),
    ("question-design", "围绕候选人的 Kafka 项目重新设计一道项目深挖题，避免重复已经问过的问题", ["设计", "项目", "主问题", "避免重复"]),
    ("question-design", "候选人简历里有高并发登录系统，请生成一道能验证架构取舍的主问题", ["生成", "主问题", "架构"]),
    ("question-design", "根据候选人的 Meituan Arena 项目设计一道实验平台相关面试主问题", ["设计", "主问题", "项目"]),
    ("question-design", "基于当前候选人的 AI Agent 项目事实生成下一道新的主问题，而不是追问上一题", ["生成", "下一道", "主问题"]),
    ("question-followup", "根据候选人刚才对 Redis 击穿的回答继续追问互斥锁失效的边界条件", ["继续追问", "回答", "边界"]),
    ("question-followup", "候选人只讲了 Kafka 异步解耦，请继续追问消息重复消费和幂等处理", ["继续追问", "消息", "幂等"]),
    ("question-followup", "候选人解释了 Z-test，但没有说明 CUPED 前提，请继续追问验证实验有效性的依据", ["继续追问", "验证", "前提"]),
    ("question-followup", "根据候选人对 Agent Harness 的回答继续深挖成本失控和循环执行边界", ["继续", "深挖", "边界"]),
    ("question-followup", "候选人回答只覆盖了正常链路，请继续追问故障降级和恢复机制", ["继续追问", "故障", "恢复"]),
    ("question-intent", "判断题目主要是在考察 Redis 缓存击穿的原理还是故障治理策略", ["判断", "考察", "意图"]),
    ("question-intent", "判断两道 Kafka 题是否属于同一个能力考察意图，防止重复出题", ["判断", "同一个", "意图"]),
    ("question-intent", "识别当前问题考察的是实验设计原理、统计显著性还是工程实现", ["识别", "考察", "意图"]),
    ("question-intent", "判断当前 Agent 问题是在问 Tool 权限还是 Skill 选择", ["判断", "问题", "意图"]),
    ("question-intent", "识别当前问题是在考察容量规划还是故障恢复", ["识别", "考察", "问题"]),
    ("answer-evaluation", "按照正确性、完整性和工程可行性评价候选人的 Redis 回答", ["评分", "正确性", "工程"]),
    ("answer-evaluation", "根据评分标准评价候选人关于 Kafka 重复消费的回答并找出缺失点", ["评分", "缺失", "回答"]),
    ("answer-evaluation", "评估候选人的 CUPED 回答是否覆盖假设、收益和风险", ["评估", "假设", "收益", "风险"]),
    ("answer-evaluation", "判断候选人的 Harness 回答是否覆盖权限、状态和预算控制", ["评价", "权限", "状态", "预算"]),
    ("answer-evaluation", "按照 rubric 评价候选人是否真正解释了 Agent 与普通 Prompt 的区别", ["rubric", "评价", "区别"]),
    ("interview-review", "总结整场模拟面试，找出 Redis、Kafka 和系统设计方面的主要薄弱项", ["总结", "整场", "薄弱项"]),
    ("interview-review", "复盘候选人的 Agent 项目面试表现，归纳能力覆盖和缺失点", ["复盘", "能力覆盖", "缺失"]),
    ("interview-review", "汇总整场实验平台面试，输出统计学和工程实践方面的改进建议", ["汇总", "整场", "改进"]),
    ("interview-review", "根据整场答案和追问轨迹生成最终面试复盘", ["整场", "复盘", "追问轨迹"]),
    ("interview-review", "分析候选人的多次 Session，形成一份阶段性面试能力复盘", ["分析", "Session", "复盘"]),
    ("difficulty-control", "候选人上一题回答完整，下一题应适度提高 Redis 题目难度", ["难度", "下一题", "提高"]),
    ("difficulty-control", "候选人刚才回答不完整，下一题需要适当降低 Kafka 问题难度", ["难度", "下一题", "降低"]),
    ("difficulty-control", "根据候选人连续两题表现决定下一道系统设计题是否升级难度", ["表现", "下一道", "难度"]),
    ("difficulty-control", "当前候选人对 Agent Runtime 基础知识掌握较弱，控制下一题不要突然升高难度", ["掌握", "控制", "难度"]),
    ("difficulty-control", "候选人在故障恢复题上表现优秀，考虑提高下一题的约束复杂度", ["优秀", "提高", "复杂度"]),
]

TOOL_OPTIONS = {
    "local_rag": "检索本地项目和技术知识库",
    "memory_search": "检索候选人的长期记忆和历史 Session",
    "nowcoder_search": "检索外部真实面经",
    "no_tool": "不调用外部工具，直接基于当前上下文完成判断",
}

TOOL_CASES = [
    ("local_rag", "需要查询项目里的 Redis 缓存击穿设计和本地知识库记录", ["Redis", "项目", "本地", "知识库"]),
    ("local_rag", "需要查找候选人项目文档中关于 Kafka 重试策略的说明", ["项目", "文档", "本地"]),
    ("local_rag", "要确认候选人当前简历中描述的 MySQL 索引方案和技术细节", ["简历", "项目", "技术"]),
    ("local_rag", "需要检索本地 Agent Runtime 架构资料来回答当前设计问题", ["本地", "架构", "资料"]),
    ("local_rag", "查找本地知识库中关于 Redis 热点 Key 的治理方案", ["本地", "知识库", "Redis", "热点"]),
    ("local_rag", "检索本地项目材料中的实验平台 CUPED 实现细节", ["本地", "项目", "CUPED"]),
    ("local_rag", "根据当前项目上下文查询 Chroma 向量检索配置", ["本地", "项目", "向量", "配置"]),
    ("local_rag", "查询本地文档里的 Harness 状态机约束定义", ["本地", "文档", "Harness", "状态机"]),
    ("memory_search", "需要知道候选人过去几次 Session 是否已经讨论过 Redis 热点 Key", ["过去", "Session", "记忆"]),
    ("memory_search", "查找候选人历史回答中关于 Kafka 幂等方案的结论", ["历史", "回答", "幂等"]),
    ("memory_search", "需要回忆候选人在上次模拟面试中暴露出的薄弱项", ["上次", "历史", "薄弱项"]),
    ("memory_search", "确认候选人以前是否已经被问过 CUPED 的前提条件", ["以前", "已经问过", "历史"]),
    ("memory_search", "查询跨 Session 保存的候选人长期能力画像", ["跨 Session", "长期", "画像"]),
    ("memory_search", "查找候选人过去对 Agent Harness 的回答和追问结果", ["过去", "Harness", "追问"]),
    ("memory_search", "需要读取候选人之前的失败案例和已经修正过的方案", ["之前", "失败案例", "修正"]),
    ("memory_search", "确认某个 Redis 方案是不是候选人历史上已经使用过的实现", ["历史", "方案", "使用过"]),
    ("nowcoder_search", "正常面试出题时需要查询外部真实面经中的 Redis 高频题", ["真实面经", "外部", "Redis"]),
    ("nowcoder_search", "需要参考牛客等外部面经了解 Kafka 面试题的真实问法", ["外部", "面经", "Kafka"]),
    ("nowcoder_search", "想统计外部真实面试中 Agent Runtime 常见追问方式", ["外部", "真实面试", "追问"]),
    ("nowcoder_search", "正常模式下需要查找某公司真实面经来设计一道新题", ["真实面经", "公司", "新题"]),
    ("nowcoder_search", "需要了解外部候选人面试中常见的 CUPED 追问方式", ["外部", "面试", "CUPED"]),
    ("nowcoder_search", "需要查询互联网真实面经验证 Redis 限流问题的常见问法", ["真实面经", "Redis", "外部"]),
    ("nowcoder_search", "需要外部资料补充某个技术岗位近期常见的 Agent 问题", ["外部", "岗位", "Agent"]),
    ("no_tool", "当前上下文已经包含所有必要信息，只需要判断下一步动作", ["当前上下文", "只需要判断", "下一步"]),
    ("no_tool", "候选人的回答和评分标准都已经给出，不需要额外资料", ["评分标准", "不需要额外资料"]),
    ("no_tool", "只需要根据 Workflow State 判断是否可以进入下一状态", ["Workflow", "State", "判断"]),
    ("no_tool", "当前只是确定 Skill 候选是否满足触发条件，无需调用工具", ["Skill", "触发条件", "无需"]),
    ("no_tool", "当前问题只要求根据已经给出的回答判断是否需要继续追问", ["回答", "判断", "继续追问"]),
    ("no_tool", "只需要决定题目难度是否应该提高，所有依据都在当前上下文", ["难度", "当前上下文", "判断"]),
    ("no_tool", "当前只需根据已经给出的评分结果决定是否进入复盘阶段，不需要额外检索", ["评分结果", "复盘", "不需要检索"]),
]

INTENT_SAME = [
    ("Redis 缓存击穿的原理是什么？", "为什么 Redis 会发生缓存击穿？", ["原理", "为什么"]),
    ("Kafka 为什么会出现重复消费？", "消息重复消费通常是怎么产生的？", ["重复消费"]),
    ("为什么需要给写请求做幂等？", "幂等设计主要解决什么问题？", ["幂等"]),
    ("Redis 热点 Key 为什么会造成压力？", "热点 Key 对 Redis 集群有什么影响？", ["热点 Key", "压力"]),
    ("为什么登录接口需要限流？", "登录接口做限流主要是为了什么？", ["限流", "登录"]),
    ("为什么要使用 Redis 而不是直接查 MySQL？", "缓存相比直接查数据库的核心收益是什么？", ["缓存", "数据库"]),
    ("互斥锁解决缓存击穿的核心原理是什么？", "为什么互斥锁可以减少缓存击穿时的并发回源？", ["互斥锁", "击穿"]),
    ("CUPED 为什么可以降低实验方差？", "CUPED 降低实验结果方差的原因是什么？", ["CUPED", "方差"]),
    ("Z-test 为什么可以用于比例差异检验？", "比例实验为什么可以使用 Z 检验？", ["Z-test", "比例"]),
    ("为什么需要 QueryID？", "执行记录为什么需要唯一的 QueryID？", ["QueryID", "唯一"]),
    ("Agent Harness 为什么要限制工具权限？", "为什么 Agent 执行工具前需要做权限检查？", ["Harness", "权限"]),
    ("为什么 Agent 需要状态机？", "状态机主要解决 Agent 工作流中的什么问题？", ["状态机"]),
    ("为什么 Skill 需要渐进式加载？", "渐进式加载 Skill 的核心目的是什么？", ["Skill", "渐进式加载"]),
    ("为什么 Memory 不能等同于 Redis？", "Redis Session 和长期 Memory 的职责有什么区别？", ["Memory", "Redis"]),
    ("为什么需要 BM25 和向量检索融合？", "混合检索相比单一向量检索解决什么问题？", ["混合检索"]),
    ("为什么要使用 RRF 融合多个召回结果？", "RRF 的主要作用是什么？", ["RRF", "融合"]),
    ("为什么评测需要独立 Test Set？", "为什么不能用 Validation Set 直接报告最终效果？", ["Validation", "Test"]),
    ("为什么要记录 Agent Trace？", "轨迹记录对于故障回放有什么价值？", ["Trace", "回放"]),
    ("为什么 Tool Output 必须视为不可信数据？", "为什么外部工具返回内容不能直接修改系统规则？", ["Tool Output", "不可信"]),
    ("为什么 Eval 模式需要禁用 Ground Truth 工具？", "评测时为什么不能让 Agent 读取标准答案？", ["Eval", "Ground Truth"]),
    ("为什么要限制 Agent 最大追问次数？", "限制追问次数主要防止什么问题？", ["追问次数", "循环"]),
    ("为什么 Context Manager 需要 Token Budget？", "上下文为什么需要显式的 Token 预算？", ["Token Budget"]),
    ("为什么原始轨迹应该作为 Memory 的源真相？", "为什么长期 Memory 不应该直接取代原始轨迹？", ["原始轨迹", "源真相"]),
    ("为什么 Memory 需要记录时间和来源？", "长期记忆中的时间和来源字段有什么价值？", ["时间", "来源"]),
    ("为什么 Skill Candidate 不能立即成为 Active Skill？", "为什么自动发现的 Skill 需要先经过评估？", ["Skill Candidate", "评估"]),
]

INTENT_DIFF = [
    ("Redis 缓存击穿的原理是什么？", "Redis 缓存击穿以后如何限流和降级？", ["原理", "限流", "降级"]),
    ("Kafka 为什么会重复消费？", "Kafka 重复消费以后怎样做幂等处理？", ["原因", "幂等"]),
    ("Redis 热点 Key 为什么带来压力？", "热点 Key 应该怎样做治理？", ["原因", "治理"]),
    ("登录接口为什么需要限流？", "登录接口限流以后如何做降级？", ["为什么", "降级"]),
    ("为什么要使用 Redis 缓存？", "Redis 缓存应该如何设置过期时间？", ["收益", "配置"]),
    ("互斥锁解决击穿的原理是什么？", "互斥锁发生竞争时怎样做超时和降级？", ["原理", "竞争", "降级"]),
    ("CUPED 为什么能降低方差？", "CUPED 变量应该如何选择？", ["原理", "变量选择"]),
    ("Z-test 为什么适合比例实验？", "实验什么时候需要检查样本量和 MDE？", ["统计原理", "实验设计"]),
    ("为什么要生成 QueryID？", "QueryID 应该如何设计幂等性？", ["作用", "幂等设计"]),
    ("Harness 为什么要限制工具权限？", "工具执行超时以后应该如何恢复？", ["权限", "故障恢复"]),
    ("为什么 Agent 需要状态机？", "状态机状态迁移如何做版本校验？", ["必要性", "实现细节"]),
    ("Skill 为什么需要渐进式加载？", "Skill 的 references 应该如何组织？", ["加载策略", "目录设计"]),
    ("Memory 和 Redis 有什么区别？", "Context Manager 如何进行 Token 压缩？", ["职责区别", "压缩"]),
    ("为什么需要 BM25 + Vector？", "向量检索的 embedding 模型如何选择？", ["检索策略", "模型选择"]),
    ("为什么使用 RRF？", "RRF 的 k 参数如何配置？", ["原理", "参数配置"]),
    ("为什么需要独立 Test Set？", "Test Set 应该包含多少样本？", ["测试独立性", "数据规模"]),
    ("为什么要记录 Trace？", "Trace 数据应该如何脱敏？", ["价值", "脱敏"]),
    ("为什么 Tool Output 不可信？", "如何对 Tool Output 做 Schema 校验？", ["安全原则", "Schema"]),
    ("为什么 Eval 模式禁用 Ground Truth？", "评测数据应该如何构造 Golden Question？", ["权限", "数据构造"]),
    ("为什么限制最大追问次数？", "超出最大追问次数以后应该进入什么状态？", ["限制原因", "状态"]),
    ("为什么 Context 有 Token Budget？", "超预算以后哪些内容应该优先压缩？", ["预算原因", "压缩策略"]),
    ("为什么原始轨迹作为源真相？", "原始轨迹应该保存成什么文件格式？", ["治理原则", "文件格式"]),
    ("为什么 Memory 要记录来源？", "Memory 来源 Session 应该如何索引？", ["来源价值", "索引"]),
    ("为什么 Skill Candidate 要经过 Evaluation？", "Skill Evaluation 通过以后如何发布新版本？", ["治理", "发布"]),
    ("为什么 Tool Router 要限制工具集合？", "新增一个 MCP Tool 需要哪些注册步骤？", ["最小工具集", "注册"]),
]


def read_spec(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def make_skill_rows() -> list[dict]:
    rows = []
    for i, (expected, state, keywords) in enumerate(SKILL_CASES, 1):
        rows.append({
            "id": f"skill-{i:02d}",
            "task_type": "skill",
            "state": state,
            "options": dict(SKILL_OPTIONS),
            "expected": expected,
            "metadata": {
                "rule_keywords": {expected: keywords},
                "category": expected,
                "source_type": "synthetic_template",
                "review_status": "needs_human_review"
            }
        })
    return rows


def make_tool_rows() -> list[dict]:
    rows = []
    for i, (expected, state, keywords) in enumerate(TOOL_CASES, 1):
        rows.append({
            "id": f"tool-{i:02d}",
            "task_type": "tool",
            "state": state,
            "options": dict(TOOL_OPTIONS),
            "expected": expected,
            "metadata": {
                "rule_keywords": {expected: keywords},
                "category": expected,
                "source_type": "synthetic_template",
                "review_status": "needs_human_review"
            }
        })
    return rows


def make_intent_rows() -> list[dict]:
    rows = []
    idx = 1
    for expected, pairs in (("same_intent", INTENT_SAME), ("different_intent", INTENT_DIFF)):
        for qa, qb, keywords in pairs:
            rows.append({
                "id": f"intent-{idx:02d}",
                "task_type": "intent",
                "state": {"question_a": qa, "question_b": qb},
                "options": {
                    "same_intent": "The two questions test the same underlying interview intent.",
                    "different_intent": "The two questions test different underlying interview intents."
                },
                "expected": expected,
                "metadata": {
                    "rule_keywords": {expected: keywords},
                    "category": expected,
                    "source_type": "synthetic_template",
                    "review_status": "needs_human_review"
                }
            })
            idx += 1
    return rows


def stratified_split(rows: list[dict], seed: int, ratio: float) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    by_task: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        by_task[row["task_type"]][row["expected"]].append(row)

    validation, test = [], []
    for task_type in sorted(by_task):
        label_groups = by_task[task_type]
        task_total = sum(len(v) for v in label_groups.values())
        task_target = round(task_total * ratio)
        task_target = max(1, min(task_total - 1, task_target))

        desired = {label: len(items) * ratio for label, items in label_groups.items()}
        base = {label: int(desired[label]) for label in label_groups}
        # Keep at least one sample per label in both splits whenever possible.
        for label, items in label_groups.items():
            base[label] = max(1, min(len(items) - 1, base[label])) if len(items) > 1 else 1

        remaining = task_target - sum(base.values())
        ranked = sorted(label_groups, key=lambda label: (desired[label] - base[label], label), reverse=True)
        for label in ranked:
            if remaining <= 0:
                break
            if base[label] < len(label_groups[label]) - 1:
                base[label] += 1
                remaining -= 1

        if remaining != 0:
            raise ValueError(f"unable to allocate validation split for task_type={task_type}")

        for label in sorted(label_groups):
            items = list(label_groups[label])
            rng.shuffle(items)
            n_val = base[label]
            validation.extend(items[:n_val])
            test.extend(items[n_val:])

    rng.shuffle(validation)
    rng.shuffle(test)
    return validation, test


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def summarize(rows: list[dict]) -> dict:
    counts = Counter(row["task_type"] for row in rows)
    by_task_expected: dict[str, dict[str, int]] = defaultdict(lambda: Counter())
    for row in rows:
        by_task_expected[row["task_type"]][row["expected"]] += 1
    return {
        "total": len(rows),
        "task_type_counts": dict(sorted(counts.items())),
        "expected_counts_by_task": {k: dict(sorted(v.items())) for k, v in sorted(by_task_expected.items())},
    }


def validate(rows: list[dict], spec: dict) -> None:
    counts = Counter(row["task_type"] for row in rows)
    expected_counts = spec["counts"]
    for task_type, expected_n in expected_counts.items():
        if counts[task_type] != expected_n:
            raise ValueError(f"{task_type} count={counts[task_type]} expected={expected_n}")
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("duplicate ids detected")
    for row in rows:
        if row["task_type"] == "intent":
            state = row["state"]
            if not isinstance(state, dict) or not state.get("question_a") or not state.get("question_b"):
                raise ValueError(f"intent case {row['id']} must contain question_a and question_b")
    validation, test = stratified_split(rows, spec["seed"], spec["split"]["validation_ratio"])
    if len(validation) + len(test) != len(rows):
        raise ValueError("split size mismatch")
    for split_name, split_rows in (("validation", validation), ("test", test)):
        for task_type in ("skill", "tool", "intent"):
            if not any(r["task_type"] == task_type for r in split_rows):
                raise ValueError(f"{split_name} missing task_type={task_type}")
        if len({r["id"] for r in split_rows}) != len(split_rows):
            raise ValueError(f"duplicate ids in {split_name}")


def generate(spec_path: Path, output_dir: Path) -> dict:
    spec = read_spec(spec_path)
    rows = make_skill_rows() + make_tool_rows() + make_intent_rows()
    validate(rows, spec)
    validation, test = stratified_split(rows, spec["seed"], spec["split"]["validation_ratio"])
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "decision_benchmark.jsonl", rows)
    write_jsonl(output_dir / "decision_validation.jsonl", validation)
    write_jsonl(output_dir / "decision_test.jsonl", test)
    manifest = {
        "dataset_version": spec["version"],
        "seed": spec["seed"],
        "status": spec["status"],
        "requires_human_review": spec["requires_human_review"],
        "note": spec["note"],
        "generator": "stage6.datasets.generate_formal_dataset",
        "counts": {
            "all": summarize(rows),
            "validation": summarize(validation),
            "test": summarize(test),
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate stratified Stage6 decision benchmark dataset")
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    manifest = generate(args.spec, args.output)
    print(json.dumps(manifest["counts"], ensure_ascii=False, indent=2))
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

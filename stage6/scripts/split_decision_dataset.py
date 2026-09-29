import json
from pathlib import Path

src = Path("stage6/datasets/decision_benchmark.jsonl")
val = Path("stage6/datasets/decision_validation.jsonl")
test = Path("stage6/datasets/decision_test.jsonl")

rows = [
    json.loads(line)
    for line in src.read_text(encoding="utf-8").splitlines()
    if line.strip()
]

groups = {}
for row in rows:
    groups.setdefault(row["task_type"], []).append(row)

validation = []
test_rows = []

for task_type, items in groups.items():
    # 当前每类有 4 条：2 条 Validation + 2 条 Test
    if len(items) < 4:
        raise ValueError(f"{task_type} cases too few: {len(items)}")

    validation.extend(items[:2])
    test_rows.extend(items[2:])

val.write_text(
    "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in validation),
    encoding="utf-8",
)

test.write_text(
    "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in test_rows),
    encoding="utf-8",
)

print(f"total={len(rows)}")
print(f"validation={len(validation)}")
print(f"test={len(test_rows)}")

for task_type in sorted(groups):
    v = sum(x["task_type"] == task_type for x in validation)
    t = sum(x["task_type"] == task_type for x in test_rows)
    print(f"{task_type}: validation={v}, test={t}")
import json
from pathlib import Path


def test_policy_eval_dataset_has_broad_coverage():
    path = Path("eval/datasets/policy_assistant_adversarial.jsonl")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) >= 30
    assert sum(row.get("refused", False) for row in rows) >= 5
    assert sum(row.get("must_cite", False) for row in rows) >= 15
    assert sum(row.get("not_found", False) for row in rows) >= 3

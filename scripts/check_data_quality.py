#!/usr/bin/env python3
"""전처리 산출물의 기본 품질을 점검한다."""
from pathlib import Path
import json
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT_DIR / "data" / "processed"


def main() -> None:
    policies_path = PROCESSED_DIR / "policies.json"
    chunks_path = PROCESSED_DIR / "chunks.jsonl"
    with policies_path.open("r", encoding="utf-8") as f:
        policies = json.load(f)
    policy_ids = [p.get("policy_id") for p in policies]
    duplicate_ids = len(policy_ids) - len(set(policy_ids))
    empty_ids = sum(1 for x in policy_ids if not x)
    chunk_count = sum(1 for _ in chunks_path.open("r", encoding="utf-8"))
    missing_report = pd.read_csv(PROCESSED_DIR / "missing_report.csv")

    print("[품질 점검 결과]")
    print(f"정책 수: {len(policies):,}")
    print(f"청크 수: {chunk_count:,}")
    print(f"policy_id 중복 수: {duplicate_ids:,}")
    print(f"policy_id 결측 수: {empty_ids:,}")
    print("주요 결측 리포트 상위 10개:")
    print(missing_report.sort_values("missing_ratio", ascending=False).head(10).to_string(index=False))


if __name__ == "__main__":
    main()

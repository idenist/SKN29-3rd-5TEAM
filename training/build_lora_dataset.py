"""
RAG 평가 질의셋을 sLLM instruction tuning 데이터로 변환하는 스크립트.

입력 예시:
  evaluation/evaluation_dataset.jsonl

출력 예시:
  training/lora_dataset.jsonl

출력 형식:
  {"instruction": "...", "input": "...", "output": "..."}
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_INSTRUCTION = (
    "사용자의 질문과 조건에 맞는 청년 정책, 창업지원 공고, 교육훈련 과정을 "
    "출처 기반으로 안내하라. 마감된 공고를 현재 신청 가능하다고 단정하지 말고, "
    "조건이 부족하면 추가 확인 필요로 답하라."
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"JSONL 파싱 실패: {path}:{line_no}: {e}") from e
    return rows


def pick_reference_answer(row: dict[str, Any]) -> str:
    for key in ["reference_answer", "expected_answer", "reference"]:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    value = row.get("reference_answers")
    if isinstance(value, list):
        answers = [str(item).strip() for item in value if str(item).strip()]
        if answers:
            return answers[0]

    return ""


def build_input_text(row: dict[str, Any]) -> str:
    query = str(row.get("query") or row.get("message") or "").strip()

    condition_parts = []
    for key in [
        "expected_route",
        "expected_source_category",
        "expected_next_action",
        "expected_external_search_target",
    ]:
        value = row.get(key)
        if value not in [None, "", []]:
            condition_parts.append(f"{key}: {value}")

    expected_keywords = row.get("expected_keywords") or row.get("must_have_any")
    if expected_keywords:
        condition_parts.append(f"expected_keywords: {expected_keywords}")

    if condition_parts:
        return f"질문: {query}\n평가 조건: " + " / ".join(condition_parts)

    return f"질문: {query}"


def convert_row(row: dict[str, Any]) -> dict[str, str] | None:
    output = pick_reference_answer(row)
    query = str(row.get("query") or row.get("message") or "").strip()

    if not query or not output:
        return None

    return {
        "instruction": row.get("instruction") or DEFAULT_INSTRUCTION,
        "input": build_input_text(row),
        "output": output,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="evaluation/evaluation_dataset.jsonl")
    parser.add_argument("--output", default="training/lora_dataset.jsonl")
    parser.add_argument("--merge-sample", action="store_true", help="sample_lora_dataset.jsonl도 함께 병합")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = load_jsonl(input_path)
    converted = [item for row in rows if (item := convert_row(row))]

    if args.merge_sample:
        sample_path = Path("training/sample_lora_dataset.jsonl")
        if sample_path.exists():
            converted.extend(load_jsonl(sample_path))

    with output_path.open("w", encoding="utf-8") as f:
        for item in converted:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"입력 케이스: {len(rows)}")
    print(f"변환 케이스: {len(converted)}")
    print(f"저장 위치: {output_path}")


if __name__ == "__main__":
    main()

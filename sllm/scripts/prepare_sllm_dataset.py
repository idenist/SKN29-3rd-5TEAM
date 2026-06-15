"""
청년 정책 RAG 서비스용 sLLM instruction 데이터셋 생성 스크립트.

입력 후보:
- data/processed/opportunities.json
- data/processed/policies.json
- data/processed/chunks.jsonl
- data/processed/opportunity_chunks.jsonl

출력:
- sllm/data/policy_qa_train_sample.jsonl
- sllm/data/policy_qa_eval_sample.jsonl

사용 예:
python sllm/scripts/prepare_sllm_dataset.py \
  --input data/processed/opportunities.json \
  --output-dir sllm/data \
  --max-samples 1000 \
  --eval-ratio 0.1
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any


DOMAIN_QUERY_TEMPLATES = {
    "policy": [
        "{title} 정책에 대해 알려줘",
        "{title} 신청 조건과 지원 내용을 알려줘",
        "청년이 받을 수 있는 {domain} 정책 중 {title} 설명해줘",
    ],
    "startup_notice": [
        "{title} 창업지원 공고 알려줘",
        "지금 신청 가능한 창업지원 공고 중 {title} 설명해줘",
        "예비창업자가 볼 만한 {title} 공고 내용을 알려줘",
    ],
    "training": [
        "{title} 교육훈련 과정 알려줘",
        "국민내일배움카드로 들을 수 있는 {title} 과정 설명해줘",
        "AI/데이터 교육 과정 중 {title} 내용을 알려줘",
    ],
    "default": [
        "{title}에 대해 알려줘",
        "{title} 지원 내용과 신청 방법을 알려줘",
    ],
}

SYSTEM_MESSAGE = (
    "너는 청년 정책 추천 RAG 서비스의 답변 생성기다. "
    "제공된 정책 정보에 근거해서만 답변하고, 정보가 없으면 없다고 말한다. "
    "신청 기간, 제출 서류, 자격 조건은 확정적으로 단정하지 말고 추가 확인 필요 여부를 함께 안내한다."
)


def read_json_or_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {path}")

    if path.suffix.lower() == ".jsonl":
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        return rows

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]

    if isinstance(data, dict):
        for key in ["items", "policies", "data", "results", "opportunities"]:
            value = data.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]

    raise ValueError("지원하지 않는 JSON 구조입니다. list 또는 items/policies/data/results/opportunities 키가 필요합니다.")


def pick_text(*values: Any, default: str = "") -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower() not in {"none", "null", "unknown", "정보 없음"}:
            return text
    return default


def get_nested(item: dict[str, Any], key: str, default: Any = None) -> Any:
    if key in item:
        return item.get(key)
    metadata = item.get("metadata") or {}
    if isinstance(metadata, dict):
        return metadata.get(key, default)
    return default


def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    source_category = pick_text(
        get_nested(item, "source_category"),
        item.get("item_type"),
        default="policy",
    )
    title = pick_text(
        get_nested(item, "title"),
        get_nested(item, "policy_name"),
        item.get("name"),
        item.get("훈련과정명"),
        item.get("공고명"),
    )
    domain = pick_text(get_nested(item, "domain"), item.get("category"), default="청년지원")
    content = pick_text(
        item.get("content"),
        item.get("text"),
        item.get("raw_text"),
        get_nested(item, "content"),
        get_nested(item, "raw_text"),
    )
    support = pick_text(
        get_nested(item, "support_content"),
        item.get("support_content"),
        item.get("policy_summary"),
        item.get("요약"),
    )
    period = pick_text(
        get_nested(item, "application_period"),
        get_nested(item, "application_period_text"),
        item.get("application_period"),
        item.get("신청기간"),
        item.get("훈련기간"),
    )
    docs = pick_text(
        get_nested(item, "required_documents"),
        item.get("required_documents"),
        item.get("제출서류"),
    )
    source_url = pick_text(
        get_nested(item, "source_url"),
        get_nested(item, "application_url"),
        item.get("source_url"),
        item.get("url"),
        item.get("상세URL"),
    )

    return {
        "source_category": source_category,
        "title": title,
        "domain": domain,
        "content": content,
        "support_content": support,
        "application_period": period,
        "required_documents": docs,
        "source_url": source_url,
    }


def build_answer(item: dict[str, Any]) -> str:
    lines = [f"'{item['title']}'에 대한 안내입니다."]

    if item["source_category"] == "training":
        lines.append("항목 유형: 교육훈련 과정")
    elif item["source_category"] == "startup_notice":
        lines.append("항목 유형: 창업지원 공고")
    else:
        lines.append("항목 유형: 청년 정책")

    if item["support_content"]:
        lines.append(f"지원/주요 내용: {item['support_content']}")
    elif item["content"]:
        excerpt = item["content"][:700].replace("\n", " ")
        lines.append(f"주요 내용: {excerpt}")
    else:
        lines.append("주요 내용: 제공된 데이터에는 정보가 없습니다.")

    if item["application_period"]:
        lines.append(f"신청/참여 기간: {item['application_period']}")
    else:
        lines.append("신청/참여 기간: 제공된 데이터에는 정보가 없습니다.")

    if item["required_documents"]:
        lines.append(f"제출 서류: {item['required_documents']}")
    else:
        lines.append("제출 서류: 제공된 데이터에는 정보가 없습니다.")

    if item["source_url"]:
        lines.append(f"출처: {item['source_url']}")
    else:
        lines.append("출처: 제공된 데이터에는 정보가 없습니다. 신청 전 공식 기관 원문 확인이 필요합니다.")

    lines.append("세부 자격 조건은 사용자 나이, 지역, 소득, 고용 상태에 따라 달라질 수 있으므로 원문 확인이 필요합니다.")
    return "\n".join(lines)


def build_instruction_row(item: dict[str, Any]) -> dict[str, Any] | None:
    if not item["title"]:
        return None

    templates = DOMAIN_QUERY_TEMPLATES.get(item["source_category"], DOMAIN_QUERY_TEMPLATES["default"])
    instruction = random.choice(templates).format(title=item["title"], domain=item["domain"])

    context_parts = [
        f"제목: {item['title']}",
        f"유형: {item['source_category']}",
        f"분야: {item['domain']}",
        f"본문: {item['content'][:1200] if item['content'] else '정보 없음'}",
        f"출처: {item['source_url'] or '정보 없음'}",
    ]

    return {
        "messages": [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": instruction + "\n\n참고 정책 정보:\n" + "\n".join(context_parts)},
            {"role": "assistant", "content": build_answer(item)},
        ],
        "instruction": instruction,
        "input": "\n".join(context_parts),
        "output": build_answer(item),
        "metadata": {
            "source_category": item["source_category"],
            "domain": item["domain"],
            "title": item["title"],
            "source_url": item["source_url"],
        },
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="정책/opportunity/chunk JSON 또는 JSONL 경로")
    parser.add_argument("--output-dir", default="sllm/data")
    parser.add_argument("--max-samples", type=int, default=1000)
    parser.add_argument("--eval-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    raw_rows = read_json_or_jsonl(Path(args.input))

    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        item = normalize_item(raw)
        row = build_instruction_row(item)
        if row:
            rows.append(row)

    random.shuffle(rows)
    rows = rows[: args.max_samples]

    eval_size = max(1, int(len(rows) * args.eval_ratio)) if rows else 0
    eval_rows = rows[:eval_size]
    train_rows = rows[eval_size:]

    out_dir = Path(args.output_dir)
    write_jsonl(out_dir / "policy_qa_train_sample.jsonl", train_rows)
    write_jsonl(out_dir / "policy_qa_eval_sample.jsonl", eval_rows)

    print(f"train: {len(train_rows)} -> {out_dir / 'policy_qa_train_sample.jsonl'}")
    print(f"eval : {len(eval_rows)} -> {out_dir / 'policy_qa_eval_sample.jsonl'}")


if __name__ == "__main__":
    main()

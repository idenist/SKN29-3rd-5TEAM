import json
from pathlib import Path

EVAL_PATH = Path("tests/evaluation_dataset.jsonl")
OPPORTUNITIES_PATH = Path("data/processed/opportunities.json")

REQUIRED_FIELDS = ["question", "answer_item_ids"]


def load_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{line_no}번째 줄 JSON 형식 오류: {e}") from e
            rows.append((line_no, obj))
    return rows


def main():
    if not EVAL_PATH.exists():
        raise FileNotFoundError(f"평가 데이터셋 파일이 없습니다: {EVAL_PATH}")

    if not OPPORTUNITIES_PATH.exists():
        raise FileNotFoundError(f"통합 데이터 파일이 없습니다: {OPPORTUNITIES_PATH}")

    eval_rows = load_jsonl(EVAL_PATH)

    opportunities = json.loads(OPPORTUNITIES_PATH.read_text(encoding="utf-8"))
    valid_item_ids = {str(row.get("item_id")) for row in opportunities}

    total = 0
    missing_field_rows = []
    empty_answer_rows = []
    missing_item_ids = []
    duplicate_questions = []

    seen_questions = set()

    for line_no, obj in eval_rows:
        total += 1

        missing_fields = [field for field in REQUIRED_FIELDS if field not in obj]
        if missing_fields:
            missing_field_rows.append({
                "line": line_no,
                "missing_fields": missing_fields,
                "row": obj,
            })
            continue

        question = str(obj.get("question", "")).strip()
        answer_item_ids = obj.get("answer_item_ids", [])

        if not question:
            missing_field_rows.append({
                "line": line_no,
                "missing_fields": ["question"],
                "row": obj,
            })

        if question in seen_questions:
            duplicate_questions.append({
                "line": line_no,
                "question": question,
            })
        seen_questions.add(question)

        if not isinstance(answer_item_ids, list) or len(answer_item_ids) == 0:
            empty_answer_rows.append({
                "line": line_no,
                "question": question,
            })
            continue

        for item_id in answer_item_ids:
            item_id = str(item_id)
            if item_id not in valid_item_ids:
                missing_item_ids.append({
                    "line": line_no,
                    "question": question,
                    "missing_item_id": item_id,
                })

    report_dir = Path("data/reports")
    report_dir.mkdir(parents=True, exist_ok=True)

    summary_path = report_dir / "evaluation_dataset_summary.csv"
    with summary_path.open("w", encoding="utf-8-sig") as f:
        f.write("metric,value\n")
        f.write(f"evaluation_rows,{total}\n")
        f.write(f"missing_field_rows,{len(missing_field_rows)}\n")
        f.write(f"empty_answer_rows,{len(empty_answer_rows)}\n")
        f.write(f"missing_item_ids,{len(missing_item_ids)}\n")
        f.write(f"duplicate_questions,{len(duplicate_questions)}\n")

    detail_path = report_dir / "evaluation_dataset_validation_errors.json"
    detail = {
        "missing_field_rows": missing_field_rows,
        "empty_answer_rows": empty_answer_rows,
        "missing_item_ids": missing_item_ids,
        "duplicate_questions": duplicate_questions,
    }
    detail_path.write_text(
        json.dumps(detail, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"검증 완료: rows={total}")
    print(f"- missing_field_rows={len(missing_field_rows)}")
    print(f"- empty_answer_rows={len(empty_answer_rows)}")
    print(f"- missing_item_ids={len(missing_item_ids)}")
    print(f"- duplicate_questions={len(duplicate_questions)}")
    print(f"- summary={summary_path}")
    print(f"- detail={detail_path}")

    if missing_field_rows or empty_answer_rows or missing_item_ids:
        raise SystemExit("검증 실패: data/reports/evaluation_dataset_validation_errors.json 파일을 확인하세요.")


if __name__ == "__main__":
    main()
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
최종 데이터셋 검증 스크립트

- opportunities.json / opportunity_chunks.jsonl 건수 확인
- item_id 중복 확인
- 필수 필드 결측률 확인
- 청크 길이 통계 생성
- 평가 지표 대응 리포트 생성
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import statistics
from pathlib import Path
from typing import Any, Dict, List


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(map(safe_text, value))
    if isinstance(value, dict):
        return " ".join(map(safe_text, value.values()))
    return str(value)


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--opportunities", default="data/processed/opportunities.json")
    parser.add_argument("--chunks", default="data/processed/opportunity_chunks.jsonl")
    parser.add_argument("--report-dir", default="data/reports")
    args = parser.parse_args()

    opportunities = json.load(open(args.opportunities, encoding="utf-8"))
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    ids = [item.get("item_id") for item in opportunities]
    counter = collections.Counter(ids)
    duplicate_rows = [
        {"item_id": item_id, "count": count}
        for item_id, count in counter.items()
        if item_id and count > 1
    ]
    duplicate_summary = [
        {"metric": "total_rows", "value": len(opportunities)},
        {"metric": "unique_item_id", "value": len(set(ids))},
        {"metric": "duplicate_item_id_count", "value": sum(count - 1 for count in counter.values() if count > 1)},
        {"metric": "duplicate_key_rows", "value": len(duplicate_rows)},
    ]
    write_csv(report_dir / "duplicate_check_report.csv", duplicate_summary + duplicate_rows[:500])

    fields = list(opportunities[0].keys()) if opportunities else []
    missing_rows = []
    for field in fields:
        missing_count = sum(1 for item in opportunities if safe_text(item.get(field)).strip() == "")
        missing_rows.append({
            "field": field,
            "missing_count": missing_count,
            "missing_ratio": round(missing_count / len(opportunities), 4) if opportunities else 0,
            "filled_count": len(opportunities) - missing_count,
        })
    write_csv(report_dir / "missing_value_report.csv", missing_rows)

    chunk_lengths = []
    chunk_categories = collections.Counter()
    with open(args.chunks, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            content = safe_text(obj.get("content", ""))
            source_category = obj.get("source_category") or obj.get("metadata", {}).get("source_category", "")
            chunk_lengths.append((len(content), source_category))
            chunk_categories[source_category] += 1

    lengths = [length for length, _ in chunk_lengths]
    chunk_report = [
        {"metric": "chunk_count", "value": len(lengths)},
        {"metric": "min_length", "value": min(lengths) if lengths else 0},
        {"metric": "max_length", "value": max(lengths) if lengths else 0},
        {"metric": "avg_length", "value": round(sum(lengths) / len(lengths), 2) if lengths else 0},
        {"metric": "median_length", "value": statistics.median(lengths) if lengths else 0},
    ]
    for source_category, count in chunk_categories.items():
        values = [length for length, category in chunk_lengths if category == source_category]
        chunk_report.append({"metric": f"{source_category}_chunk_count", "value": count})
        chunk_report.append({"metric": f"{source_category}_avg_length", "value": round(sum(values) / len(values), 2) if values else 0})
    write_csv(report_dir / "chunk_length_report.csv", chunk_report)

    evaluation_rows = [
        {"evaluation_item": "데이터셋 선정 타당성", "implemented": "Y", "artifact": "README.md, docs/source_notes.md, docs/data_pipeline_summary.md"},
        {"evaluation_item": "편향성 처리", "implemented": "Y", "artifact": "source_coverage_report.csv, docs/data_pipeline_summary.md"},
        {"evaluation_item": "중복 제거", "implemented": "Y", "artifact": "data/reports/duplicate_check_report.csv"},
        {"evaluation_item": "결측치 처리", "implemented": "Y", "artifact": "data/reports/missing_value_report.csv"},
        {"evaluation_item": "정규표현식 텍스트 정규화", "implemented": "Y", "artifact": "scripts/analyze_korean_text.py, docs/text_preprocessing.md"},
        {"evaluation_item": "KoNLPy 형태소 분석", "implemented": "Partial", "artifact": "scripts/analyze_korean_text.py, data/reports/konlpy_keyword_report.csv"},
        {"evaluation_item": "불용어 처리", "implemented": "Y", "artifact": "data/reports/stopword_report.csv"},
        {"evaluation_item": "BoW", "implemented": "Y", "artifact": "data/reports/bow_keyword_report.csv"},
        {"evaluation_item": "TF-IDF", "implemented": "Y", "artifact": "data/reports/tfidf_keyword_report.csv"},
        {"evaluation_item": "Word2Vec/FastText", "implemented": "Partial", "artifact": "data/reports/word2vec_fasttext_status_report.csv"},
        {"evaluation_item": "청킹 전략", "implemented": "Y", "artifact": "docs/chunking_strategy.md, data/reports/chunk_length_report.csv"},
        {"evaluation_item": "데이터 스키마 문서화", "implemented": "Y", "artifact": "docs/data_dictionary.md, docs/opportunity_schema.md"},
        {"evaluation_item": "전처리 파이프라인 문서화", "implemented": "Y", "artifact": "docs/data_pipeline_summary.md"},
        {"evaluation_item": "데이터 수량 문서화", "implemented": "Y", "artifact": "README.md, data/processed/preprocessing_summary.json"},
    ]
    write_csv(report_dir / "evaluation_mapping_report.csv", evaluation_rows)

    print(f"완료: opportunities={len(opportunities)}, chunks={len(lengths)}, duplicate_item_id={len(duplicate_rows)}")


if __name__ == "__main__":
    main()

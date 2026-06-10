#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
최종 통합 데이터 한국어 텍스트 분석 스크립트

기능:
- opportunities.json 로드
- 정규표현식 기반 텍스트 정규화
- KoNLPy Okt 명사 추출 시도
- KoNLPy 사용 불가 시 regex fallback 토큰화
- 불용어 제거
- opportunities_with_keywords.json 및 키워드 리포트 생성
"""

from __future__ import annotations

import argparse
import collections
import csv
import html
import json
import re
from pathlib import Path
from typing import Any, Dict, List


TEXT_FIELDS = ["title", "summary", "target_text", "benefit_text", "raw_text"]

STOPWORDS = {
    "지원", "사업", "대상", "신청", "기간", "관련", "가능", "정보", "제공",
    "과정", "공고", "모집", "안내", "내용", "사항", "기관", "지역", "운영",
    "참여", "이상", "이하", "선정", "문의", "확인", "대해", "위해",
    "경우", "통해", "사업자", "기업", "프로그램", "서비스", "센터", "사용",
    "기준", "해당", "또는", "대한", "년", "월", "일", "및", "등",
    "수", "시", "제", "차", "명", "회", "원", "개", "내", "외", "중",
    "후", "전", "훈련",
}

PRESERVE_WORDS = {
    "청년", "창업", "교육", "주거", "취업", "AI", "데이터", "인공지능",
    "KDT", "디지털", "내일배움카드", "구직자",
}


def safe_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(map(safe_str, value))
    if isinstance(value, dict):
        return " ".join(map(safe_str, value.values()))
    return str(value)


def normalize_text(text: str) -> str:
    text = html.unescape(safe_str(text))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"[^0-9A-Za-z가-힣+#./\- ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fallback_tokens(text: str) -> List[str]:
    text = normalize_text(text)
    tokens = re.findall(r"[가-힣]{2,}|[A-Za-z][A-Za-z0-9+#.\-]{1,}", text)
    result = []
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        upper = token.upper()
        if token in PRESERVE_WORDS or upper in {"AI", "KDT", "IT"}:
            result.append(upper if upper in {"AI", "KDT", "IT"} else token)
        elif token not in STOPWORDS and len(token) >= 2:
            result.append(token)
    return result


def get_tokenizer():
    try:
        from konlpy.tag import Okt  # type: ignore

        okt = Okt()

        def tokenize(text: str) -> List[str]:
            nouns = okt.nouns(normalize_text(text))
            result = []
            for token in nouns:
                if token in PRESERVE_WORDS or (token not in STOPWORDS and len(token) >= 2):
                    result.append(token)
            return result

        return tokenize, "konlpy.Okt", ""
    except Exception as exc:
        return fallback_tokens, "regex_fallback", repr(exc)


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
    parser.add_argument("--input", default="data/processed/opportunities.json")
    parser.add_argument("--output", default="data/processed/opportunities_with_keywords.json")
    parser.add_argument("--report-dir", default="data/reports")
    args = parser.parse_args()

    data = json.load(open(args.input, encoding="utf-8"))
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    tokenize, analyzer_used, analyzer_error = get_tokenizer()

    global_counter = collections.Counter()
    source_counter = collections.defaultdict(collections.Counter)
    domain_counter = collections.defaultdict(collections.Counter)

    output = []
    sample_rows = []
    for idx, item in enumerate(data):
        combined = " ".join(safe_str(item.get(field)) for field in TEXT_FIELDS)
        tokens = tokenize(combined)
        counter = collections.Counter(tokens)
        keywords = [word for word, _ in counter.most_common(30)]

        new_item = dict(item)
        new_item["normalized_text_sample"] = normalize_text(combined)[:1000]
        new_item["noun_keywords"] = keywords
        new_item["keyword_count"] = len(tokens)
        output.append(new_item)

        source_category = item.get("source_category", "")
        domain = item.get("domain", "")
        global_counter.update(tokens)
        source_counter[source_category].update(tokens)
        domain_counter[domain].update(tokens)

        if idx < 1000:
            sample_rows.append({
                "item_id": item.get("item_id", ""),
                "source_category": source_category,
                "domain": domain,
                "title": item.get("title", ""),
                "keyword_count": len(tokens),
                "noun_keywords": "|".join(keywords[:20]),
                "normalized_text_sample": normalize_text(combined)[:500],
            })

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    write_csv(report_dir / "konlpy_keyword_report.csv", [
        {"keyword": word, "count": count, "analyzer": analyzer_used}
        for word, count in global_counter.most_common(500)
    ])

    source_rows = []
    for source_category, counter in source_counter.items():
        for word, count in counter.most_common(100):
            source_rows.append({"source_category": source_category, "keyword": word, "count": count})
    write_csv(report_dir / "source_category_keyword_report.csv", source_rows)

    domain_rows = []
    for domain, counter in domain_counter.items():
        for word, count in counter.most_common(100):
            domain_rows.append({"domain": domain, "keyword": word, "count": count})
    write_csv(report_dir / "domain_keyword_report.csv", domain_rows)

    stopword_rows = [
        {"stopword": word, "status": "removed", "note": "generic administrative/common word"}
        for word in sorted(STOPWORDS)
    ]
    stopword_rows.extend([
        {"stopword": word, "status": "preserved", "note": "domain-critical word"}
        for word in sorted(PRESERVE_WORDS)
    ])
    stopword_rows.append({
        "stopword": "ANALYZER_USED",
        "status": analyzer_used,
        "note": analyzer_error or "KoNLPy available",
    })
    write_csv(report_dir / "stopword_report.csv", stopword_rows)
    write_csv(Path("data/processed/opportunities_text_features_sample.csv"), sample_rows)

    print(f"완료: rows={len(data)}, analyzer={analyzer_used}, output={args.output}")


if __name__ == "__main__":
    main()

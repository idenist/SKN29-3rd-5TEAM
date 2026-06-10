#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BoW / TF-IDF / Word2Vec / FastText 분석 스크립트

RAG 검색은 opportunity_chunks.jsonl의 content 임베딩을 기준으로 수행한다.
본 스크립트는 평가 및 데이터 이해를 위한 키워드 리포트를 생성한다.
"""

from __future__ import annotations

import argparse
import csv
import json
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
    parser.add_argument("--input", default="data/processed/opportunities_with_keywords.json")
    parser.add_argument("--fallback-input", default="data/processed/opportunities.json")
    parser.add_argument("--report-dir", default="data/reports")
    args = parser.parse_args()

    input_path = Path(args.input)
    if input_path.exists():
        data = json.load(open(input_path, encoding="utf-8"))
    else:
        data = json.load(open(args.fallback_input, encoding="utf-8"))

    docs = []
    source_categories = []
    domains = []
    token_sentences = []

    for item in data:
        keywords = item.get("noun_keywords") or []
        if keywords:
            text = " ".join(map(str, keywords))
        else:
            text = " ".join(safe_text(item.get(field)) for field in ["title", "summary", "target_text", "benefit_text", "raw_text"])
        docs.append(text)
        source_categories.append(item.get("source_category", ""))
        domains.append(item.get("domain", ""))
        token_sentences.append(text.split())

    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    try:
        from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer

        count_vectorizer = CountVectorizer(token_pattern=r"(?u)\b\w+\b", max_features=2000)
        bow_matrix = count_vectorizer.fit_transform(docs)
        bow_terms = count_vectorizer.get_feature_names_out()
        bow_counts = bow_matrix.sum(axis=0).A1
        bow_rows = [
            {"keyword": term, "count": int(count)}
            for term, count in sorted(zip(bow_terms, bow_counts), key=lambda pair: pair[1], reverse=True)[:500]
        ]
        write_csv(report_dir / "bow_keyword_report.csv", bow_rows)

        tfidf_vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b", max_features=3000)
        tfidf_matrix = tfidf_vectorizer.fit_transform(docs)
        tfidf_terms = tfidf_vectorizer.get_feature_names_out()

        rows = []
        overall = tfidf_matrix.mean(axis=0).A1
        for term, score in sorted(zip(tfidf_terms, overall), key=lambda pair: pair[1], reverse=True)[:300]:
            rows.append({"group_type": "overall", "group": "all", "keyword": term, "tfidf_score": round(float(score), 6)})

        for group_type, groups in [("source_category", source_categories), ("domain", domains)]:
            for group in sorted(set(groups)):
                idx = [i for i, value in enumerate(groups) if value == group]
                if not idx:
                    continue
                avg = tfidf_matrix[idx].mean(axis=0).A1
                for term, score in sorted(zip(tfidf_terms, avg), key=lambda pair: pair[1], reverse=True)[:80]:
                    rows.append({"group_type": group_type, "group": group, "keyword": term, "tfidf_score": round(float(score), 6)})
        write_csv(report_dir / "tfidf_keyword_report.csv", rows)
    except Exception as exc:
        write_csv(report_dir / "bow_keyword_report.csv", [{"status": "failed", "error": repr(exc)}])
        write_csv(report_dir / "tfidf_keyword_report.csv", [{"status": "failed", "error": repr(exc)}])

    status_rows = []
    try:
        from gensim.models import Word2Vec, FastText

        token_sentences = [sentence for sentence in token_sentences if sentence][:10000]
        if len(token_sentences) > 10:
            w2v = Word2Vec(sentences=token_sentences, vector_size=50, window=5, min_count=5, workers=1, epochs=3)
            _ = FastText(sentences=token_sentences, vector_size=50, window=5, min_count=5, workers=1, epochs=3)

            seed_words = [word for word in ["청년", "창업", "취업", "교육", "데이터", "AI"] if word in w2v.wv]
            if seed_words:
                for seed in seed_words:
                    similar = w2v.wv.most_similar(seed, topn=5)
                    status_rows.append({
                        "model": "Word2Vec",
                        "status": "trained_sample",
                        "seed": seed,
                        "similar_words": "|".join([f"{word}:{round(float(score), 3)}" for word, score in similar]),
                        "note": "평가/분석용 샘플 학습이며 서비스 검색에는 사용하지 않음",
                    })
            else:
                status_rows.append({
                    "model": "Word2Vec/FastText",
                    "status": "trained_sample",
                    "seed": "",
                    "similar_words": "",
                    "note": "시드 단어가 vocabulary에 충분히 존재하지 않음",
                })
        else:
            status_rows.append({
                "model": "Word2Vec/FastText",
                "status": "not_trained",
                "seed": "",
                "similar_words": "",
                "note": "토큰 문장 수 부족",
            })
    except Exception as exc:
        status_rows.append({
            "model": "Word2Vec/FastText",
            "status": "not_available",
            "seed": "",
            "similar_words": "",
            "note": f"{repr(exc)}; RAG 검색은 임베딩 기반이며 BoW/TF-IDF 리포트로 대체",
        })

    write_csv(report_dir / "word2vec_fasttext_status_report.csv", status_rows)
    print(f"완료: rows={len(data)}, reports={report_dir}")


if __name__ == "__main__":
    main()

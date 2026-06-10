#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
K-Startup 창업공고 청년 HIGH 데이터 전처리 스크립트

목적:
- K-Startup 원본 CSV를 보존한 상태에서 청년 관련성 기준으로 분류
- youth_relevance=high 데이터만 온통청년 정책 데이터와 통합할 후보로 생성
- CSV, JSON, JSONL, 리포트를 재현 가능하게 생성

실행:
python scripts/preprocess_kstartup_youth.py \
  --input data/raw/kstartup_api/kstartup_announcements_raw.csv \
  --output-dir data/processed
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
from pathlib import Path

import pandas as pd


TEXT_COLS = [
    "biz_pbanc_nm", "intg_pbanc_biz_nm", "pbanc_ctnt", "aply_trgt",
    "aply_trgt_ctnt", "biz_trgt_age", "prfn_matr", "supt_biz_clsfc",
    "biz_enyy", "aply_excl_trgt_ctnt"
]

HIGH_KEYWORDS = [
    "청년", "청년창업", "청년기업", "청년창업센터", "청년 스타트업",
    "청년 예비창업자", "청년창업자", "청년층"
]

YOUTH_PREFERENCE_KEYWORDS = [
    "청년 우대", "청년우대", "청년 가점", "청년가점", "청년기업 우대",
    "청년기업우대", "청년창업자 우대", "청년창업자우대", "청년층 우대",
    "청년층우대", "청년 참여 우대", "청년참여우대"
]

MEDIUM_KEYWORDS = [
    "예비창업자", "초기창업자", "창업 3년", "창업3년", "창업 7년",
    "창업7년", "스타트업", "창업기업", "일반 창업기업", "창업교육",
    "멘토링", "사업화 자금"
]

LOW_KEYWORDS = [
    "중소기업", "법인기업", "수출기업", "재창업기업", "기술보유기업",
    "지역 주력산업 기업", "주력산업"
]


def safe_text(value) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return html.unescape(str(value)).strip()


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def contains_keywords(text: str, keywords: list[str]) -> list[str]:
    found = []
    compact = compact_text(text)
    for kw in keywords:
        if kw in text or compact_text(kw) in compact:
            if kw not in found:
                found.append(kw)
    return found


def build_raw_text(row: pd.Series) -> str:
    lines = []
    for col in TEXT_COLS:
        val = safe_text(row.get(col, ""))
        if val:
            lines.append(f"{col}: {val}")
    return "\n".join(lines)


def is_youth_age_high(age) -> bool:
    text = compact_text(safe_text(age))
    if not text:
        return False

    # 청년 연령대로 제한된 경우만 high.
    # 40세 이상이 함께 있으면 청년 전용/청년 중심으로 보지 않고 medium으로 둔다.
    if "만40세이상" in text:
        return False

    patterns = [
        "만20세이상~만39세이하",
        "만19세이상~만39세이하",
        "만34세이하",
        "만39세이하",
        "19세~39세",
        "20세~39세",
    ]
    if any(pattern in text for pattern in patterns):
        return True

    return bool(re.search(r"(19|20)세[~\-∼]39세", text))


def age_contains_youth(age) -> bool:
    text = compact_text(safe_text(age))
    patterns = [
        "만20세이상~만39세이하",
        "만19세이상~만39세이하",
        "만34세이하",
        "만39세이하",
        "19세~39세",
        "20세~39세",
    ]
    return any(pattern in text for pattern in patterns)


def classify_youth(row: pd.Series):
    raw_text = build_raw_text(row)
    reasons = []

    youth_direct = contains_keywords(raw_text, HIGH_KEYWORDS)
    youth_pref = contains_keywords(raw_text, YOUTH_PREFERENCE_KEYWORDS)
    age_high = is_youth_age_high(row.get("biz_trgt_age", ""))

    if youth_direct:
        reasons.append("청년 키워드 명시: " + ", ".join(youth_direct[:8]))
    if youth_pref:
        reasons.append("청년 우대/가점 조건 명시: " + ", ".join(youth_pref[:8]))
    if age_high:
        reasons.append("청년 연령 기준 명확: " + safe_text(row.get("biz_trgt_age", "")))

    if reasons:
        youth_preference = bool(youth_pref)
        youth_only = bool(youth_direct or age_high)
        if youth_preference and not (youth_direct or age_high):
            youth_only = False
        return pd.Series({
            "youth_relevance": "high",
            "youth_only": youth_only,
            "youth_preference": youth_preference,
            "youth_relevance_reason": " | ".join(reasons),
        })

    medium_reasons = []
    if age_contains_youth(row.get("biz_trgt_age", "")):
        medium_reasons.append("청년 연령대 포함 가능: " + safe_text(row.get("biz_trgt_age", "")))
    medium_keywords = contains_keywords(raw_text, MEDIUM_KEYWORDS)
    if medium_keywords:
        medium_reasons.append("청년도 신청 가능성이 있는 창업 키워드: " + ", ".join(medium_keywords[:8]))

    if medium_reasons:
        return pd.Series({
            "youth_relevance": "medium",
            "youth_only": False,
            "youth_preference": False,
            "youth_relevance_reason": " | ".join(medium_reasons),
        })

    low_keywords = contains_keywords(raw_text, LOW_KEYWORDS)
    reason = "청년 관련성 명확하지 않음"
    if low_keywords:
        reason += " | 일반 기업 대상 키워드: " + ", ".join(low_keywords[:8])

    return pd.Series({
        "youth_relevance": "low",
        "youth_only": False,
        "youth_preference": False,
        "youth_relevance_reason": reason,
    })


def parse_yyyymmdd(value) -> str:
    text = "".join(ch for ch in safe_text(value) if ch.isdigit())
    if len(text) != 8:
        return ""
    try:
        return dt.datetime.strptime(text, "%Y%m%d").date().isoformat()
    except ValueError:
        return ""


def make_item_id(row: pd.Series) -> str:
    raw = (
        safe_text(row.get("pbanc_sn"))
        or safe_text(row.get("detl_pg_url"))
        or safe_text(row.get("biz_pbanc_nm"))
        or safe_text(row.get("id"))
    )
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]
    return f"startup_{digest}"


def detect_stage(row: pd.Series) -> str:
    text = build_raw_text(row)
    if "재창업" in text:
        return "재창업"
    if "예비창업" in text or "예비창업자" in text:
        return "예비창업"
    if "초기창업" in text or "3년미만" in text or "3년 미만" in text or "창업 3년" in text:
        return "초기창업"
    if "도약" in text or "7년미만" in text or "7년 미만" in text or "창업 7년" in text:
        return "도약"
    if "창업기업" in text or "스타트업" in text:
        return "창업기업"
    return "확인필요"


def combine_application_methods(row: pd.Series) -> str:
    candidates = [
        ("온라인", row.get("aply_mthd_onli_rcpt_istc")),
        ("이메일", row.get("aply_mthd_eml_rcpt_istc")),
        ("방문", row.get("aply_mthd_vst_rcpt_istc")),
        ("우편", row.get("aply_mthd_pssr_rcpt_istc")),
        ("팩스", row.get("aply_mthd_fax_rcpt_istc")),
        ("기타", row.get("aply_mthd_etc_istc")),
    ]
    parts = []
    for label, value in candidates:
        text = safe_text(value)
        if text:
            parts.append(f"{label}: {text}")
    return " / ".join(parts)


def first_url(*values) -> str:
    for value in values:
        text = safe_text(value)
        if text and (text.startswith("http://") or text.startswith("https://") or "." in text):
            return text
    return ""


def normalize_row(row: pd.Series) -> dict:
    title = safe_text(row.get("biz_pbanc_nm")) or safe_text(row.get("intg_pbanc_biz_nm"))
    summary = safe_text(row.get("pbanc_ctnt")) or safe_text(row.get("intg_pbanc_biz_nm")) or title
    benefit_text = safe_text(row.get("supt_biz_clsfc"))
    target_text = safe_text(row.get("aply_trgt_ctnt")) or safe_text(row.get("aply_trgt"))

    start_raw = safe_text(row.get("pbanc_rcpt_bgng_dt"))
    end_raw = safe_text(row.get("pbanc_rcpt_end_dt"))
    period_text = f"{start_raw} ~ {end_raw}".strip() if (start_raw or end_raw) else ""

    application_method = combine_application_methods(row)
    application_url = first_url(row.get("biz_aply_url"), row.get("aply_mthd_onli_rcpt_istc"))
    source_url = first_url(row.get("detl_pg_url"), row.get("biz_gdnc_url"))

    raw_text = "\n".join([x for x in [
        f"제목: {title}" if title else "",
        f"통합공고사업명: {safe_text(row.get('intg_pbanc_biz_nm'))}" if safe_text(row.get("intg_pbanc_biz_nm")) else "",
        f"요약: {summary}" if summary else "",
        f"지원사업분류: {benefit_text}" if benefit_text else "",
        f"신청대상: {safe_text(row.get('aply_trgt'))}" if safe_text(row.get("aply_trgt")) else "",
        f"신청대상내용: {target_text}" if target_text else "",
        f"지원지역: {safe_text(row.get('supt_regin'))}" if safe_text(row.get("supt_regin")) else "",
        f"사업대상연령: {safe_text(row.get('biz_trgt_age'))}" if safe_text(row.get("biz_trgt_age")) else "",
        f"사업업력: {safe_text(row.get('biz_enyy'))}" if safe_text(row.get("biz_enyy")) else "",
        f"우대사항: {safe_text(row.get('prfn_matr'))}" if safe_text(row.get("prfn_matr")) else "",
        f"신청기간: {period_text}" if period_text else "",
        f"신청방법: {application_method}" if application_method else "",
        f"상세URL: {source_url}" if source_url else "",
    ] if x])

    core_values = [title, summary, target_text, safe_text(row.get("supt_regin")), period_text, source_url]
    missing_count = sum(1 for value in core_values if not value)

    return {
        "item_id": make_item_id(row),
        "source_name": "K-Startup",
        "source_category": "startup_notice",
        "domain": "startup",
        "title": title,
        "summary": summary,
        "benefit_text": benefit_text,
        "target_text": target_text,
        "region": safe_text(row.get("supt_regin")),
        "application_period_text": period_text,
        "application_start_date": parse_yyyymmdd(row.get("pbanc_rcpt_bgng_dt")),
        "application_end_date": parse_yyyymmdd(row.get("pbanc_rcpt_end_dt")),
        "organization": safe_text(row.get("pbanc_ntrp_nm")) or safe_text(row.get("sprv_inst")),
        "application_method": application_method,
        "application_url": application_url,
        "source_url": source_url,
        "raw_text": raw_text,
        "startup_stage": detect_stage(row),
        "is_open": safe_text(row.get("rcrt_prgs_yn")),
        "info_score": max(0, 100 - missing_count * 15),
        "needs_detail_check": bool(missing_count >= 2 or not source_url),
        "collected_at": dt.date.today().isoformat(),
    }


def write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for rec in records:
            content = "\n".join([x for x in [
                f"공고명: {rec.get('title', '')}",
                "분야: 창업지원",
                f"지원사업분류: {rec.get('benefit_text', '')}",
                f"요약: {rec.get('summary', '')}",
                f"신청대상: {rec.get('target_text', '')}",
                f"지원지역: {rec.get('region', '')}",
                f"신청기간: {rec.get('application_period_text', '')}",
                f"청년 관련성: {rec.get('youth_relevance', '')}",
                f"청년 우대 여부: {rec.get('youth_preference', '')}",
                f"청년 관련성 판단 이유: {rec.get('youth_relevance_reason', '')}",
                f"창업단계: {rec.get('startup_stage', '')}",
            ] if str(x).split(": ", 1)[-1] not in ["", "nan", "None"]])

            obj = {
                "chunk_id": f"{rec['item_id']}::search_profile",
                "item_id": rec["item_id"],
                "source_category": rec["source_category"],
                "domain": rec["domain"],
                "title": rec["title"],
                "content": content,
                "metadata": {
                    "source_name": rec["source_name"],
                    "youth_relevance": rec["youth_relevance"],
                    "youth_only": rec["youth_only"],
                    "youth_preference": rec["youth_preference"],
                    "startup_stage": rec["startup_stage"],
                    "is_open": rec["is_open"],
                    "region": rec["region"],
                    "application_start_date": rec["application_start_date"],
                    "application_end_date": rec["application_end_date"],
                    "source_url": rec["source_url"],
                    "application_url": rec["application_url"],
                    "needs_detail_check": rec["needs_detail_check"],
                    "info_score": rec["info_score"],
                },
            }
            file.write(json.dumps(obj, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/raw/kstartup_api/kstartup_announcements_raw.csv")
    parser.add_argument("--output-dir", default="data/processed")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path, encoding="utf-8-sig", low_memory=False)

    classified = df.copy()
    class_cols = df.apply(classify_youth, axis=1)
    for col in class_cols.columns:
        classified[col] = class_cols[col]
    classified["startup_stage"] = classified.apply(detect_stage, axis=1)
    classified["is_open"] = classified.get("rcrt_prgs_yn", "")

    normalized = pd.DataFrame([normalize_row(row) for _, row in df.iterrows()])
    for col in ["youth_relevance", "youth_only", "youth_preference", "youth_relevance_reason"]:
        normalized[col] = class_cols[col].values

    final_cols = [
        "item_id", "source_name", "source_category", "domain", "title", "summary",
        "benefit_text", "target_text", "region", "application_period_text",
        "application_start_date", "application_end_date", "organization",
        "application_method", "application_url", "source_url", "raw_text",
        "youth_relevance", "youth_only", "youth_preference",
        "youth_relevance_reason", "startup_stage", "is_open", "info_score",
        "needs_detail_check", "collected_at"
    ]
    normalized = normalized[final_cols]

    high = normalized[normalized["youth_relevance"] == "high"].copy()
    medium = normalized[normalized["youth_relevance"] == "medium"].copy()
    low = normalized[normalized["youth_relevance"] == "low"].copy()
    high_raw = classified[classified["youth_relevance"] == "high"].copy()

    classified.to_csv(output_dir / "startup_youth_classified_all.csv", index=False, encoding="utf-8-sig")
    normalized.to_csv(output_dir / "startup_youth_cleaned_all_common_schema.csv", index=False, encoding="utf-8-sig")
    high.to_csv(output_dir / "startup_youth_high_only.csv", index=False, encoding="utf-8-sig")
    high_raw.to_csv(output_dir / "startup_youth_high_raw_view.csv", index=False, encoding="utf-8-sig")
    medium.to_csv(output_dir / "startup_youth_medium_reference_only.csv", index=False, encoding="utf-8-sig")
    low.to_csv(output_dir / "startup_youth_low_reference_only.csv", index=False, encoding="utf-8-sig")

    records = high.to_dict(orient="records")
    with (output_dir / "startup_youth_high_only.json").open("w", encoding="utf-8") as file:
        json.dump(records, file, ensure_ascii=False, indent=2)

    write_jsonl(output_dir / "startup_youth_high_chunks.jsonl", records)

    report = normalized["youth_relevance"].value_counts().rename_axis("youth_relevance").reset_index(name="count")
    report["ratio"] = (report["count"] / len(normalized) * 100).round(2)
    report.to_csv(output_dir / "startup_youth_relevance_report.csv", index=False, encoding="utf-8-sig")

    metrics = pd.DataFrame([
        {"metric": "total_rows", "value": len(normalized)},
        {"metric": "high_rows_for_integration", "value": len(high)},
        {"metric": "medium_reference_only", "value": len(medium)},
        {"metric": "low_reference_only", "value": len(low)},
        {"metric": "youth_preference_high_rows", "value": int(high["youth_preference"].sum())},
        {"metric": "youth_only_high_rows", "value": int(high["youth_only"].sum())},
        {"metric": "open_high_rows", "value": int((high["is_open"].astype(str) == "Y").sum())},
    ])
    metrics.to_csv(output_dir / "startup_youth_summary_metrics.csv", index=False, encoding="utf-8-sig")

    stage_report = high.groupby("startup_stage").size().reset_index(name="high_count").sort_values("high_count", ascending=False)
    stage_report.to_csv(output_dir / "startup_stage_high_report.csv", index=False, encoding="utf-8-sig")

    summary = {
        "source_file": str(input_path),
        "total_rows": len(normalized),
        "high_rows_for_integration": len(high),
        "medium_reference_only": len(medium),
        "low_reference_only": len(low),
        "high_ratio_percent": round(len(high) / len(normalized) * 100, 2),
        "youth_preference_high_rows": int(high["youth_preference"].sum()),
        "youth_only_high_rows": int(high["youth_only"].sum()),
        "open_high_rows": int((high["is_open"].astype(str) == "Y").sum()),
        "processed_at": dt.datetime.now().isoformat(timespec="seconds"),
        "integration_policy": "온통청년 정책 데이터와 통합하는 대상은 youth_relevance=high인 K-Startup 창업공고만 사용한다.",
    }
    with (output_dir / "preprocessing_summary.json").open("w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)

    print("[K-Startup 청년 HIGH 전처리 완료]")
    print(f"원본 건수: {len(normalized):,}")
    print(f"HIGH 통합 후보: {len(high):,}")
    print(f"MEDIUM 참고용: {len(medium):,}")
    print(f"LOW 참고용: {len(low):,}")
    print(f"청년 우대 HIGH: {int(high['youth_preference'].sum()):,}")
    print(f"출력 폴더: {output_dir}")


if __name__ == "__main__":
    main()

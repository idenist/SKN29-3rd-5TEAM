#!/usr/bin/env python3
"""
온통청년 청년정책 CSV를 백엔드/RAG용 산출물로 전처리하는 스크립트.

입력:
- data/raw/youthcenter_api/youth_policy_raw.csv

출력:
- data/processed/policies_cleaned.csv
- data/processed/policies.json
- data/processed/chunks.jsonl
- data/processed/missing_report.csv
- data/processed/column_summary.csv
- data/processed/duplicate_policy_name_report.csv

주의:
- 원본 데이터는 덮어쓰지 않는다.
- 결측치를 임의 생성하지 않는다.
- policy_name은 중복될 수 있으므로 key로 사용하지 않는다.
- 모든 연결 기준은 policy_id다.
"""
from __future__ import annotations

from pathlib import Path
import json
import re
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
RAW_CSV = ROOT_DIR / "data" / "raw" / "youthcenter_api" / "youth_policy_raw.csv"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"

COLUMN_MAP = {
    "plcyNo": "policy_id",
    "plcyNm": "policy_name",
    "plcyKywdNm": "keywords",
    "plcyExplnCn": "policy_summary",
    "lclsfNm": "large_category",
    "mclsfNm": "middle_category",
    "plcySprtCn": "support_content",
    "sprvsnInstCdNm": "supervising_org",
    "operInstCdNm": "operating_org",
    "bizPrdBgngYmd": "business_start_date",
    "bizPrdEndYmd": "business_end_date",
    "bizPrdEtcCn": "business_period_note",
    "aplyYmd": "application_period_text",
    "plcyAplyMthdCn": "application_method",
    "aplyUrlAddr": "application_url",
    "sbmsnDcmntCn": "required_documents",
    "srngMthdCn": "screening_method",
    "etcMttrCn": "notes",
    "refUrlAddr1": "source_url",
    "refUrlAddr2": "source_url_2",
    "sprtTrgtMinAge": "age_min",
    "sprtTrgtMaxAge": "age_max",
    "sprtTrgtAgeLmtYn": "age_limit_yn",
    "earnMinAmt": "income_min",
    "earnMaxAmt": "income_max",
    "earnEtcCn": "income_condition",
    "addAplyQlfcCndCn": "additional_condition",
    "ptcpPrpTrgtCn": "participation_target",
    "zipCd": "region_codes",
    "plcyMajorCd": "major_code",
    "jobCd": "job_code",
    "schoolCd": "school_code",
    "frstRegDt": "created_at",
    "lastMdfcnDt": "updated_at",
}

BASE_FIELDS = [
    "policy_id", "policy_name", "domain", "keywords", "policy_summary",
    "large_category", "middle_category", "support_content",
    "supervising_org", "operating_org", "age_min", "age_max", "age_text",
    "application_period_text", "application_start_date", "application_end_date",
    "business_start_date", "business_end_date", "business_period_note",
    "application_method", "application_url", "required_documents", "screening_method",
    "income_min", "income_max", "income_condition", "additional_condition",
    "participation_target", "region_codes", "source_url", "source_url_2",
    "notes", "info_score", "needs_detail_check", "raw_text", "created_at", "updated_at",
]

CORE_INFO_FIELDS = [
    "policy_id", "policy_name", "policy_summary", "support_content", "supervising_org",
    "age_text", "application_period_text", "application_method", "application_url", "source_url",
]

DETAIL_CHECK_FIELDS = [
    "application_method", "application_url", "required_documents", "screening_method", "support_content", "source_url",
]


def read_csv(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return pd.read_csv(path, encoding=enc, dtype=str).fillna("")
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, dtype=str).fillna("")


def clean_text(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_date_yyyymmdd(value: str) -> str:
    value = clean_text(value)
    digits = re.sub(r"\D", "", value)
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return value


def split_period(value: str) -> tuple[str, str, str]:
    """신청기간 텍스트를 보존하면서 시작/종료일을 가능한 범위에서 정제한다."""
    text = clean_text(value)
    if not text:
        return "", "", ""
    dates = re.findall(r"\d{4}[.\-/]?\d{2}[.\-/]?\d{2}|\d{8}", text)
    normalized = [normalize_date_yyyymmdd(d) for d in dates]
    start = normalized[0] if len(normalized) >= 1 else ""
    end = normalized[1] if len(normalized) >= 2 else ""
    return text, start, end


def clean_age(min_age: str, max_age: str, age_limit_yn: str) -> tuple[str, str, str]:
    min_digits = re.sub(r"\D", "", clean_text(min_age))
    max_digits = re.sub(r"\D", "", clean_text(max_age))
    min_clean = min_digits if min_digits else ""
    max_clean = max_digits if max_digits else ""
    if clean_text(age_limit_yn).upper() == "Y":
        return min_clean, max_clean, "연령 제한 없음"
    if min_clean and max_clean:
        return min_clean, max_clean, f"만 {min_clean}세 ~ {max_clean}세"
    if min_clean:
        return min_clean, max_clean, f"만 {min_clean}세 이상"
    if max_clean:
        return min_clean, max_clean, f"만 {max_clean}세 이하"
    return min_clean, max_clean, ""


def make_domain(row: pd.Series) -> str:
    parts = [clean_text(row.get("large_category", "")), clean_text(row.get("middle_category", ""))]
    parts = [p for p in parts if p]
    return " > ".join(parts)


def calculate_info_score(row: pd.Series) -> int:
    filled = sum(1 for field in CORE_INFO_FIELDS if clean_text(row.get(field, "")))
    return int(round((filled / len(CORE_INFO_FIELDS)) * 100))


def make_needs_detail_check(row: pd.Series) -> bool:
    missing_detail = any(not clean_text(row.get(field, "")) for field in DETAIL_CHECK_FIELDS)
    low_score = int(row.get("info_score", 0) or 0) < 70
    return bool(missing_detail or low_score)


def make_raw_text(row: pd.Series) -> str:
    blocks = [
        ("정책명", row.get("policy_name", "")),
        ("분야", row.get("domain", "")),
        ("키워드", row.get("keywords", "")),
        ("정책요약", row.get("policy_summary", "")),
        ("지원내용", row.get("support_content", "")),
        ("주관기관", row.get("supervising_org", "")),
        ("운영기관", row.get("operating_org", "")),
        ("나이조건", row.get("age_text", "")),
        ("신청기간", row.get("application_period_text", "")),
        ("신청방법", row.get("application_method", "")),
        ("제출서류", row.get("required_documents", "")),
        ("심사방법", row.get("screening_method", "")),
        ("소득조건", row.get("income_condition", "")),
        ("추가자격조건", row.get("additional_condition", "")),
        ("참여제한대상", row.get("participation_target", "")),
        ("비고", row.get("notes", "")),
        ("신청URL", row.get("application_url", "")),
        ("출처URL", row.get("source_url", "")),
    ]
    lines = [f"{label}: {clean_text(value)}" for label, value in blocks if clean_text(value)]
    return "\n".join(lines)


def build_chunks(policies: list[dict]) -> list[dict]:
    chunks = []
    sections = [
        ("summary", ["policy_summary", "support_content"]),
        ("eligibility", ["age_text", "income_condition", "additional_condition", "participation_target", "region_codes"]),
        ("application", ["application_period_text", "application_method", "required_documents", "screening_method", "application_url"]),
        ("source", ["supervising_org", "operating_org", "source_url", "source_url_2", "notes"]),
    ]
    for policy in policies:
        for section, fields in sections:
            content_parts = []
            for field in fields:
                value = clean_text(policy.get(field, ""))
                if value:
                    content_parts.append(f"{field}: {value}")
            content = "\n".join(content_parts).strip()
            if not content:
                continue
            chunk_id = f"{policy['policy_id']}::{section}"
            chunks.append({
                "chunk_id": chunk_id,
                "policy_id": policy["policy_id"],
                "policy_name": policy.get("policy_name", ""),
                "domain": policy.get("domain", ""),
                "section": section,
                "content": content,
                "source_url": policy.get("source_url", ""),
                "application_url": policy.get("application_url", ""),
                "needs_detail_check": policy.get("needs_detail_check", True),
                "info_score": policy.get("info_score", 0),
            })
    return chunks


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    raw_df = read_csv(RAW_CSV)

    column_summary = pd.DataFrame({
        "column": raw_df.columns,
        "non_null_count": [(raw_df[c].astype(str).str.strip() != "").sum() for c in raw_df.columns],
        "missing_count": [(raw_df[c].astype(str).str.strip() == "").sum() for c in raw_df.columns],
        "sample_value": [next((v for v in raw_df[c].astype(str).head(20) if v.strip()), "") for c in raw_df.columns],
    })
    column_summary.to_csv(PROCESSED_DIR / "column_summary.csv", index=False, encoding="utf-8-sig")

    df = raw_df.rename(columns=COLUMN_MAP).copy()
    for field in BASE_FIELDS:
        if field not in df.columns:
            df[field] = ""

    for col in df.columns:
        df[col] = df[col].map(clean_text)

    df["policy_id"] = df["policy_id"].astype(str).map(clean_text)
    df = df[df["policy_id"] != ""].copy()
    df = df.drop_duplicates(subset=["policy_id"], keep="first").copy()

    ages = df.apply(lambda r: clean_age(r.get("age_min", ""), r.get("age_max", ""), r.get("age_limit_yn", "")), axis=1)
    df["age_min"] = [x[0] for x in ages]
    df["age_max"] = [x[1] for x in ages]
    df["age_text"] = [x[2] for x in ages]

    periods = df["application_period_text"].map(split_period)
    df["application_period_text"] = [x[0] for x in periods]
    df["application_start_date"] = [x[1] for x in periods]
    df["application_end_date"] = [x[2] for x in periods]
    df["business_start_date"] = df["business_start_date"].map(normalize_date_yyyymmdd)
    df["business_end_date"] = df["business_end_date"].map(normalize_date_yyyymmdd)

    df["domain"] = df.apply(make_domain, axis=1)
    df["info_score"] = df.apply(calculate_info_score, axis=1)
    df["needs_detail_check"] = df.apply(make_needs_detail_check, axis=1)
    df["raw_text"] = df.apply(make_raw_text, axis=1)

    out_df = df[BASE_FIELDS].copy()
    out_df.to_csv(PROCESSED_DIR / "policies_cleaned.csv", index=False, encoding="utf-8-sig")

    policies = out_df.to_dict(orient="records")
    with (PROCESSED_DIR / "policies.json").open("w", encoding="utf-8") as f:
        json.dump(policies, f, ensure_ascii=False, indent=2)

    chunks = build_chunks(policies)
    with (PROCESSED_DIR / "chunks.jsonl").open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    missing_report = pd.DataFrame([
        {
            "field": field,
            "missing_count": int((out_df[field].astype(str).str.strip() == "").sum()),
            "missing_ratio": round(float((out_df[field].astype(str).str.strip() == "").mean()), 4),
        }
        for field in BASE_FIELDS
    ])
    missing_report.to_csv(PROCESSED_DIR / "missing_report.csv", index=False, encoding="utf-8-sig")

    duplicate_report = (
        out_df[out_df["policy_name"].duplicated(keep=False)]
        .sort_values(["policy_name", "policy_id"])[["policy_id", "policy_name", "domain", "source_url"]]
    )
    duplicate_report.to_csv(PROCESSED_DIR / "duplicate_policy_name_report.csv", index=False, encoding="utf-8-sig")

    print(f"전처리 완료: policies={len(policies):,}, chunks={len(chunks):,}")


if __name__ == "__main__":
    main()

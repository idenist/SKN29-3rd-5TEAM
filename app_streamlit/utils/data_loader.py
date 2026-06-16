import json
from datetime import date, datetime
from pathlib import Path

import streamlit as st


DATA_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "processed"
    / "opportunities.json"
)

CATEGORY_META = {
    "취업": "💼",
    "금융": "💰",
    "주거": "🏠",
    "교육": "📘",
    "창업": "🚀",
    "복지": "🌿",
}

REGION_CODE_NAMES = {
    "11": "서울",
    "26": "부산",
    "27": "대구",
    "28": "인천",
    "29": "광주",
    "30": "대전",
    "31": "울산",
    "36": "세종",
    "41": "경기",
    "42": "강원",
    "43": "충북",
    "44": "충남",
    "45": "전북",
    "46": "전남",
    "47": "경북",
    "48": "경남",
    "50": "제주",
    "51": "강원",
    "52": "전북",
}
REGION_DISPLAY_ORDER = [
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
]


def _category_for(item):
    source_category = str(item.get("source_category", ""))
    domain = str(item.get("domain", ""))

    if source_category == "training":
        return "교육"
    if source_category == "startup_notice":
        return "창업"
    if "주거" in domain:
        return "주거"
    if "창업" in domain:
        return "창업"
    if "교육" in domain or "역량" in domain:
        return "교육"
    if "금융" in domain or "자산" in domain:
        return "금융"
    if "일자리" in domain or "취업" in domain or "재직" in domain:
        return "취업"
    return "복지"


def _format_date(value):
    if not value:
        return ""

    text = str(value)
    for date_format in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, date_format).strftime("%Y.%m.%d")
        except ValueError:
            continue
    return text


def _period_for(item):
    start = item.get("application_start_date") or item.get("program_start_date")
    end = item.get("application_end_date") or item.get("program_end_date")
    if start or end:
        return f"{_format_date(start) or '미정'} ~ {_format_date(end) or '미정'}"

    return (
        item.get("application_period_text")
        or item.get("program_period_text")
        or "상시 또는 일정 미정"
    )


def _status_for(item):
    end_text = item.get("application_end_date") or item.get("program_end_date")
    is_open = item.get("is_open")

    if is_open in (False, "N", "n", "false", "False"):
        return "신청 마감", "badge-red"

    if end_text:
        try:
            end_date = datetime.strptime(str(end_text), "%Y-%m-%d").date()
            remaining_days = (end_date - date.today()).days
            if remaining_days < 0:
                return "신청 마감", "badge-red"
            if remaining_days <= 14:
                return "마감 임박", "badge-red"
            return "신청 가능", "badge-green"
        except ValueError:
            pass

    if item.get("needs_detail_check"):
        return "조건 확인 필요", "badge-orange"
    return "신청 가능", "badge-green"


def _age_for(item):
    age_min = str(item.get("age_min") or "").strip()
    age_max = str(item.get("age_max") or "").strip()
    age_min = "" if age_min == "0" else age_min
    age_max = "" if age_max == "0" else age_max

    if age_min and age_max:
        return f"만 {age_min}세 ~ {age_max}세"
    if age_min:
        return f"만 {age_min}세 이상"
    if age_max:
        return f"만 {age_max}세 이하"
    return "연령 정보 없음"


def _region_for(item):
    region = str(item.get("region") or item.get("location") or "").strip()
    if not region:
        return "전국"

    region_codes = [
        code.strip()
        for code in region.split(",")
        if code.strip().isdigit()
    ]
    if region_codes and len(region_codes) == len(region.split(",")):
        region_names = {
            REGION_CODE_NAMES[code[:2]]
            for code in region_codes
            if code[:2] in REGION_CODE_NAMES
        }
        if len(region_names) >= 10:
            return "전국"
        if region_names:
            return ", ".join(
                name
                for name in REGION_DISPLAY_ORDER
                if name in region_names
            )

    return region


def _normalize(item, rank):
    category = _category_for(item)
    status, status_class = _status_for(item)
    application_url = str(item.get("application_url") or "").strip()
    source_url = str(item.get("source_url") or "").strip()
    age_min = str(item.get("age_min") or "").strip()
    age_max = str(item.get("age_max") or "").strip()
    age_min = "" if age_min == "0" else age_min
    age_max = "" if age_max == "0" else age_max

    return {
        "id": str(item.get("item_id") or f"opportunity_{rank}"),
        "rank": rank,
        "title": str(item.get("title") or "제목 없음"),
        "category": category,
        "icon": CATEGORY_META[category],
        "description": str(item.get("summary") or "상세 내용은 공식 공고를 확인하세요."),
        "period": _period_for(item),
        "age": _age_for(item),
        "support": str(item.get("benefit_text") or "공식 공고 확인"),
        "method": str(item.get("application_method") or "공식 공고 확인"),
        "income": str(item.get("target_text") or "공식 공고 확인"),
        "docs": "공식 공고 확인",
        "status": status,
        "status_class": status_class,
        "detail": category,
        "region": _region_for(item),
        "job_status": "무관",
        "housing_status": "무관",
        "score": int(item.get("info_score") or 0),
        "official_url": application_url or source_url,
        "application_url": application_url,
        "source_url": source_url,
        "organization": str(item.get("organization") or "기관 정보 없음"),
        "source_category": str(item.get("source_category") or ""),
        "needs_detail_check": bool(item.get("needs_detail_check")),
        "age_min": age_min,
        "age_max": age_max,
        "search_text": " ".join(
            str(item.get(key) or "")
            for key in ("title", "summary", "domain", "tags", "target_text", "region", "location")
        ).lower(),
    }


@st.cache_data(show_spinner="실제 정책 데이터를 불러오는 중입니다...")
def load_policies():
    with DATA_PATH.open(encoding="utf-8") as data_file:
        opportunities = json.load(data_file)

    policies = [
        _normalize(item, rank)
        for rank, item in enumerate(opportunities, 1)
    ]
    return sorted(policies, key=lambda item: item["score"], reverse=True)

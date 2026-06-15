"""
공식 외부 출처 fallback 모듈.

내부 Vector DB 검색 결과가 부족할 때 공식 출처 도메인으로 제한된 웹 검색을 수행한다.
검색 API 키가 있으면 API를 우선 사용하고, 없으면 DuckDuckGo HTML 검색을 best-effort로 시도한다.
네트워크/키가 없거나 결과가 없으면 기존처럼 검색 계획만 반환한다.
외부 검색 결과는 공식 도메인 제한, 문서/PDF 제외, 핵심 키워드 검증, 재정렬(rerank)을 거친 뒤 답변 후보로 사용한다.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


OFFICIAL_SOURCE_MAP: dict[str, dict[str, Any]] = {
    "startup_notice": {
        "key": "startup_notice",
        "name": "K-Startup",
        "kind": "창업지원 공고",
        "official_url": "https://www.k-startup.go.kr",
        "allowed_domains": ["k-startup.go.kr"],
    },
    "policy": {
        "key": "policy",
        "name": "온통청년",
        "kind": "청년정책",
        "official_url": "https://www.youthcenter.go.kr",
        "allowed_domains": ["youthcenter.go.kr", "youth.seoul.go.kr", "bokjiro.go.kr", "moel.go.kr"],
    },
    "training": {
        "key": "training",
        "name": "고용24/HRD-Net",
        "kind": "교육훈련 과정",
        "official_url": "https://www.work24.go.kr",
        "allowed_domains": ["work24.go.kr", "hrd.go.kr"],
    },
}


TRAINING_KEYWORDS = [
    "훈련",
    "국비",
    "국비지원",
    "내일배움",
    "국민내일배움카드",
    "k-digital",
    "kdt",
    "교육과정",
    "자격증",
    "기능사",
    "일경험",
    "직무",
]


POLICY_FALLBACK_EXPANSIONS: list[tuple[list[str], list[str]]] = [
    (
        ["교통비"],
        [
            "청년 교통비 지원",
            "중소기업 청년 교통비 지원",
            "청년 대중교통비 지원",
            "청년 복지 교통비 지원",
        ],
    ),
    (
        ["식품"],
        [
            "취약계층 청년 식품 지원",
            "청년 식비 지원",
            "청년 먹거리 지원",
            "저소득 청년 식품 지원",
        ],
    ),
    (
        ["식비"],
        [
            "청년 식비 지원",
            "청년 먹거리 지원",
            "취약계층 청년 식비 지원",
            "저소득 청년 식생활 지원",
            "청년 급식 지원",
        ],
    ),
    (
        ["공공기관", "인턴"],
        [
            "청년 공공기관 인턴",
            "청년 행정인턴",
            "공공기관 청년 일경험",
        ],
    ),
    (
        ["일경험"],
        [
            "청년 일경험 지원사업",
            "청년 직무 일경험",
            "미래내일 일경험 사업",
        ],
    ),
    (
        ["행사"],
        [
            "청년 고용 정책 행사",
            "청년 일자리 박람회",
            "청년 고용정책 설명회",
            "청년 고용정책 한눈에",
            "청년 일자리 정책 설명회",
        ],
    ),
    (
        ["장기", "재직"],
        [
            "중소기업 재직 청년 장기재직 공제",
            "청년재직자 내일채움공제",
            "청년 장기재직 지원",
        ],
    ),
    (
        ["임차료"],
        [
            "청년 창업자 임차료 지원",
            "청년 창업기업 사무실 임차료 지원",
            "창업기업 사업장 임차료 지원",
            "청년 창업기업 사무실 임차료 지원사업 참여자 모집",
            "창업자 임차료 지원사업",
            "청년 창업 입주공간 지원",
        ],
    ),
]


class _DDGHTMLParser(HTMLParser):
    """DuckDuckGo HTML 결과에서 제목/URL/snippet을 아주 보수적으로 추출한다."""

    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._capture: str | None = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k: v or "" for k, v in attrs}
        cls = attr.get("class", "")

        if tag == "a" and "result__a" in cls:
            href = attr.get("href", "")
            self._current = {"title": "", "url": href, "snippet": ""}
            self._capture = "title"
            self._buffer = []
            return

        if tag in {"a", "div", "span"} and "result__snippet" in cls and self._current is not None:
            self._capture = "snippet"
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture == "title" and tag == "a" and self._current is not None:
            self._current["title"] = html.unescape(" ".join(self._buffer)).strip()
            if self._current.get("title") and self._current.get("url"):
                self.results.append(self._current)
            self._capture = None
            self._buffer = []
            return

        if self._capture == "snippet" and tag in {"a", "div", "span"} and self._current is not None:
            self._current["snippet"] = html.unescape(" ".join(self._buffer)).strip()
            self._capture = None
            self._buffer = []


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(v.strip() for v in values if v and v.strip()))


def _normalize_domain(domain: str) -> str:
    return domain.lower().replace("www.", "").strip()



def _clean_result_url(url: str) -> str:
    """검색 결과 URL에서 DuckDuckGo redirect wrapper 등을 제거한다."""
    url = _safe_str(url)
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlparse(url)
    if "duckduckgo.com" in parsed.netloc and parsed.query:
        qs = parse_qs(parsed.query)
        for key in ("uddg", "u"):
            if key in qs and qs[key]:
                return unquote(qs[key][0])
    return url

def _allowed_domain(url: str, allowed_domains: list[str]) -> bool:
    try:
        netloc = _normalize_domain(urlparse(url).netloc)
    except Exception:
        return False
    if not netloc:
        return False
    allowed = [_normalize_domain(domain) for domain in allowed_domains]
    return any(netloc == domain or netloc.endswith("." + domain) for domain in allowed)




def _normalize_text_for_match(text: str) -> str:
    """검색 결과 품질 판단용 텍스트 정규화."""
    text = html.unescape(_safe_str(text)).lower()
    text = re.sub(r"<.*?>", " ", text)
    text = re.sub(r"[\[\](){}/_|·,.:;!?\-–—]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_document_file(url: str, title: str) -> bool:
    """PDF/문서 파일은 일반적으로 스니펫 품질이 낮아 기본 제외한다."""
    if os.getenv("ALLOW_EXTERNAL_DOCUMENT_RESULTS", "false").lower() in {"true", "1", "yes", "y"}:
        return False
    text = f"{url} {title}".lower()
    blocked_ext = (".pdf", ".hwp", ".hwpx", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx")
    return any(ext in text for ext in blocked_ext) or title.strip().lower().startswith("[pdf]")


def _required_keyword_groups(query: str, target_key: str) -> list[list[str]]:
    """
    질문 의도별로 반드시 근거에 나타나야 하는 핵심 키워드 그룹을 만든다.
    각 내부 리스트는 OR 조건, 그룹 간에는 AND 조건이다.
    """
    q = _normalize_text_for_match(query)
    groups: list[list[str]] = []

    if "지게차" in q:
        groups.append(["지게차", "지게차운전기능사"])
        groups.append(["훈련", "교육", "국비", "내일배움", "hrd", "고용24"])

    if "교통비" in q or "교통" in q:
        groups.append(["교통비", "교통", "대중교통"])
        groups.append(["청년", "근로자", "재직", "중소기업"])

    if any(word in q for word in ["식품", "식비", "먹거리", "도시락"]):
        groups.append(["식품", "식비", "먹거리", "식사", "도시락", "급식", "푸드", "양곡", "식생활", "식료품", "식품비"])
        groups.append(["청년", "취약", "저소득", "취약계층", "기초생활", "차상위"])

    if "임차료" in q or "임대료" in q:
        groups.append(["임차료", "임대료", "월세", "사무실", "공간", "입주"])
        groups.append(["창업", "창업자", "창업기업", "스타트업"])

    if "일경험" in q or ("직무" in q and "경험" in q):
        groups.append(["일경험", "직무", "인턴", "미래내일"])
        groups.append(["청년", "고용24", "고용노동부"])

    if "공공기관" in q and "인턴" in q:
        groups.append(["공공기관", "행정", "공공"])
        groups.append(["인턴", "일경험", "체험"])

    if "행사" in q or "한눈" in q:
        groups.append(["행사", "박람회", "설명회", "페어", "컨퍼런스", "한눈"])
        groups.append(["고용", "일자리", "취업", "정책"])

    if ("장기" in q and "재직" in q) or "공제" in q:
        groups.append(["공제", "내일채움", "재직", "장기재직", "장기"])
        groups.append(["중소기업", "청년", "근로자", "재직자"])

    # 교육훈련은 제목이 범용적인 경우가 많지만, 최소한 원 질문의 핵심 자격/과정명이 보여야 함.
    if target_key == "training" and not groups:
        if "자격증" in q or "기능사" in q or "국비" in q or "훈련" in q:
            groups.append(["자격증", "기능사", "국비", "훈련", "교육", "내일배움", "hrd", "고용24"])

    return groups


_GENERIC_QUERY_STOPWORDS = {
    "청년", "지원", "지원사업", "사업", "정책", "있어", "있나요", "알려줘", "받을", "받을수", "있는", "해주는", "관련", "추천", "과정", "프로그램",
    "분야", "정보", "확인", "가능", "가능한", "해주세요", "좀", "한눈에",
}


def _generic_query_terms(query: str) -> list[str]:
    q = _normalize_text_for_match(query)
    terms = re.findall(r"[가-힣A-Za-z0-9\-]+", q)
    cleaned: list[str] = []
    for term in terms:
        term = term.strip().lower()
        if len(term) < 2:
            continue
        if term in _GENERIC_QUERY_STOPWORDS:
            continue
        if term.endswith("은") or term.endswith("는") or term.endswith("이") or term.endswith("가"):
            term = term[:-1]
        if term and term not in _GENERIC_QUERY_STOPWORDS:
            cleaned.append(term)
    return _dedupe(cleaned)[:8]



def _title_specificity_bonus(title: str, snippet: str, query: str, target_key: str) -> float:
    """구체적인 결과를 위로 올리기 위한 보너스/패널티 점수."""
    q = _normalize_text_for_match(query)
    title_norm = _normalize_text_for_match(title)
    snippet_norm = _normalize_text_for_match(snippet)
    combined = f"{title_norm} {snippet_norm}"
    bonus = 0.0

    # 질문별 핵심 조합이 제목에 직접 보이면 가장 강하게 보상한다.
    phrase_rules = [
        (["지게차"], ["국비", "내일배움", "훈련", "교육"], 0.35),
        (["교통비"], ["중소기업", "청년", "산업단지"], 0.40),
        (["식품", "식비", "먹거리"], ["취약", "저소득", "청년", "급식", "식생활"], 0.40),
        (["임차료", "임대료"], ["창업", "사무실", "사업장", "입주"], 0.45),
        (["일경험"], ["청년", "직무", "미래내일", "고용24"], 0.35),
        (["행사", "박람회", "설명회"], ["청년", "고용", "일자리", "취업"], 0.35),
        (["공제", "내일채움"], ["중소기업", "청년", "재직", "장기"], 0.35),
    ]
    for primary, secondary, value in phrase_rules:
        if any(p in q for p in primary):
            primary_hit_title = any(p in title_norm for p in primary)
            secondary_hit_title = any(s in title_norm for s in secondary)
            primary_hit_any = any(p in combined for p in primary)
            secondary_hit_any = any(s in combined for s in secondary)
            if primary_hit_title and secondary_hit_title:
                bonus += value
            elif primary_hit_any and secondary_hit_any:
                bonus += value * 0.65

    # 제목이 너무 포괄적이면 뒤로 보낸다. 단, snippet에 핵심어가 충분하면 약한 패널티만 준다.
    broad_title_terms = ["청년지원정보", "훈련 통합검색", "정책/제도", "고객센터", "상세", "포털", "통합검색"]
    if any(term.lower() in title_norm for term in broad_title_terms):
        bonus -= 0.20

    # PDF/보고서/연구 문서는 이미 대체로 제외하지만 제목에 남아 있으면 추가 패널티.
    if any(term in title_norm for term in ["연구", "보고서", "분과", "자료집"]):
        bonus -= 0.15

    return bonus


def _result_sort_key(raw: dict[str, Any], target: dict[str, Any], query: str, quality: dict[str, Any]) -> float:
    title = _safe_str(raw.get("title"))
    snippet = _safe_str(raw.get("snippet") or raw.get("content"))
    target_key = _safe_str(target.get("key"), "policy")
    base = float(quality.get("score") or 0.0)
    bonus = _title_specificity_bonus(title=title, snippet=snippet, query=query, target_key=target_key)
    # Tavily가 주는 원점수가 있으면 아주 약하게만 반영한다.
    provider_score = 0.0
    try:
        provider_score = float(raw.get("score") or 0.0) * 0.05
    except Exception:
        provider_score = 0.0
    return round(base + bonus + provider_score, 4)

def _evaluate_external_result(raw: dict[str, Any], target: dict[str, Any], query: str) -> dict[str, Any]:
    """Tavily/검색 API 결과가 답변 근거로 쓸 만큼 질문과 직접 관련 있는지 평가한다."""
    title = _safe_str(raw.get("title"))
    url = _clean_result_url(_safe_str(raw.get("url")))
    snippet = _safe_str(raw.get("snippet") or raw.get("content"))
    target_key = _safe_str(target.get("key"), "policy")
    combined = _normalize_text_for_match(" ".join([title, snippet, url]))

    reject_reasons: list[str] = []
    matched_terms: list[str] = []

    if _is_document_file(url, title):
        reject_reasons.append("문서/PDF 검색 결과 제외")

    # 너무 일반적인 HRD 상세 제목은 snippet/url에 실제 과정 키워드가 없으면 제외
    generic_title_patterns = [
        "훈련과정 상세", "훈련과정 정보", "상세 >", "고객센터", "정책/제도", "정부인증 가사서비스",
    ]
    if any(pattern.lower() in title.lower() for pattern in generic_title_patterns):
        required_groups = _required_keyword_groups(query, target_key)
        if required_groups:
            group_hit = [any(term.lower() in combined for term in group) for group in required_groups]
            if not all(group_hit):
                reject_reasons.append("일반 상세/고객센터 페이지이며 질문 핵심 키워드 근거 부족")

    required_groups = _required_keyword_groups(query, target_key)
    group_results: list[dict[str, Any]] = []
    if required_groups:
        for group in required_groups:
            hits = [term for term in group if term.lower() in combined]
            if hits:
                matched_terms.extend(hits)
            group_results.append({"group": group, "hits": hits})
        missing_groups = [row["group"] for row in group_results if not row["hits"]]
        if missing_groups:
            reject_reasons.append(f"질문 핵심 키워드 그룹 미충족: {missing_groups[:2]}")

    generic_terms = _generic_query_terms(query)
    generic_hits = [term for term in generic_terms if term.lower() in combined]
    matched_terms.extend(generic_hits)

    # 특정 규칙이 없는 일반 질문에서는 최소한 핵심어 일부는 보여야 한다.
    if not required_groups and generic_terms:
        min_hits = 1 if len(generic_terms) <= 2 else 2
        if len(generic_hits) < min_hits:
            reject_reasons.append(f"질문 핵심어 overlap 부족: {generic_hits}/{generic_terms}")

    # 과도하게 넓은 포털/메인/센터 페이지는 핵심어가 충분하지 않으면 제외
    broad_page_terms = ["포털", "고객센터", "자료실", "공지사항", "전체", "메인"]
    if any(term in combined for term in broad_page_terms) and len(set(matched_terms)) < 2:
        reject_reasons.append("포털/고객센터성 페이지이며 직접 근거 부족")

    # 점수: 그룹 충족과 핵심어 hit를 합산
    score = 0.0
    if required_groups:
        satisfied = sum(1 for row in group_results if row["hits"])
        score += satisfied / max(1, len(required_groups)) * 0.7
    if generic_terms:
        score += min(0.3, len(set(generic_hits)) / max(1, len(generic_terms)) * 0.3)
    if not required_groups and not generic_terms:
        score = 0.5

    ranking_score = _result_sort_key(raw, target, query, {"score": score})

    return {
        "usable": not reject_reasons,
        "score": round(score, 4),
        "ranking_score": ranking_score,
        "matched_terms": _dedupe(matched_terms),
        "generic_terms": generic_terms,
        "required_groups": required_groups,
        "reject_reasons": reject_reasons,
        "clean_url": url,
    }


def _make_domain_query(query: str, domains: list[str]) -> str:
    domain_expr = " OR ".join(f"site:{domain}" for domain in domains)
    return f"({domain_expr}) {query}" if len(domains) > 1 else f"site:{domains[0]} {query}"


def select_official_targets(source_category: str | None, route: str | None, query: str) -> list[dict[str, Any]]:
    """source_category/route/query를 기준으로 조회해야 할 공식 출처를 선택한다."""
    source_category = _safe_str(source_category)
    route = _safe_str(route)
    query_text = _safe_str(query).lower()

    # 창업 임차료/임대료/입주공간은 K-Startup 공고뿐 아니라 지자체 청년정책에도 자주 올라온다.
    if any(word in query_text for word in ["임차료", "임대료", "사무실", "사업장", "입주공간", "입주 공간"]):
        return [OFFICIAL_SOURCE_MAP["startup_notice"], OFFICIAL_SOURCE_MAP["policy"]]

    # 일경험/직무경험은 고용24에 공식 포털/제도 페이지가 있는 경우가 많다.
    if any(word in query_text for word in ["일경험", "직무 일경험", "직무경험", "미래내일"]):
        return [OFFICIAL_SOURCE_MAP["training"], OFFICIAL_SOURCE_MAP["policy"]]

    if source_category in OFFICIAL_SOURCE_MAP:
        return [OFFICIAL_SOURCE_MAP[source_category]]

    if route == "창업" or any(word in query_text for word in ["창업", "스타트업", "사업화"]):
        return [OFFICIAL_SOURCE_MAP["startup_notice"]]

    if route == "교육" and any(word in query_text for word in TRAINING_KEYWORDS):
        return [OFFICIAL_SOURCE_MAP["training"]]

    if any(word in query_text for word in TRAINING_KEYWORDS):
        return [OFFICIAL_SOURCE_MAP["training"]]

    if route in {"주거", "금융", "복지문화", "참여권리", "일자리", "교육"}:
        return [OFFICIAL_SOURCE_MAP["policy"]]

    return list(OFFICIAL_SOURCE_MAP.values())

def _build_training_query_expansions(query: str) -> list[str]:
    q = _safe_str(query)
    compact = q.replace("있어?", "").replace("있나요?", "").replace("알려줘", "").strip()
    expansions: list[str] = []

    if "지게차" in q:
        expansions.extend(
            [
                "지게차운전기능사 국민내일배움카드",
                "지게차 자격증 국비지원 과정",
                "지게차 훈련과정 고용24",
                "지게차운전기능사 훈련과정",
            ]
        )

    if "자격증" in q or "기능사" in q:
        expansions.extend([f"{compact} 국민내일배움카드", f"{compact} 국비지원", f"{compact} 훈련과정"])

    if "국비" in q or "내일배움" in q or "훈련" in q:
        expansions.append(f"{compact} 고용24")

    if "일경험" in q or "직무" in q:
        expansions.extend(["청년 직무 일경험 지원사업", "미래내일 일경험 사업", "청년 일경험 프로그램"])

    return _dedupe(expansions)


def _build_policy_query_expansions(query: str) -> list[str]:
    q = _safe_str(query)
    expansions: list[str] = []

    for triggers, candidates in POLICY_FALLBACK_EXPANSIONS:
        if all(trigger in q for trigger in triggers) or any(trigger in q for trigger in triggers):
            expansions.extend(candidates)

    return _dedupe(expansions)


def build_external_search_queries(
    query: str,
    user_conditions: dict[str, Any] | None = None,
    route: str | None = None,
) -> list[str]:
    """공식 출처 조회에 사용할 검색어 후보를 만든다."""
    user_conditions = user_conditions or {}
    query = _safe_str(query)
    route = _safe_str(route)

    parts = [query]
    region = _safe_str(user_conditions.get("region"))
    interest_domain = _safe_str(user_conditions.get("interest_domain"))

    if region and region not in query:
        parts.append(region)

    if interest_domain and interest_domain not in query:
        parts.append(interest_domain)
    elif route and route not in query and route not in {"전체", "기타"}:
        parts.append(route)

    compact = " ".join(dict.fromkeys(" ".join(parts).split()))
    queries = [compact]

    if route == "교육" or any(word in query for word in TRAINING_KEYWORDS):
        queries.extend(_build_training_query_expansions(query))
    else:
        queries.extend(_build_policy_query_expansions(query))

    if route in {"일자리", "복지문화", "주거", "금융", "참여권리"}:
        queries.extend(_build_policy_query_expansions(query))

    if any(word in query for word in ["지금", "현재", "신청 가능한", "신청가능한", "모집 중", "모집중", "접수 중", "접수중", "2026"]):
        queries.append(f"{compact} 모집중")
        queries.append(f"{compact} 신청 가능")

    return _dedupe(queries)[:8]


def plan_official_external_search(
    query: str | None = None,
    user_conditions: dict[str, Any] | None = None,
    route: str | None = None,
    filters: dict[str, Any] | None = None,
    sufficiency_reasons: list[str] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """외부 공식 출처 fallback 계획을 생성한다."""
    if query is None:
        query = kwargs.get("user_query") or kwargs.get("message") or ""

    filters = filters or {}
    user_conditions = user_conditions or {}
    sufficiency_reasons = sufficiency_reasons or []

    source_category = _safe_str(filters.get("source_category"))
    targets = select_official_targets(source_category=source_category, route=route, query=query)
    queries = build_external_search_queries(query=query, user_conditions=user_conditions, route=route)

    return {
        "status": "planned_not_executed",
        "reason": sufficiency_reasons,
        "targets": targets,
        "target_names": [target["name"] for target in targets],
        "queries": queries,
        "message": "공식 외부 출처 검색 계획을 생성했습니다. 실제 API 호출은 추후 K-Startup/온통청년/고용24 연동으로 교체 예정입니다.",
    }


def _result_to_policy_item(
    raw: dict[str, Any],
    target: dict[str, Any],
    query: str,
    rank: int,
    backend: str,
    quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
    title = _safe_str(raw.get("title"), "공식 출처 검색 결과")
    url = _safe_str(raw.get("url"))
    snippet = _safe_str(raw.get("snippet") or raw.get("content"), "공식 출처 검색 결과입니다. 원문에서 세부 조건을 확인해야 합니다.")
    quality = quality or {}
    matched_terms = quality.get("matched_terms") or []
    relevance_note = ""
    if matched_terms:
        relevance_note = f"\nmatched_keywords: {', '.join(str(term) for term in matched_terms[:8])}"
    source_category = _safe_str(target.get("key"), "policy")
    official_source = _safe_str(target.get("name"), "공식 출처")
    digest = hashlib.md5(f"{url}|{title}".encode("utf-8")).hexdigest()[:12]

    return {
        "policy_id": f"external_{source_category}_{digest}",
        "policy_name": title,
        "title": title,
        "text": (
            f"official_source: {official_source}\n"
            f"search_query: {query}\n"
            f"summary: {snippet}\n"
            f"source_url: {url}\n"
            f"relevance_score: {quality.get('score', '')}{relevance_note}\n"
            "note: 공식 외부 출처 검색 결과이며, 세부 자격/신청기간은 원문 확인이 필요합니다."
        ),
        "content": snippet,
        "source_url": url,
        "source_category": source_category,
        "deadline_status": "unknown",
        "application_end_date": None,
        "is_expired": False,
        "score": max(0.35, min(0.95, float(quality.get("ranking_score") or quality.get("score") or 0.5) - (rank * 0.02))),
        "needs_detail_check": True,
        "cautions": ["공식 외부 출처 검색 결과이므로 신청 전 원문에서 세부 조건 확인 필요"],
        "metadata": {
            "source_category": source_category,
            "source_url": url,
            "application_url": url,
            "official_source": official_source,
            "official_source_url": target.get("official_url", ""),
            "external_search": True,
            "external_search_backend": backend,
            "needs_detail_check": True,
            "external_relevance_score": quality.get("score"),
            "external_ranking_score": quality.get("ranking_score"),
            "external_matched_terms": matched_terms,
        },
    }


def _search_with_tavily(query: str, domains: list[str], max_results: int, timeout: float) -> tuple[list[dict[str, str]], str]:
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return [], ""

    import requests

    response = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": api_key,
            "query": query,
            "search_depth": os.getenv("TAVILY_SEARCH_DEPTH", "basic"),
            "max_results": max_results,
            "include_domains": domains,
            "include_raw_content": os.getenv("TAVILY_INCLUDE_RAW_CONTENT", "false").lower() in {"true", "1", "yes", "y"},
        },
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    results = []
    for item in data.get("results", []) or []:
        snippet = _safe_str(item.get("content"))
        raw_content = _safe_str(item.get("raw_content"))
        if raw_content and len(raw_content) > len(snippet):
            snippet = (snippet + " " + raw_content[:700]).strip()
        results.append({"title": _safe_str(item.get("title")), "url": _safe_str(item.get("url")), "snippet": snippet})
    return results, "tavily"


def _search_with_brave(query: str, domains: list[str], max_results: int, timeout: float) -> tuple[list[dict[str, str]], str]:
    api_key = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
    if not api_key:
        return [], ""

    import requests

    response = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        headers={"Accept": "application/json", "X-Subscription-Token": api_key},
        params={"q": _make_domain_query(query, domains), "count": max_results},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    results = []
    for item in (data.get("web") or {}).get("results", []) or []:
        results.append({"title": _safe_str(item.get("title")), "url": _safe_str(item.get("url")), "snippet": _safe_str(item.get("description"))})
    return results, "brave"


def _search_with_serpapi(query: str, domains: list[str], max_results: int, timeout: float) -> tuple[list[dict[str, str]], str]:
    api_key = os.getenv("SERPAPI_API_KEY", "").strip()
    if not api_key:
        return [], ""

    import requests

    response = requests.get(
        "https://serpapi.com/search.json",
        params={"engine": "google", "q": _make_domain_query(query, domains), "num": max_results, "api_key": api_key, "hl": "ko"},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    results = []
    for item in data.get("organic_results", []) or []:
        results.append({"title": _safe_str(item.get("title")), "url": _safe_str(item.get("link")), "snippet": _safe_str(item.get("snippet"))})
    return results, "serpapi"


def _search_with_bing(query: str, domains: list[str], max_results: int, timeout: float) -> tuple[list[dict[str, str]], str]:
    api_key = os.getenv("BING_SEARCH_API_KEY", "").strip()
    endpoint = os.getenv("BING_SEARCH_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search").strip()
    if not api_key:
        return [], ""

    import requests

    response = requests.get(
        endpoint,
        headers={"Ocp-Apim-Subscription-Key": api_key},
        params={"q": _make_domain_query(query, domains), "count": max_results, "mkt": "ko-KR"},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    results = []
    for item in (data.get("webPages") or {}).get("value", []) or []:
        results.append({"title": _safe_str(item.get("name")), "url": _safe_str(item.get("url")), "snippet": _safe_str(item.get("snippet"))})
    return results, "bing"


def _search_with_naver(query: str, domains: list[str], max_results: int, timeout: float) -> tuple[list[dict[str, str]], str]:
    client_id = os.getenv("NAVER_CLIENT_ID", "").strip()
    client_secret = os.getenv("NAVER_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return [], ""

    import requests

    response = requests.get(
        "https://openapi.naver.com/v1/search/webkr.json",
        headers={"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret},
        params={"query": _make_domain_query(query, domains), "display": max_results, "sort": "sim"},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    results = []
    for item in data.get("items", []) or []:
        title = re.sub(r"<.*?>", "", _safe_str(item.get("title")))
        snippet = re.sub(r"<.*?>", "", _safe_str(item.get("description")))
        results.append({"title": html.unescape(title), "url": _safe_str(item.get("link")), "snippet": html.unescape(snippet)})
    return results, "naver"


def _search_with_duckduckgo_html(query: str, domains: list[str], max_results: int, timeout: float) -> tuple[list[dict[str, str]], str]:
    if os.getenv("ENABLE_DDG_HTML_SEARCH", "true").lower() not in {"true", "1", "yes", "y"}:
        return [], ""

    import requests

    response = requests.get(
        "https://duckduckgo.com/html/",
        params={"q": _make_domain_query(query, domains)},
        headers={"User-Agent": "Mozilla/5.0 (compatible; YouthPolicyRAG/1.0)"},
        timeout=timeout,
    )
    response.raise_for_status()
    parser = _DDGHTMLParser()
    parser.feed(response.text)
    return parser.results[:max_results], "duckduckgo_html"


def _run_search_backends(query: str, domains: list[str], max_results: int, timeout: float) -> tuple[list[dict[str, str]], str, list[str]]:
    errors: list[str] = []
    backends = [
        _search_with_tavily,
        _search_with_brave,
        _search_with_serpapi,
        _search_with_bing,
        _search_with_naver,
        _search_with_duckduckgo_html,
    ]

    for backend in backends:
        try:
            results, backend_name = backend(query, domains, max_results, timeout)
            if results:
                return results, backend_name, errors
        except Exception as exc:
            errors.append(f"{backend.__name__}: {repr(exc)}")

    return [], "", errors[:3]


def search_official_external_sources(
    query: str | None = None,
    user_conditions: dict[str, Any] | None = None,
    route: str | None = None,
    filters: dict[str, Any] | None = None,
    sufficiency_reasons: list[str] | None = None,
    max_results: int = 3,
    timeout: float = 5.0,
    **kwargs: Any,
) -> dict[str, Any]:
    """공식 도메인으로 제한된 외부 웹 검색을 수행하고, 결과를 RAG 후보 형식으로 반환한다."""
    if query is None:
        query = kwargs.get("user_query") or kwargs.get("message") or ""

    plan = plan_official_external_search(
        query=query,
        user_conditions=user_conditions,
        route=route,
        filters=filters,
        sufficiency_reasons=sufficiency_reasons,
    )

    if os.getenv("EXTERNAL_WEB_SEARCH_ENABLED", "true").lower() not in {"true", "1", "yes", "y"}:
        return {**plan, "results": [], "external_used": False, "backend": "disabled"}

    # 먼저 넓게 수집한 뒤, 후처리 점수로 재정렬한다.
    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    filtered_out: list[dict[str, Any]] = []
    backend_used = ""
    backend_errors: list[str] = []

    targets = plan.get("targets") or []
    queries = plan.get("queries") or [_safe_str(query)]
    per_query_results = max(5, max_results)

    for target in targets:
        domains = list(target.get("allowed_domains") or [])
        if not domains:
            continue
        # 확장 검색어까지 보되, 크레딧 과소비를 막기 위해 상위 5개까지만 사용한다.
        for search_query in queries[:5]:
            raw_results, backend, errors = _run_search_backends(search_query, domains, max_results=per_query_results, timeout=timeout)
            backend_errors.extend(errors)
            if backend and not backend_used:
                backend_used = backend

            for original_rank, raw in enumerate(raw_results):
                url = _clean_result_url(_safe_str(raw.get("url")))
                raw["url"] = url
                title = _safe_str(raw.get("title"))
                normalized_title = _normalize_text_for_match(title)[:120]
                if not url or url in seen_urls:
                    continue
                if normalized_title and normalized_title in seen_titles:
                    filtered_out.append({"title": title, "url": url, "reason": ["중복 제목 제외"]})
                    continue
                if not _allowed_domain(url, domains):
                    continue

                quality = _evaluate_external_result(raw, target=target, query=search_query)
                if not quality.get("usable"):
                    filtered_out.append({
                        "title": title,
                        "url": url,
                        "reason": quality.get("reject_reasons") or [],
                        "matched_terms": quality.get("matched_terms") or [],
                    })
                    continue

                seen_urls.add(url)
                if normalized_title:
                    seen_titles.add(normalized_title)
                quality["original_rank"] = original_rank
                candidates.append({"raw": dict(raw), "target": target, "query": search_query, "backend": backend or backend_used or "unknown", "quality": quality})

    # 품질 점수 우선, 원래 검색 순위 보조로 정렬한다.
    candidates.sort(
        key=lambda row: (
            float((row.get("quality") or {}).get("ranking_score") or 0.0),
            -int((row.get("quality") or {}).get("original_rank") or 0),
        ),
        reverse=True,
    )

    results: list[dict[str, Any]] = []
    for rank, row in enumerate(candidates[:max_results]):
        results.append(_result_to_policy_item(
            row["raw"],
            target=row["target"],
            query=row["query"],
            rank=rank,
            backend=row.get("backend") or backend_used or "unknown",
            quality=row.get("quality") or {},
        ))

    if results:
        return {
            **plan,
            "status": "executed",
            "external_used": True,
            "results": results,
            "backend": backend_used or "unknown",
            "errors": backend_errors[:3],
            "post_filter": {
                "filtered_out_count": len(filtered_out),
                "filtered_out_samples": filtered_out[:5],
                "accepted_count": len(results),
                "candidate_count_before_rerank": len(candidates),
                "reranked_titles": [item.get("policy_name") for item in results[:max_results]],
                "reranked_scores": [item.get("score") for item in results[:max_results]],
            },
            "message": "공식 도메인 제한 외부 웹 검색 결과를 가져왔습니다. 후처리 필터와 재정렬을 통과한 결과만 후보로 사용됩니다.",
        }

    return {
        **plan,
        "status": "planned_not_executed",
        "external_used": False,
        "results": [],
        "backend": backend_used or "none",
        "errors": backend_errors[:3],
        "post_filter": {
            "filtered_out_count": len(filtered_out),
            "filtered_out_samples": filtered_out[:5],
            "accepted_count": 0,
            "candidate_count_before_rerank": 0,
        },
        "message": "공식 도메인 제한 외부 웹 검색을 시도했지만 후처리 필터를 통과한 결과가 없어 검색 계획만 반환합니다.",
    }

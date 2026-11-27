"""온통청년 공식 Open API에서 모든 분야의 정책 원본 전량을 수집한다 (포트폴리오 p.12).

실행: interview-practice 폴더에서 python collect_youth_policies.py
환경: YOUTH_POLICY_API_KEY를 환경변수 또는 이 폴더의 .env에 설정한다.
출력: data/youth_policies_raw.json. policies에는 API의 정책 객체를 그대로 넣고,
수집 시각·출처·페이지 수·분야별 분포은 별도의 collection 필드에 기록한다.
"""

import json
import os
from collections import Counter
from time import sleep
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "data" / "youth_policies_raw.json"
ENDPOINT = "https://www.youthcenter.go.kr/go/ythip/getPlcy"
SPEC = "https://www.youthcenter.go.kr/cmnFooter/openapiIntro/oaiDoc/86"
# 한 번의 요청 크기이며 전체 수집 건수에는 상한을 두지 않는다.
PAGE_SIZE = 100
KST = timezone(timedelta(hours=9))


def fetch_page(session, api_key, page):
    """분야 필터 없이 한 페이지의 원본과 공식 응답의 pagging 정보를 읽는다."""
    params = {"apiKeyNm": api_key, "rtnType": "json", "pageNum": page, "pageSize": PAGE_SIZE}
    for attempt in range(3):
        try:
            response = session.get(ENDPOINT, params=params, timeout=(10, 45), allow_redirects=False)
        except requests.RequestException as error:
            if attempt == 2:
                # 예외의 요청 URL에는 인증키가 들어가므로 그대로 출력하지 않는다.
                raise RuntimeError(f"{page}쪽 연결 실패 ({type(error).__name__})") from None
            sleep(2 ** (attempt + 1))
            continue
        if response.status_code == 200:
            break
        if response.status_code not in (429, 500, 502, 503, 504) or attempt == 2:
            raise RuntimeError(f"{page}쪽 HTTP {response.status_code}")
        retry_after = response.headers.get("Retry-After", "")
        sleep(int(retry_after) if retry_after.isdigit() else 2 ** (attempt + 1))

    payload = response.json()
    if str(payload.get("resultCode")) != "200":
        raise RuntimeError(f"{page}쪽 API 응답 코드 {payload.get('resultCode')}")
    result = payload["result"]
    return result["youthPolicyList"], result["pagging"]  # pagging은 공식 필드명


def collect(session, api_key):
    """분야나 건수로 잘라내지 않고 서버가 보고한 마지막 페이지까지 원본을 모은다."""
    started = datetime.now(KST)
    policies = []
    expected_total = None
    page = 1
    while True:
        rows, paging = fetch_page(session, api_key, page)
        total = int(paging["totCount"])
        page_size = int(paging["pageSize"])
        if expected_total is None:
            expected_total = total
        if total != expected_total or int(paging["pageNum"]) != page or page_size != PAGE_SIZE:
            raise RuntimeError(f"{page}쪽에서 전체 건수 또는 페이지 정보가 달라졌습니다.")
        expected_rows = min(page_size, total - (page - 1) * page_size)
        if len(rows) != expected_rows:
            raise RuntimeError(f"{page}쪽 응답 건수 불일치: 예상 {expected_rows}, 수신 {len(rows)}")
        policies.extend(rows)
        print(f"{page}쪽: 누적 {len(policies):,} / {total:,}건", flush=True)
        if len(policies) == total:
            break
        page += 1
        sleep(1)

    ids = {row["plcyNo"] for row in policies}
    if not ids or not all(ids) or len(ids) != expected_total:
        raise RuntimeError("정책번호 누락·중복 또는 빈 응답으로 전체 수집을 확인할 수 없습니다.")
    # 분류값은 통계에만 사용하고 policies에 담긴 원본 객체에는 손대지 않는다.
    counts = Counter(row.get("lclsfNm") or "(미기재)" for row in policies)
    return {
        "collection": {
            "source": "한국고용정보원 온통청년 청년정책 Open API",
            "endpoint": ENDPOINT, "spec_url": SPEC,
            "started_at": started.isoformat(timespec="seconds"),
            "collected_at": datetime.now(KST).isoformat(timespec="seconds"),
            "selection": "분야 필터 및 건수 제한 없이 전체 페이지 수집",
            "page_size": PAGE_SIZE, "pages_read": page, "api_total": expected_total,
            "categories": dict(counts), "count": len(policies),
        },
        "policies": policies,
    }


def main():
    """전체 수집 성공 후에만 임시 파일을 최종 JSON으로 교체한다."""
    load_dotenv(ROOT / ".env", encoding="utf-8-sig")
    key = os.getenv("YOUTH_POLICY_API_KEY")
    if not key:
        raise SystemExit("YOUTH_POLICY_API_KEY를 설정하세요.")
    with requests.Session() as session:
        snapshot = collect(session, key)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=OUTPUT.parent, suffix=".tmp", delete=False) as temp:
        temp_path = Path(temp.name)
    try:
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(snapshot, file, ensure_ascii=False, indent=2)
            file.write("\n")
        temp_path.replace(OUTPUT)
    finally:
        temp_path.unlink(missing_ok=True)
    print(f"{len(snapshot['policies'])}건 저장 완료: {OUTPUT}")


if __name__ == "__main__":
    main()

import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv


load_dotenv()

API_KEY = os.getenv("YOUTH_API_KEY")

BASE_URL = "https://www.youthcenter.go.kr/go/ythip/getPlcy"

PAGE_SIZE = 100
OUTPUT_PATH = "./data/youth_policy.csv"


def find_policy_list(data):
    """
    API 응답 구조가 확실하지 않을 때,
    JSON 내부에서 정책 목록으로 보이는 list를 자동 탐색한다.
    """
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        candidate_keys = [
            "result",
            "data",
            "items",
            "item",
            "list",
            "policyList",
            "plcyList",
            "youthPolicyList",
        ]

        for key in candidate_keys:
            if key in data and isinstance(data[key], list):
                return data[key]

        for value in data.values():
            found = find_policy_list(value)
            if found:
                return found

    return []


def request_page(page_num):
    params = {
        "apiKeyNm": API_KEY,
        "pageNum": page_num,
        "pageSize": PAGE_SIZE,
        "rtnType": "json",
    }

    response = requests.get(BASE_URL, params=params, timeout=20)

    print(f"[요청] page={page_num}, status={response.status_code}")

    response.raise_for_status()

    return response.json()


def collect_all_policies():
    if not API_KEY:
        raise ValueError(".env 파일에 YOUTH_API_KEY가 없습니다.")

    all_rows = []
    page_num = 1

    while True:
        data = request_page(page_num)
        rows = find_policy_list(data)

        if not rows:
            print(f"[종료] page={page_num}에서 데이터 없음")
            break

        print(f"[수집] page={page_num}, rows={len(rows)}")

        all_rows.extend(rows)

        if len(rows) < PAGE_SIZE:
            print("[종료] 마지막 페이지로 판단")
            break

        page_num += 1
        time.sleep(0.2)

    return all_rows


def save_to_csv(rows):
    if not rows:
        print("저장할 데이터가 없습니다.")
        return

    df = pd.json_normalize(rows)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print(f"[완료] CSV 저장: {OUTPUT_PATH}")
    print(f"[완료] 총 {len(df)}건 저장")
    print(f"[컬럼] {list(df.columns)}")


if __name__ == "__main__":
    rows = collect_all_policies()
    save_to_csv(rows)
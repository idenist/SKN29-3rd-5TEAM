#!/usr/bin/env python3
"""
온통청년 API 수집 스크립트 자리.

MVP 산출물에서는 이미 수집된 CSV를
- data/raw/youthcenter_api/youth_policy_raw.csv
에 보존한다.

실제 API 키 기반 재수집이 필요할 경우 이 파일에 requests 로직을 추가한다.
원본 파일을 덮어쓰기 전에는 반드시 별도 백업 파일을 만든다.
"""
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT_DIR / "data" / "raw" / "youthcenter_api"


def main() -> None:
    print("현재 MVP에서는 업로드/수집 완료된 원본 CSV를 사용합니다.")
    print(f"원본 데이터 위치: {RAW_DIR / 'youth_policy_raw.csv'}")


if __name__ == "__main__":
    main()

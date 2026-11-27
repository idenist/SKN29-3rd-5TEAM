"""실험 설정과 API 연결 (p.9~12).

main과 workflow가 읽는 실행 조건, indexing과 뷰어가 공유하는 DB 위치를 정의한다.
질문·날짜·후보 수를 바꾸면 같은 데이터로 분기를 비교할 수 있다. 키는 실습 .env에서 읽는다.
설정값만으로 임베딩 모델 변경 전후의 벡터 호환성을 검사하지 않는다.
"""

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


PRACTICE_DIR = Path(__file__).resolve().parent
DB_PATH = str(PRACTICE_DIR / "practice_vector_db")
DATASET = "extended"  # "sample"은 기존 3정책, "extended"는 온통청년 전량 실습
COLLECTIONS = {"sample": "youth_policy", "extended": "youth_policy_extended"}
EMBEDDING_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"

QUERY = "서울에 사는 28세 청년인데 월세 지원 정책 알려줘"
AS_OF = None  # None은 실행 당일. 과거 실험은 datetime.date(2026, 6, 1) 등으로 지정한다.
FETCH_K = 80  # 최초 검색 청크 수. 조건 탈락·정책 중복을 고려해 여유 있게 가져온다.
TOP_K = 5  # 정리한 정책 중 답변에 사용할 최대 개수. 두 수의 최적성은 검증하지 않았다.
FILTER_MODE = "post"  # "pre"는 조건에 맞을 수 있는 정책 ID로 검색 범위를 먼저 제한한다.
UPDATE_INDEX = False  # sample 전용. extended는 main에서 조회만 한다.
RUN_EVALUATION = True  # 답변 생성이 끝난 뒤 평가 모델을 한 번 더 호출한다.
VERBOSE = False  # True는 검색된 청크 ID·유사도와 최종 State의 키도 출력한다.

load_dotenv(PRACTICE_DIR / ".env")


@lru_cache(maxsize=1)
def get_openai_client():
    """처음 API가 필요해질 때 환경의 키로 클라이언트를 만들고 이후 호출에서 재사용한다.

    인자는 없고 OpenAI 클라이언트를 반환한다. 모듈 읽기와 DB 조회에는 키가 필요 없다.
    실제 모델 호출에는 유효한 OPENAI_API_KEY와 네트워크 연결이 필요하다.
    """
    return OpenAI()

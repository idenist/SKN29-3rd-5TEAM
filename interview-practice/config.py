"""실험 설정과 API 연결 (p.9~12).

main과 workflow가 읽는 실행 조건, indexing과 뷰어가 공유하는 DB 위치를 정의한다.
질문·날짜·후보 수를 바꾸면 같은 데이터로 분기를 비교할 수 있다. 키는 실습 .env에서 읽는다."""

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


PRACTICE_DIR = Path(__file__).resolve().parent
DB_PATH = str(PRACTICE_DIR / "practice_vector_db")
COLLECTION_NAME = "youth_policy"
EMBEDDING_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"

QUERY = "월세 지원 정책 알려줘"
AS_OF = None  # None은 실행 당일. 과거 실험은 datetime.date(2026, 6, 1) 등으로 지정한다.
FETCH_K = 4  # 필터링 전 검색할 청크 수. 중복 제거 후의 정책 수와 다를 수 있다.
UPDATE_INDEX = False  # 빈 컬렉션은 최초 적재. True는 현재 청크 ID들을 다시 upsert한다.
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

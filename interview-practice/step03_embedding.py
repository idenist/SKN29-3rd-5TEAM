from openai import OpenAI
from dotenv import load_dotenv

# 1. OpenAI 클라이언트 생성
load_dotenv()
client = OpenAI()

# 2. 정책 데이터 정의
policy = {
    "item_id": "policy_001",
    "title": "2026년 서울시 청년월세지원",
    "document": "서울 청년의 주거비 부담을 줄이기 위해 월세를 월 최대 20만 원씩 12개월 동안 지원하는 사업",
    "metadata": {
        "age_min": 19,
        "age_max": 39,
        "region": "서울",
        "domain": "주거",
        "application_end_date": "2026-05-19"
    }
}

# 3. 청킹 및 메타데이터 연결
chunks = [
    {
        "chunk_id": "policy_001::summary",
        "item_id": policy["item_id"],
        "document": policy["document"],
        "metadata": policy["metadata"].copy()
    },
    {
        "chunk_id": "policy_001::eligibility",
        "item_id": policy["item_id"],
        "document": "서울시 청년월세지원 사업의 신청 대상 연령은 19세 이상 39세 이하이며, 서울에 거주해야 한다.",
        "metadata": policy["metadata"].copy()
    }
]

# 4. 임베딩할 텍스트 추출
texts = [chunk["document"] for chunk in chunks]

# 5. OpenAI 임베딩 API 호출
response = client.embeddings.create(
    model="text-embedding-3-small",
    input=texts
)

# 6. 각 청크에 임베딩 벡터 저장
for item in response.data:
    chunks[item.index]["embedding"] = item.embedding

# 7. 결과 확인
for chunk in chunks:
    print("청크 ID:", chunk["chunk_id"])
    print("본문:", chunk["document"])
    print("임베딩 차원:", len(chunk["embedding"]))
    print("벡터 앞 5개:", chunk["embedding"][:5])
    print("-" * 50)
    
    
import math

# 사용자 질문 임베딩
query = "몇 살부터 신청할 수 있어?"

response = client.embeddings.create(
    model="text-embedding-3-small",
    input=query
)

query_embedding = response.data[0].embedding


# 코사인 유사도 계산
def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x ** 2 for x in a))
    norm_b = math.sqrt(sum(y ** 2 for y in b))

    return dot / (norm_a * norm_b)


# 질문과 각 청크의 유사도 비교
for chunk in chunks:
    score = cosine_similarity(
        query_embedding,
        chunk["embedding"]
    )

    print(chunk["chunk_id"], score)
"""실습에 사용할 정책 세 건 (p.9~10, p.12).

입력 원본은 이 목록이다. main이 POLICIES를 indexing.build_chunks에 전달하면 네 청크가 된다.
나중에 같은 키를 갖춘 JSON 레코드를 읽어 넘겨도 청킹·검색 함수의 인터페이스는 같다.
"""

POLICIES = [
    {
        "item_id": "policy_001",
        "title": "2026년 서울시 청년월세지원",
        "documents": {
            "summary": (
                "서울 청년의 주거비 부담을 줄이기 위해 "
                "월세를 월 최대 20만 원씩 12개월 동안 지원하는 사업"
            ),
            "eligibility": (
                "서울시 청년월세지원 사업의 신청 대상 연령은 "
                "19세 이상 39세 이하이며, 서울에 거주해야 한다."
            )
        },
        "metadata": {
            "age_min": 19,
            "age_max": 39,
            "region": "서울",
            "domain": "주거",
            "application_end_date": "2026-05-19"
        }
    },
    {
        "item_id": "policy_002",
        "title": "2026년 대전시 청년월세지원",
        "documents": {
            "summary": (
                "대전시 거주 19~39세 무주택 청년에게 "
                "월세를 월 최대 20만 원씩 12개월 지원하는 사업"
            )
        },
        "metadata": {
            "age_min": 19,
            "age_max": 39,
            "region": "대전",
            "domain": "주거",
            "application_end_date": "2026-09-10"
        }
    },
    {
        "item_id": "policy_003",
        "title": "2026년 서울시 청년수당",
        "documents": {
            "summary": (
                "서울시 거주 19~34세 미취업 청년에게 "
                "활동지원금을 월 50만 원씩 최대 6개월 지급하는 청년수당 사업"
            )
        },
        "metadata": {
            "age_min": 19,
            "age_max": 34,
            "region": "서울",
            "domain": "일자리",
            "application_end_date": "2026-05-29"
        }
    }
]

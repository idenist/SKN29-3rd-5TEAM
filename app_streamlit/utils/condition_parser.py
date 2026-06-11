import re


def parse_user_query(query: str):
    result = {
        "age": None,
        "region": None,
        "income": None,
        "job_status": None,
        "interest": []
    }

    age_match = re.search(r"(\d{2})\s*살", query)
    if age_match:
        result["age"] = int(age_match.group(1))

    income_match = re.search(r"연소득\s*(\d+)", query)
    if income_match:
        result["income"] = int(income_match.group(1))

    regions = ["서울", "부산", "대구", "인천", "광주", "대전", "경기"]
    for region in regions:
        if region in query:
            result["region"] = region
            break

    if "중소기업" in query:
        result["job_status"] = "중소기업 재직자"
    elif "취준" in query or "취업준비" in query:
        result["job_status"] = "구직자"
    elif "창업" in query:
        result["job_status"] = "예비창업자"

    for field in ["취업", "금융", "주거", "교육", "창업"]:
        if field in query:
            result["interest"].append(field)

    if any(keyword in query for keyword in ["월세", "전세", "주택", "주거비"]):
        if "주거" not in result["interest"]:
            result["interest"].append("주거")

    return result

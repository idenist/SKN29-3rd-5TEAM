def get_status_badge(status):
    if status == "신청 가능":
        return "badge-green"
    if status == "조건 확인 필요":
        return "badge-orange"
    if status == "마감 임박":
        return "badge-red"
    return "badge-blue"


def recommend_policies(policies, user_profile):
    sorted_policies = sorted(
        policies,
        key=lambda x: int(x["score"]),
        reverse=True
    )
    return sorted_policies


def check_conditions(policy, user_profile):
    return [
        {
            "label": "나이",
            "user": f"만 {user_profile.get('age')}세",
            "policy": policy["age"],
            "result": "충족",
            "class": "condition-ok"
        },
        {
            "label": "지역",
            "user": user_profile.get("region"),
            "policy": policy["region"],
            "result": "충족" if policy["region"] in ["전국", user_profile.get("region")] else "확인 필요",
            "class": "condition-ok" if policy["region"] in ["전국", user_profile.get("region")] else "condition-warn"
        },
        {
            "label": "소득",
            "user": f"{user_profile.get('income')}만원",
            "policy": policy["income"],
            "result": "확인 필요" if "중위소득" in policy["income"] else "충족",
            "class": "condition-warn" if "중위소득" in policy["income"] else "condition-ok"
        },
        {
            "label": "현재 상태",
            "user": user_profile.get("job_status"),
            "policy": policy["job_status"],
            "result": "충족" if user_profile.get("job_status") in policy["job_status"] or policy["job_status"] == "무관" else "확인 필요",
            "class": "condition-ok" if user_profile.get("job_status") in policy["job_status"] or policy["job_status"] == "무관" else "condition-warn"
        }
    ]
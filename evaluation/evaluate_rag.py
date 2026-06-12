"""
청년 정책 RAG 서비스 평가 스크립트.

기본 사용법:
    python evaluation/evaluate_rag.py --base-url http://127.0.0.1:8000 --endpoint /chat

/api/chat을 쓰는 프로젝트라면:
    python evaluation/evaluate_rag.py --base-url http://127.0.0.1:8000 --endpoint /api/chat

결과:
    evaluation/result/evaluation_results.json
    evaluation/result/evaluation_results.md
    evaluation/result/judge_inputs.jsonl  # 선택: --write-judge-inputs 사용 시 생성
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import request, error

try:
    from llm_judge_prompt import build_judge_prompt
except Exception:
    build_judge_prompt = None


@dataclass
class EvalResult:
    case_id: str
    query: str
    passed: bool
    score: float
    checks: dict[str, Any]
    response: dict[str, Any]
    error: str | None = None


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    cases = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"JSONL 파싱 실패: {path}:{line_no}: {e}") from e
    return cases


def post_chat(base_url: str, endpoint: str, message: str, top_k: int, timeout: int) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/" + endpoint.strip("/")
    payload = json.dumps({"message": message, "top_k": top_k}, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body}") from e
    except Exception as e:
        raise RuntimeError(str(e)) from e


def normalize_text(value: Any) -> str:
    return str(value or "").lower().replace(" ", "")


def contains_any(text: str, keywords: list[str] | None) -> bool:
    if not keywords:
        return True
    compact = normalize_text(text)
    return any(normalize_text(k) in compact for k in keywords)


def contains_none(text: str, keywords: list[str] | None) -> bool:
    if not keywords:
        return True
    compact = normalize_text(text)
    return all(normalize_text(k) not in compact for k in keywords)


def response_text_blob(response: dict[str, Any]) -> str:
    return json.dumps(response, ensure_ascii=False)


def get_recommendations(response: dict[str, Any]) -> list[dict[str, Any]]:
    recs = response.get("recommendations") or []
    return recs if isinstance(recs, list) else []


def count_expired_recommendations(recommendations: list[dict[str, Any]]) -> int:
    count = 0
    for rec in recommendations:
        status = str(rec.get("deadline_status") or "").lower()
        is_expired = rec.get("is_expired")
        if status == "expired" or is_expired is True or str(is_expired).lower() == "true":
            count += 1
    return count


def route_matches(actual: str, expected: str | None) -> bool:
    if not expected:
        return True
    return normalize_text(expected) in normalize_text(actual)


def value_matches_any(actual: Any, expected_any: list[Any] | None) -> bool:
    if not expected_any:
        return True
    return any(actual == expected for expected in expected_any)


def evaluate_case(case: dict[str, Any], response: dict[str, Any]) -> EvalResult:
    checks: dict[str, Any] = {}
    blob = response_text_blob(response)
    answer = response.get("answer", "")
    recs = get_recommendations(response)

    checks["must_have_any"] = contains_any(blob, case.get("must_have_any"))
    checks["must_not_have_any"] = contains_none(blob, case.get("must_not_have_any"))

    expected_route = case.get("expected_route")
    checks["route"] = route_matches(response.get("route", ""), expected_route)

    expected_sufficient = case.get("expected_internal_search_sufficient")
    checks["internal_search_sufficient"] = (
        True if expected_sufficient is None else response.get("internal_search_sufficient") == expected_sufficient
    )

    expected_next = case.get("expected_next_action")
    expected_next_any = case.get("expected_next_action_any")
    if expected_next:
        checks["next_action"] = response.get("next_action") == expected_next
    else:
        checks["next_action"] = value_matches_any(response.get("next_action"), expected_next_any)

    expected_external_used = case.get("expected_external_used")
    checks["external_used"] = (
        True if expected_external_used is None else response.get("external_used") == expected_external_used
    )

    expected_external_status = case.get("expected_external_search_status")
    checks["external_search_status"] = (
        True if expected_external_status is None else response.get("external_search_status") == expected_external_status
    )

    expected_targets_any = case.get("expected_external_search_targets_any")
    actual_targets = response.get("external_search_targets") or []
    checks["external_search_targets"] = (
        True
        if not expected_targets_any
        else any(target in actual_targets for target in expected_targets_any)
    )

    min_recs = case.get("min_recommendations")
    max_recs = case.get("max_recommendations")
    checks["min_recommendations"] = True if min_recs is None else len(recs) >= int(min_recs)
    checks["max_recommendations"] = True if max_recs is None else len(recs) <= int(max_recs)

    allow_expired = bool(case.get("allow_expired", True))
    expired_count = count_expired_recommendations(recs)
    checks["no_expired_recommendations"] = True if allow_expired else expired_count == 0

    expected_warning_any = case.get("expected_warning_any")
    warnings_blob = "\n".join(response.get("warnings") or [])
    checks["expected_warning_any"] = contains_any(warnings_blob, expected_warning_any)

    expected_error_any = case.get("expected_error_any")
    # API 응답 스키마에 errors가 없는 경우 answer/warnings까지 함께 확인한다.
    err_blob = "\n".join(response.get("errors") or []) + "\n" + warnings_blob + "\n" + str(answer)
    checks["expected_error_any"] = contains_any(err_blob, expected_error_any)

    # ReAct trace 기본 품질 확인
    trace = response.get("tool_trace") or []
    checks["tool_trace_present_when_needed"] = True
    if case.get("intent") not in {"empty_query_validation"}:
        checks["tool_trace_present_when_needed"] = isinstance(trace, list) and len(trace) >= 2

    passed_count = sum(1 for ok in checks.values() if ok)
    total_count = len(checks)
    score = passed_count / total_count if total_count else 0.0
    passed = all(checks.values())

    return EvalResult(
        case_id=case.get("id", "unknown"),
        query=case.get("query", ""),
        passed=passed,
        score=score,
        checks=checks,
        response=response,
    )


def write_results_json(results: list[EvalResult], output_path: Path) -> None:
    data = [
        {
            "case_id": r.case_id,
            "query": r.query,
            "passed": r.passed,
            "score": round(r.score, 4),
            "checks": r.checks,
            "error": r.error,
            "response": r.response,
        }
        for r in results
    ]
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_results_md(results: list[EvalResult], output_path: Path) -> None:
    pass_count = sum(1 for r in results if r.passed)
    avg_score = statistics.mean([r.score for r in results]) if results else 0.0

    lines = []
    lines.append("# RAG 평가 결과")
    lines.append("")
    lines.append(f"- 총 케이스 수: {len(results)}")
    lines.append(f"- 통과 케이스 수: {pass_count}")
    lines.append(f"- 통과율: {pass_count / len(results) * 100:.1f}%" if results else "- 통과율: 0.0%")
    lines.append(f"- 평균 규칙 기반 점수: {avg_score:.3f}")
    lines.append("")
    lines.append("## 케이스별 결과")
    lines.append("")
    lines.append("| ID | Pass | Score | Query | 실패 항목 |")
    lines.append("|---|---:|---:|---|---|")
    for r in results:
        failed = [name for name, ok in r.checks.items() if not ok]
        failed_text = ", ".join(failed) if failed else "-"
        query = r.query.replace("|", "\\|")
        lines.append(f"| {r.case_id} | {'✅' if r.passed else '❌'} | {r.score:.3f} | {query} | {failed_text} |")

    lines.append("")
    lines.append("## 해석 가이드")
    lines.append("")
    lines.append("- 규칙 기반 점수는 route, next_action, 마감 공고 배제, recommendations 개수, ReAct trace 존재 여부 등을 자동 점검한 값이다.")
    lines.append("- LLM-as-a-Judge 평가는 judge_inputs.jsonl을 사용해 context_relevance, groundedness, answer_relevance, freshness_safety, react_trace_quality를 별도로 채점한다.")
    lines.append("- 자동 점수에서 실패한 케이스는 Swagger 응답의 tool_trace와 recommendations를 함께 확인한다.")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_judge_inputs(cases: list[dict[str, Any]], results: list[EvalResult], output_path: Path) -> None:
    if build_judge_prompt is None:
        raise RuntimeError("llm_judge_prompt.py를 import할 수 없습니다.")

    case_by_id = {case.get("id"): case for case in cases}
    with output_path.open("w", encoding="utf-8") as f:
        for result in results:
            case = case_by_id.get(result.case_id, {})
            messages = build_judge_prompt(
                query=result.query,
                expected_behavior=case.get("expected_behavior", ""),
                judge_focus=case.get("judge_focus", []),
                response_json=json.dumps(result.response, ensure_ascii=False, indent=2),
            )
            row = {
                "id": result.case_id,
                "query": result.query,
                "messages": messages,
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def resolve_output_path(output_dir: Path, value: str) -> Path:
    """
    결과 파일 경로를 결정한다.

    - 기본값처럼 파일명만 들어오면 evaluation/result 아래에 생성한다.
    - 사용자가 하위 경로를 직접 넘기면 그 경로를 존중한다.
    - 절대 경로도 그대로 사용한다.
    """
    path = Path(value)
    if path.is_absolute() or len(path.parts) > 1:
        return path
    return output_dir / path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="evaluation_dataset.jsonl", help="평가 JSONL 경로")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="FastAPI 서버 주소")
    parser.add_argument("--endpoint", default="/chat", help="채팅 API endpoint: /chat 또는 /api/chat")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument(
        "--output-dir",
        default="evaluation/result",
        help="평가 결과 산출물 저장 디렉터리",
    )
    parser.add_argument("--output-json", default="evaluation_results.json")
    parser.add_argument("--output-md", default="evaluation_results.md")
    parser.add_argument("--write-judge-inputs", action="store_true")
    parser.add_argument("--judge-inputs", default="judge_inputs.jsonl")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    cases = load_jsonl(dataset_path)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_json_path = resolve_output_path(output_dir, args.output_json)
    output_md_path = resolve_output_path(output_dir, args.output_md)
    judge_inputs_path = resolve_output_path(output_dir, args.judge_inputs)

    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_md_path.parent.mkdir(parents=True, exist_ok=True)
    if args.write_judge_inputs:
        judge_inputs_path.parent.mkdir(parents=True, exist_ok=True)

    results: list[EvalResult] = []
    for idx, case in enumerate(cases, start=1):
        case_id = case.get("id", f"case_{idx}")
        query = case.get("query", "")
        print(f"[{idx}/{len(cases)}] {case_id}: {query!r}")
        try:
            response = post_chat(args.base_url, args.endpoint, query, args.top_k, args.timeout)
            result = evaluate_case(case, response)
        except Exception as e:
            result = EvalResult(
                case_id=case_id,
                query=query,
                passed=False,
                score=0.0,
                checks={"request_success": False},
                response={},
                error=str(e),
            )
        results.append(result)

    write_results_json(results, output_json_path)
    write_results_md(results, output_md_path)

    if args.write_judge_inputs:
        write_judge_inputs(cases, results, judge_inputs_path)

    pass_count = sum(1 for r in results if r.passed)
    print(f"\n완료: {pass_count}/{len(results)} 통과")
    print(f"- Output dir: {output_dir}")
    print(f"- JSON: {output_json_path}")
    print(f"- MD: {output_md_path}")
    if args.write_judge_inputs:
        print(f"- Judge inputs: {judge_inputs_path}")

    return 0 if pass_count == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

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

평가 방식:
    1) 규칙 기반 평가: route, next_action, recommendations, 마감 공고 배제, ReAct trace 확인
    2) 텍스트 유사도 평가: evaluation_dataset.jsonl의 reference_answer와 실제 answer를 비교해 BLEU/ROUGE 계산
    3) LLM-as-a-Judge 입력 생성: --write-judge-inputs 사용 시 judge_inputs.jsonl 생성
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
    text_metrics: dict[str, Any] | None = None


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

def tokenize_for_metric(text: Any) -> list[str]:
    """BLEU/ROUGE 계산용 간단 토크나이저.

    외부 라이브러리 없이 실행되도록 한글/영문/숫자 토큰을 정규식으로 분리한다.
    형태소 분석 기반 지표는 아니므로, RAG 답변 품질의 보조 지표로만 사용한다.
    """
    return re.findall(r"[가-힣A-Za-z0-9]+", str(text or "").lower())


def _ngram_counts(tokens: list[str], n: int) -> dict[tuple[str, ...], int]:
    counts: dict[tuple[str, ...], int] = {}
    if n <= 0 or len(tokens) < n:
        return counts
    for i in range(len(tokens) - n + 1):
        gram = tuple(tokens[i : i + n])
        counts[gram] = counts.get(gram, 0) + 1
    return counts


def _safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def compute_bleu(candidate: str, reference: str, max_n: int = 4) -> float:
    """간단 BLEU 구현.

    - BLEU-1~4 modified precision의 기하평균을 사용한다.
    - 0점 방지를 위해 아주 작은 smoothing을 적용한다.
    """
    cand_tokens = tokenize_for_metric(candidate)
    ref_tokens = tokenize_for_metric(reference)

    if not cand_tokens or not ref_tokens:
        return 0.0

    precisions: list[float] = []
    smoothing = 1e-9

    for n in range(1, max_n + 1):
        cand_counts = _ngram_counts(cand_tokens, n)
        ref_counts = _ngram_counts(ref_tokens, n)
        if not cand_counts:
            precisions.append(smoothing)
            continue

        clipped = 0
        total = sum(cand_counts.values())
        for gram, count in cand_counts.items():
            clipped += min(count, ref_counts.get(gram, 0))
        precisions.append(max(_safe_div(clipped, total), smoothing))

    import math

    log_precision = sum(math.log(p) for p in precisions) / max_n
    brevity_penalty = 1.0
    if len(cand_tokens) < len(ref_tokens):
        brevity_penalty = math.exp(1 - len(ref_tokens) / max(len(cand_tokens), 1))

    return brevity_penalty * math.exp(log_precision)


def compute_rouge_n(candidate: str, reference: str, n: int = 1) -> dict[str, float]:
    cand_tokens = tokenize_for_metric(candidate)
    ref_tokens = tokenize_for_metric(reference)
    cand_counts = _ngram_counts(cand_tokens, n)
    ref_counts = _ngram_counts(ref_tokens, n)

    if not cand_counts or not ref_counts:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    overlap = 0
    for gram, ref_count in ref_counts.items():
        overlap += min(ref_count, cand_counts.get(gram, 0))

    precision = _safe_div(overlap, sum(cand_counts.values()))
    recall = _safe_div(overlap, sum(ref_counts.values()))
    f1 = _safe_div(2 * precision * recall, precision + recall)
    return {"precision": precision, "recall": recall, "f1": f1}


def _lcs_length(a: list[str], b: list[str]) -> int:
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for token_a in a:
        curr = [0] * (len(b) + 1)
        for j, token_b in enumerate(b, start=1):
            if token_a == token_b:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev = curr
    return prev[-1]


def compute_rouge_l(candidate: str, reference: str) -> dict[str, float]:
    cand_tokens = tokenize_for_metric(candidate)
    ref_tokens = tokenize_for_metric(reference)
    if not cand_tokens or not ref_tokens:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    lcs = _lcs_length(cand_tokens, ref_tokens)
    precision = _safe_div(lcs, len(cand_tokens))
    recall = _safe_div(lcs, len(ref_tokens))
    f1 = _safe_div(2 * precision * recall, precision + recall)
    return {"precision": precision, "recall": recall, "f1": f1}


def get_reference_answer(case: dict[str, Any]) -> str:
    """평가셋에서 기준 답변을 가져온다.

    지원 필드명:
    - reference_answer
    - expected_answer
    - reference
    - reference_answers: list[str]인 경우 첫 번째 값을 사용
    """
    for key in ("reference_answer", "expected_answer", "reference"):
        value = case.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    values = case.get("reference_answers")
    if isinstance(values, list):
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()

    return ""


def compute_text_metrics(candidate: str, reference: str) -> dict[str, Any]:
    if not reference.strip():
        return {
            "available": False,
            "reason": "reference_answer 필드가 없어 BLEU/ROUGE를 계산하지 않았습니다.",
        }

    rouge_1 = compute_rouge_n(candidate, reference, n=1)
    rouge_2 = compute_rouge_n(candidate, reference, n=2)
    rouge_l = compute_rouge_l(candidate, reference)

    return {
        "available": True,
        "bleu": round(compute_bleu(candidate, reference), 4),
        "rouge_1_f1": round(rouge_1["f1"], 4),
        "rouge_2_f1": round(rouge_2["f1"], 4),
        "rouge_l_f1": round(rouge_l["f1"], 4),
        "rouge_1": {k: round(v, 4) for k, v in rouge_1.items()},
        "rouge_2": {k: round(v, 4) for k, v in rouge_2.items()},
        "rouge_l": {k: round(v, 4) for k, v in rouge_l.items()},
    }



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

    reference_answer = get_reference_answer(case)
    text_metrics = compute_text_metrics(str(answer), reference_answer)

    return EvalResult(
        case_id=case.get("id", "unknown"),
        query=case.get("query", ""),
        passed=passed,
        score=score,
        checks=checks,
        response=response,
        text_metrics=text_metrics,
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
            "text_metrics": r.text_metrics or {"available": False},
            "response": r.response,
        }
        for r in results
    ]
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_results_md(results: list[EvalResult], output_path: Path) -> None:
    pass_count = sum(1 for r in results if r.passed)
    avg_score = statistics.mean([r.score for r in results]) if results else 0.0

    metric_results = [r.text_metrics or {} for r in results if (r.text_metrics or {}).get("available")]
    avg_bleu = statistics.mean([m["bleu"] for m in metric_results]) if metric_results else None
    avg_rouge_1 = statistics.mean([m["rouge_1_f1"] for m in metric_results]) if metric_results else None
    avg_rouge_2 = statistics.mean([m["rouge_2_f1"] for m in metric_results]) if metric_results else None
    avg_rouge_l = statistics.mean([m["rouge_l_f1"] for m in metric_results]) if metric_results else None

    lines = []
    lines.append("# RAG 평가 결과")
    lines.append("")
    lines.append(f"- 총 케이스 수: {len(results)}")
    lines.append(f"- 통과 케이스 수: {pass_count}")
    lines.append(f"- 통과율: {pass_count / len(results) * 100:.1f}%" if results else "- 통과율: 0.0%")
    lines.append(f"- 평균 규칙 기반 점수: {avg_score:.3f}")
    if metric_results:
        lines.append(f"- BLEU/ROUGE 계산 케이스 수: {len(metric_results)}")
        lines.append(f"- 평균 BLEU: {avg_bleu:.4f}")
        lines.append(f"- 평균 ROUGE-1 F1: {avg_rouge_1:.4f}")
        lines.append(f"- 평균 ROUGE-2 F1: {avg_rouge_2:.4f}")
        lines.append(f"- 평균 ROUGE-L F1: {avg_rouge_l:.4f}")
    else:
        lines.append("- BLEU/ROUGE: reference_answer이 없어 계산 생략")
    lines.append("")
    lines.append("## 케이스별 결과")
    lines.append("")
    lines.append("| ID | Pass | Rule Score | BLEU | ROUGE-L F1 | Query | 실패 항목 |")
    lines.append("|---|---:|---:|---:|---:|---|---|")
    for r in results:
        failed = [name for name, ok in r.checks.items() if not ok]
        failed_text = ", ".join(failed) if failed else "-"
        query = r.query.replace("|", "\\|")
        metrics = r.text_metrics or {}
        bleu_text = f"{metrics.get('bleu', 0.0):.4f}" if metrics.get("available") else "-"
        rouge_l_text = f"{metrics.get('rouge_l_f1', 0.0):.4f}" if metrics.get("available") else "-"
        lines.append(
            f"| {r.case_id} | {'✅' if r.passed else '❌'} | {r.score:.3f} | "
            f"{bleu_text} | {rouge_l_text} | {query} | {failed_text} |"
        )

    lines.append("")
    lines.append("## 해석 가이드")
    lines.append("")
    lines.append("- 규칙 기반 점수는 route, next_action, 마감 공고 배제, recommendations 개수, ReAct trace 존재 여부 등을 자동 점검한 값이다.")
    lines.append("- BLEU/ROUGE는 evaluation_dataset.jsonl의 reference_answer 또는 expected_answer가 있는 케이스에서만 계산된다.")
    lines.append("- 추천형 RAG에서는 같은 정책을 맞게 추천해도 문장 표현 차이로 BLEU/ROUGE가 낮을 수 있으므로 참고 지표로 사용한다.")
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
            reference_answer = get_reference_answer(case)
            try:
                messages = build_judge_prompt(
                    query=result.query,
                    expected_behavior=case.get("expected_behavior", ""),
                    judge_focus=case.get("judge_focus", []),
                    response_json=json.dumps(result.response, ensure_ascii=False, indent=2),
                    reference_answer=reference_answer,
                )
            except TypeError:
                # 이전 버전 llm_judge_prompt.py와도 호환
                messages = build_judge_prompt(
                    query=result.query,
                    expected_behavior=case.get("expected_behavior", ""),
                    judge_focus=case.get("judge_focus", []),
                    response_json=json.dumps(result.response, ensure_ascii=False, indent=2),
                )
            row = {
                "id": result.case_id,
                "query": result.query,
                "reference_answer": reference_answer,
                "text_metrics": result.text_metrics or {"available": False},
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

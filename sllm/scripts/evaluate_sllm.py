"""
파인튜닝 sLLM 간이 평가 스크립트.

정책 추천형 답변은 BLEU/ROUGE만으로 판단하기 어렵기 때문에,
- 생성 성공 여부
- reference keyword 포함 여부
- 출처/추가 확인 안내 포함 여부
- 평균 생성 길이
를 함께 기록한다.

사용 예:
python sllm/scripts/evaluate_sllm.py \
  --model sllm/outputs/lora_policy_qa \
  --eval-file sllm/data/policy_qa_eval_sample.jsonl \
  --output sllm/evaluation/sllm_eval_results.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def tokenize_words(text: str) -> list[str]:
    return re.findall(r"[가-힣A-Za-z0-9]+", text.lower())


def rouge_l_f1(pred: str, ref: str) -> float:
    a = tokenize_words(pred)
    b = tokenize_words(ref)
    if not a or not b:
        return 0.0

    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    lcs = dp[-1][-1]
    precision = lcs / len(a)
    recall = lcs / len(b)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def keyword_hit(pred: str, row: dict[str, Any]) -> bool:
    metadata = row.get("metadata") or {}
    candidates = [metadata.get("title", ""), metadata.get("source_category", ""), metadata.get("domain", "")]
    output = row.get("output", "")
    words = [w for w in tokenize_words(" ".join(candidates)) if len(w) >= 2]
    if not words:
        words = [w for w in tokenize_words(output) if len(w) >= 2][:5]
    return any(w in pred.lower() for w in words[:8])


def build_prompt(row: dict[str, Any], tokenizer) -> str:
    if row.get("messages"):
        messages = [m for m in row["messages"] if m.get("role") != "assistant"]
        try:
            return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        except Exception:
            pass
    return f"<|user|>\n{row.get('instruction', '')}\n\n{row.get('input', '')}\n<|assistant|>\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="LoRA adapter 경로 또는 merge된 모델 경로")
    parser.add_argument("--base-model", default=None, help="adapter만 있는 경우 원본 base model 경로")
    parser.add_argument("--eval-file", required=True)
    parser.add_argument("--output", default="sllm/evaluation/sllm_eval_results.json")
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    model_path = args.base_model or args.model
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        trust_remote_code=True,
        device_map="auto",
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
    )
    if args.base_model:
        model = PeftModel.from_pretrained(model, args.model)
    model.eval()

    rows = read_jsonl(Path(args.eval_file))[: args.limit]
    results = []

    for row in rows:
        prompt = build_prompt(row, tokenizer)
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=args.max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        generated = tokenizer.decode(output_ids[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True).strip()
        ref = row.get("output", "")
        results.append({
            "instruction": row.get("instruction"),
            "prediction": generated,
            "reference": ref,
            "rouge_l_f1": rouge_l_f1(generated, ref),
            "keyword_hit": keyword_hit(generated, row),
            "mentions_source_or_check": ("출처" in generated) or ("확인" in generated),
            "generated_length": len(generated),
        })

    summary = {
        "total": len(results),
        "avg_rouge_l_f1": sum(r["rouge_l_f1"] for r in results) / len(results) if results else 0,
        "keyword_hit_rate": sum(r["keyword_hit"] for r in results) / len(results) if results else 0,
        "source_or_check_rate": sum(r["mentions_source_or_check"] for r in results) / len(results) if results else 0,
        "avg_generated_length": sum(r["generated_length"] for r in results) / len(results) if results else 0,
    }

    out = {"summary": summary, "results": results}
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path = output_path.with_suffix(".md")
    md_path.write_text(
        "# sLLM 평가 결과\n\n"
        f"- 총 평가 수: {summary['total']}\n"
        f"- 평균 ROUGE-L F1: {summary['avg_rouge_l_f1']:.4f}\n"
        f"- 키워드 적중률: {summary['keyword_hit_rate']:.2%}\n"
        f"- 출처/확인 안내 포함률: {summary['source_or_check_rate']:.2%}\n"
        f"- 평균 생성 길이: {summary['avg_generated_length']:.1f}\n",
        encoding="utf-8",
    )
    print(f"saved: {output_path}")
    print(f"saved: {md_path}")


if __name__ == "__main__":
    main()

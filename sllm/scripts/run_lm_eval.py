"""
lm-evaluation-harness 실행 래퍼.

주의:
- 이 스크립트는 표준 벤치마크 또는 별도 task yaml이 준비되어 있을 때 사용한다.
- 정책 QA 서비스의 실제 품질 평가는 evaluate_sllm.py와 RAG LLM-as-a-Judge를 함께 보는 것이 더 적절하다.

사용 예:
python sllm/scripts/run_lm_eval.py \
  --model hf \
  --model-args pretrained=sllm/outputs/lora_policy_qa \
  --tasks kobest_boolq,kobest_hellaswag \
  --output-path sllm/evaluation/lm_eval_results.json
"""

from __future__ import annotations

import argparse
import subprocess


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="hf")
    parser.add_argument("--model-args", required=True)
    parser.add_argument("--tasks", required=True)
    parser.add_argument("--batch-size", default="auto")
    parser.add_argument("--output-path", default="sllm/evaluation/lm_eval_results.json")
    args = parser.parse_args()

    cmd = [
        "lm_eval",
        "--model", args.model,
        "--model_args", args.model_args,
        "--tasks", args.tasks,
        "--batch_size", args.batch_size,
        "--output_path", args.output_path,
    ]
    print("실행 명령:", " ".join(cmd))
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()

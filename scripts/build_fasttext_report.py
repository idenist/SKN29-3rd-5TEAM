import csv
import json
from pathlib import Path

DATA_PATH = Path("data/processed/opportunities_with_keywords.json")
REPORT_PATH = Path("data/reports/word2vec_fasttext_status_report.csv")

SEEDS = ["청년", "창업", "취업", "교육", "데이터"]

def load_tokens():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    docs = []

    for row in data:
        kws = row.get("noun_keywords") or row.get("filtered_keywords") or []
        if isinstance(kws, str):
            kws = [x.strip() for x in kws.replace("|", ",").split(",") if x.strip()]
        if isinstance(kws, list):
            toks = [str(x).strip() for x in kws if str(x).strip()]
            if len(toks) >= 2:
                docs.append(toks)

    return docs[:8000]

def read_existing_rows():
    if not REPORT_PATH.exists():
        return []

    rows = []
    with REPORT_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("model") != "FastText":
                rows.append(row)
    return rows

def main():
    rows = read_existing_rows()

    try:
        from gensim.models import FastText

        docs = load_tokens()
        if not docs:
            raise RuntimeError("학습 가능한 token 문서가 없습니다.")

        model = FastText(
            sentences=docs,
            vector_size=50,
            window=5,
            min_count=2,
            workers=2,
            sg=1,
            epochs=5,
        )

        for seed in SEEDS:
            if seed in model.wv:
                sims = model.wv.most_similar(seed, topn=5)
                similar_words = "|".join([f"{word}:{score:.3f}" for word, score in sims])
                rows.append({
                    "model": "FastText",
                    "status": "trained_sample",
                    "seed": seed,
                    "similar_words": similar_words,
                    "note": "평가/분석용 샘플 학습이며 서비스 검색에는 사용하지 않음",
                })
            else:
                rows.append({
                    "model": "FastText",
                    "status": "seed_not_in_vocab",
                    "seed": seed,
                    "similar_words": "",
                    "note": "해당 seed가 FastText 학습 vocab에 없어 유사어를 산출하지 못함",
                })

    except Exception as e:
        rows.append({
            "model": "FastText",
            "status": "not_available",
            "seed": "",
            "similar_words": "",
            "note": str(e),
        })

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with REPORT_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = ["model", "status", "seed", "similar_words", "note"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"완료: {REPORT_PATH}")

if __name__ == "__main__":
    main()
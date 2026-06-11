import pandas as pd


def load_policies():
    df = pd.read_csv("data/policies.csv", encoding="utf-8-sig")
    return df.to_dict(orient="records")
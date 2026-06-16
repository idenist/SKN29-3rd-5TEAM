import os
from functools import lru_cache

import requests

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
CONDITION_EXTRACT_TIMEOUT = float(os.getenv("CONDITION_EXTRACT_TIMEOUT", "2.5"))


@lru_cache(maxsize=128)
def extract_conditions_from_backend(message: str) -> dict:
    message = str(message or "").strip()
    if not message:
        return {}

    response = requests.post(
        f"{BACKEND_URL}/api/conditions/extract",
        json={"message": message},
        timeout=(0.5, CONDITION_EXTRACT_TIMEOUT),
    )
    response.raise_for_status()
    return response.json()

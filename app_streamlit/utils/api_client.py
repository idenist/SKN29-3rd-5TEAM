import os
import requests

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


def extract_conditions_from_backend(message: str) -> dict:
    response = requests.post(
        f"{BACKEND_URL}/api/conditions/extract",
        json={"message": message},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()
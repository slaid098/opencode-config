import os

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

API_URL = os.environ.get(
    "AI_PROVIDER_API_URL",
    "https://ai.slaid098.dev/v1",
)
API_KEY = os.environ.get("AI_PROVIDER_API_KEY", "")
EMBEDDING_MODEL = "gemini-embedding-2-preview"


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_is_retryable),
)
def _call_embedding_api(
    client: httpx.Client,
    url: str,
    headers: dict[str, str],
    payload: dict[str, str | list[str]],
) -> list[list[float]]:
    resp = client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    return [d["embedding"] for d in data["data"]]


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    url = f"{API_URL}/embeddings"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    payload: dict[str, str | list[str]] = {"model": EMBEDDING_MODEL, "input": texts}

    with httpx.Client(timeout=120.0) as client:
        return _call_embedding_api(client, url, headers, payload)

from typing import NoReturn
from unittest.mock import patch

import httpx
import pytest
from src.memory.embedder import embed_texts


def test_embed_texts_success() -> None:
    fake_embedding = [0.1, 0.2, 0.3]

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "data": [{"embedding": fake_embedding, "index": 0}],
                "model": "gemini-embedding-2-preview",
            }

        def raise_for_status(self) -> None:
            pass

    def mock_post(self, url, **kwargs):
        assert "embeddings" in url
        return FakeResponse()

    with patch.object(httpx.Client, "post", mock_post):
        result = embed_texts(["test text"])

    assert len(result) == 1
    assert result[0] == fake_embedding


def test_embed_texts_empty() -> None:
    assert embed_texts([]) == []


def test_embed_texts_api_error() -> None:
    class FakeErrorResponse:
        status_code = 401

        def raise_for_status(self) -> NoReturn:
            msg = "Unauthorized"
            raise httpx.HTTPStatusError(
                msg,
                request=None,
                response=self,
            )

        def json(self):
            return {}

    def mock_post(self, url, **kwargs):
        return FakeErrorResponse()

    with patch.object(httpx.Client, "post", mock_post), pytest.raises(httpx.HTTPStatusError):
        embed_texts(["test"])

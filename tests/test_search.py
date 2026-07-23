import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import src.memory.search as search_mod
from src.memory.search import _cosine_sim


class TestCosineSim:
    def test_identical(self) -> None:
        v = np.array([1.0, 2.0, 3.0])
        assert _cosine_sim(v, v) == pytest.approx(1.0)

    def test_orthogonal(self) -> None:
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        assert _cosine_sim(a, b) == pytest.approx(0.0)

    def test_zero_vector(self) -> None:
        a = np.array([0.0, 0.0])
        b = np.array([1.0, 1.0])
        assert _cosine_sim(a, b) == pytest.approx(0.0)

    def test_parallel(self) -> None:
        a = np.array([1.0, 2.0])
        b = np.array([2.0, 4.0])
        assert _cosine_sim(a, b) == pytest.approx(1.0)

    def test_opposite(self) -> None:
        a = np.array([1.0, 1.0])
        b = np.array([-1.0, -1.0])
        assert _cosine_sim(a, b) == pytest.approx(-1.0)


class TestSearchOutput:
    def test_search_json_format(self, tmp_path: Path) -> None:
        index_dir = tmp_path / ".rag"
        index_dir.mkdir()
        index = {
            "files": [
                {
                    "source": "test.md",
                    "text": "hello world",
                    "embedding": [1.0, 0.0, 0.0],
                },
            ],
        }
        (index_dir / "index.json").write_text(json.dumps(index))

        def fake_embed_texts(texts):
            return [[1.0, 0.0, 0.0]]

        with patch.object(search_mod, "embed_texts", fake_embed_texts):
            args = Namespace(index_dir=str(index_dir), query="hello", k=5, json=True)
            search_mod.run_search(args)

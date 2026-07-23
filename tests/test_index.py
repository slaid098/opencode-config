import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from src.memory.index import _extract_text, run_index


class TestExtractText:
    def test_with_frontmatter(self) -> None:
        md = "---\ntitle: test\n---\n\nbody content"
        assert _extract_text(md) == "body content"

    def test_no_frontmatter(self) -> None:
        md = "just content"
        assert _extract_text(md) == "just content"

    def test_empty(self) -> None:
        assert _extract_text("") == ""


class TestRunIndex:
    def test_index_creates_json(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "memory"
        index_dir = tmp_path / ".rag"
        memory_dir.mkdir(parents=True)

        (memory_dir / "test.md").write_text("---\ntitle: test\n---\n\nhello world")

        def fake_embed_texts(texts):
            return [[0.1, 0.2, 0.3]] * len(texts)

        with patch("src.memory.index.embed_texts", fake_embed_texts):
            args = Namespace(memory_dir=str(memory_dir), output=str(index_dir))
            run_index(args)

        assert (index_dir / "index.json").exists()
        index = json.loads((index_dir / "index.json").read_text())
        assert len(index["files"]) == 1
        assert index["files"][0]["source"] == "test.md"
        assert index["files"][0]["embedding"] == [0.1, 0.2, 0.3]

    def test_no_md_files(self, tmp_path: Path, capsys) -> None:
        memory_dir = tmp_path / "empty"
        index_dir = tmp_path / ".rag"
        memory_dir.mkdir(parents=True)

        args = Namespace(memory_dir=str(memory_dir), output=str(index_dir))
        run_index(args)

        captured = capsys.readouterr()
        assert "No .md files found" in captured.out

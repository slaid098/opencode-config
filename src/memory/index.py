import argparse
import json
from pathlib import Path

from src.memory.embedder import embed_texts

INDEX_FILENAME = "index.json"


def _extract_text(content: str) -> str:
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return content.strip()


def run_index(args: argparse.Namespace) -> None:
    memory_dir = Path(args.memory_dir)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    md_files = sorted(memory_dir.rglob("*.md"))
    md_files = [f for f in md_files if ".rag" not in f.parts]

    if not md_files:
        print("No .md files found")
        return

    texts: list[str] = []
    file_map: list[dict[str, str]] = []

    for fpath in md_files:
        rel = fpath.relative_to(memory_dir)
        content = fpath.read_text(encoding="utf-8")
        text = _extract_text(content)
        texts.append(text)
        file_map.append({"source": str(rel), "text": text[:500]})

    embeddings = embed_texts(texts)

    index = {
        "files": [{**fm, "embedding": emb} for fm, emb in zip(file_map, embeddings, strict=False)],
    }

    (output_dir / INDEX_FILENAME).write_text(
        json.dumps(index, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Indexed {len(md_files)} files to {output_dir / INDEX_FILENAME}")

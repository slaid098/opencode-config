import argparse
import json
import sys
from pathlib import Path

import numpy as np
from src.memory.embedder import embed_texts


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def run_search(args: argparse.Namespace) -> None:
    index_path = Path(args.index_dir) / "index.json"
    if not index_path.exists():
        json.dump([], sys.stdout)
        return

    index = json.loads(index_path.read_text(encoding="utf-8"))
    files = index.get("files", [])
    if not files:
        json.dump([], sys.stdout)
        return

    query_emb = embed_texts([args.query])[0]
    query_vec = np.array(query_emb)

    results: list[dict[str, str | float]] = []
    for f in files:
        file_vec = np.array(f["embedding"])
        sim = _cosine_sim(query_vec, file_vec)
        results.append({"source": f["source"], "score": sim, "text": f["text"]})

    results.sort(key=lambda r: r["score"], reverse=True)
    top = results[: args.k]

    print(json.dumps(top, ensure_ascii=False))

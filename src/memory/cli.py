import argparse

from src.memory.index import run_index
from src.memory.search import run_search


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="rag")
    sub = parser.add_subparsers(dest="command", required=True)

    search_p = sub.add_parser("search")
    search_p.add_argument("query")
    search_p.add_argument("-i", "--index-dir", required=True)
    search_p.add_argument("-k", type=int, default=15)
    search_p.add_argument("--json", action="store_true")

    index_p = sub.add_parser("index")
    index_p.add_argument("memory_dir")
    index_p.add_argument("-o", "--output", required=True)

    sub.add_parser("download")

    args = parser.parse_args(argv)

    if args.command == "search":
        run_search(args)
    elif args.command == "index":
        run_index(args)
    elif args.command == "download":
        print("Gemini API: model download not needed")


if __name__ == "__main__":
    main()

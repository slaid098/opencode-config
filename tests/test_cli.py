import subprocess
import sys


def test_cli_download() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "src.memory", "download"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "not needed" in result.stdout


def test_cli_search_no_index(tmp_path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.memory",
            "search",
            "test query",
            "-i",
            str(tmp_path),
            "-k",
            "5",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "[]"

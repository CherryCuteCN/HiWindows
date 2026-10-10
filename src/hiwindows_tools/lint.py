from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMMANDS = (
    ("ruff", ("ruff", "check", ".")),
    ("basedpyright", ("basedpyright",)),
)


def _run_linter(name: str, command: tuple[str, ...]) -> int:
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert process.stdout is not None
    for line in process.stdout:
        print(f"[{name}] {line}", end="", flush=True)

    return process.wait()


def main() -> int:
    with ThreadPoolExecutor(max_workers=len(COMMANDS)) as executor:
        results = executor.map(lambda item: _run_linter(*item), COMMANDS)

    exit_codes = tuple(results)
    return max(exit_codes, default=0)


if __name__ == "__main__":
    sys.exit(main())

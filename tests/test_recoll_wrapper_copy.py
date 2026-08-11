"""
Verify that recoll_wrapper/ is copied into the recoll-engine image at build time
so the container has the full folder baked in (pyproject.toml, docs, tests, etc.)
and then bind-mounted read-only at runtime so the host version is the single
source of truth and container restarts cannot overwrite host edits.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = REPO_ROOT / "recoll-engine" / "Dockerfile"
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"


def main() -> int:
    failures: list[str] = []

    if not DOCKERFILE.is_file():
        failures.append(f"Dockerfile missing: {DOCKERFILE}")
    if not COMPOSE_FILE.is_file():
        failures.append(f"docker-compose.yml missing: {COMPOSE_FILE}")

    if failures:
        print("FAIL: missing files", file=sys.stderr)
        for line in failures:
            print(f"  {line}", file=sys.stderr)
        return 1

    dockerfile_text = DOCKERFILE.read_text()
    compose_text = COMPOSE_FILE.read_text()

    # 1. Dockerfile must copy the entire recoll_wrapper folder into the image
    if "COPY recoll_wrapper/" not in dockerfile_text:
        failures.append(
            "Dockerfile has no COPY instruction for recoll_wrapper/. "
            "Expected: COPY recoll_wrapper/ /usr/local/src/recoll_wrapper/"
        )
    if "RUN chmod +x /usr/local/src/recoll_wrapper/recollindex.py" not in dockerfile_text:
        failures.append(
            "Dockerfile does not make recollindex.py executable after copy"
        )

    # 2. Dockerfile must create a symlink so recollindex is in PATH
    if "ln -s /usr/local/src/recoll_wrapper/recollindex.py /usr/local/bin/recollindex" not in dockerfile_text:
        failures.append(
            "Dockerfile does not create symlink for recollindex in /usr/local/bin/"
        )

    # 3. docker-compose.yml must bind-mount recoll_wrapper/ read-only via x-data-mounts
    anchor_match = re.search(
        r"x-data-mounts:.*?(?=\n  [a-z]|\Z)", compose_text, re.DOTALL
    )
    if not anchor_match:
        failures.append("x-data-mounts anchor not found in docker-compose.yml")
    else:
        anchor = anchor_match.group(0)
        if "recoll_wrapper/" not in anchor:
            failures.append(
                "x-data-mounts anchor has no bind mount for recoll_wrapper/. "
                "Expected: type: bind, source: ../recoll_wrapper/, target: /usr/local/src/recoll_wrapper/, read_only: true"
            )
        if "read_only: true" not in anchor:
            failures.append("recoll_wrapper bind mount is not read-only")

    if failures:
        print("FAIL: recoll_wrapper verification failed:", file=sys.stderr)
        for line in failures:
            print(f"  {line}", file=sys.stderr)
        return 1

    print("OK: recoll_wrapper/ is copied into the image and bind-mounted read-only")
    return 0


def test_recoll_wrapper_copy() -> None:
    """Pytest wrapper — asserts that the verification passes."""
    assert main() == 0, "recoll_wrapper verification failed"


if __name__ == "__main__":
    sys.exit(main())
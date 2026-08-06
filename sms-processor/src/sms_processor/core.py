"""Core processing logic - state management, scanning, and main loop."""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import time
from pathlib import Path

from sms_processor.archiver import process_xml_file

log = logging.getLogger("sms-processor")

# Lazy defaults evaluated only when main() runs or tests override them
_DEFAULT_INPUT = Path("/input")
_DEFAULT_OUTPUT = Path("/output")
_DEFAULT_POLL = 300


def _parse_cli_args():
    """Parse CLI arguments. Only call from main(), not at import time."""
    input_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_INPUT
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else _DEFAULT_OUTPUT
    try:
        poll_seconds = int(sys.argv[3]) if len(sys.argv) > 3 else _DEFAULT_POLL
    except (ValueError, IndexError):
        poll_seconds = _DEFAULT_POLL
    return input_dir, output_dir, poll_seconds


# Module-level defaults (tests can override these)
INPUT_DIR = _DEFAULT_INPUT
OUTPUT_DIR = _DEFAULT_OUTPUT
POLL_SECONDS = _DEFAULT_POLL
STATE_FILE = OUTPUT_DIR / ".processed.json"


def load_state() -> dict[str, str]:
    """Return {relative_path: md5} of already-processed files."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            log.warning("Corrupt state file, starting fresh")
            return {}
    return {}


def save_state(state: dict[str, str]) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def file_hash(path: Path) -> str:
    h = hashlib.md5()
    h.update(path.read_bytes())
    return h.hexdigest()


def scan_and_process() -> int:
    """Scan INPUT_DIR for user subdirs and process any new XML files."""
    state = load_state()
    processed_count = 0

    if not INPUT_DIR.exists():
        log.warning("Input directory %s does not exist", INPUT_DIR)
        return 0

    for user_dir in sorted(INPUT_DIR.iterdir()):
        if not user_dir.is_dir():
            continue

        user_label = user_dir.name
        for xml_file in sorted(user_dir.glob("*.xml")):
            rel = str(xml_file.relative_to(INPUT_DIR))
            current_hash = file_hash(xml_file)
            saved_hash = state.get(rel)

            if saved_hash == current_hash:
                continue

            process_xml_file(xml_file, OUTPUT_DIR, user_label)
            state[rel] = current_hash
            processed_count += 1

    if processed_count:
        save_state(state)

    return processed_count


def main() -> None:
    global INPUT_DIR, OUTPUT_DIR, POLL_SECONDS, STATE_FILE
    INPUT_DIR, OUTPUT_DIR, POLL_SECONDS = _parse_cli_args()
    STATE_FILE = OUTPUT_DIR / ".processed.json"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    log.info("=" * 60)
    log.info("SMS/RCS Backup Processor")
    log.info("Input:  %s", INPUT_DIR)
    log.info("Output: %s", OUTPUT_DIR)
    log.info("Poll:   every %ds", POLL_SECONDS)
    log.info("=" * 60)

    count = scan_and_process()
    if count:
        log.info("Initial run: processed %d file(s)", count)
    else:
        log.info("Initial run: no new files to process")

    iteration = 0
    while True:
        time.sleep(POLL_SECONDS)
        iteration += 1
        try:
            count = scan_and_process()
            if count:
                log.info("Poll #%d: processed %d new file(s)", iteration, count)
            else:
                log.debug("Poll #%d: no changes", iteration)
        except Exception:
            log.exception("Poll #%d encountered an error", iteration)

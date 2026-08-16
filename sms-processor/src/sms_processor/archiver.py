"""Output generation - organize messages by phone number into markdown files."""

from __future__ import annotations

import html
import logging
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sms_processor.extractor import extract_sms_messages

log = logging.getLogger("sms-processor")


def contact_key(address: str, contact_name: str | None) -> tuple[str, str]:
    """Return (filename-safe key, display name)."""
    if contact_name:
        safe = re.sub(r"[^a-zA-Z0-9_\-\+]", "", address)
        return (f"{contact_name} ({safe})", contact_name)
    safe = re.sub(r"[^a-zA-Z0-9_\-\+]", "", address)
    return (safe, address)


def process_xml_file(xml_path: Path, output_base: Path, user_label: str) -> list[str]:
    """Process a single XML backup file.

    Returns list of contact keys that were updated.
    """
    log.info("Processing %s", xml_path.name)

    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as e:
        log.error("Failed to parse %s: %s", xml_path.name, e)
        return []

    root = tree.getroot()
    messages = extract_sms_messages(root)
    if not messages:
        log.info("  No SMS/MMS messages found in %s", xml_path.name)
        return []

    groups: dict[str, list[dict[str, Any]]] = {}
    for msg in messages:
        key, _ = contact_key(msg["address"], msg["contact"])
        groups.setdefault(key, []).append(msg)

    user_dir = output_base / user_label
    user_dir.mkdir(parents=True, exist_ok=True)
    updated: list[str] = []

    for key, msgs in groups.items():
        display = key
        if " (" in key and key.endswith(")"):
            display = key.split(" (", 1)[0]

        msgs.sort(key=lambda m: m["timestamp"] or datetime.min.replace(tzinfo=UTC))

        md_path = user_dir / f"{key}.md"
        new_content = _build_md_content(msgs, display)

        with open(md_path, "a") as f:
            if md_path.exists() and md_path.stat().st_size > 0:
                f.write("\n---\n\n")
            f.write(new_content)

        updated.append(key)
        log.info("  Updated %s (+%d messages)", md_path.name, len(msgs))

    return updated


def _build_md_content(msgs: list[dict[str, Any]], display_name: str) -> str:
    """Build markdown text for a batch of messages."""
    lines: list[str] = []
    for msg in msgs:
        ts_str = (
            msg["timestamp"].strftime("%Y-%m-%d %H:%M:%S UTC")
            if msg["timestamp"]
            else msg.get("date_str", "Unknown date")
        )
        protocol = f" ({msg['protocol']})" if msg.get("protocol") else ""
        mms_badge = " [MMS]" if msg.get("is_mms") else ""

        lines.append(f"## {display_name} — {ts_str}")
        lines.append(f"**{msg['type']}**{protocol}{mms_badge}")

        if msg.get("subject"):
            lines.append(f"*Subject: {html.escape(msg['subject'])}*")

        body = html.escape(msg["body"])
        body = body.replace("\n", "\n\n")
        lines.append("")
        lines.append(body)

        if msg.get("attachments"):
            lines.append("")
            lines.append("**Attachments:**")
            for att in msg["attachments"]:
                name = att.get("name") or "unknown"
                loc = att.get("location") or ""
                atype = att.get("type") or ""
                lines.append(f"- `{name}` ({atype}) — {html.escape(loc)}")

        lines.append("")

    return "\n".join(lines)

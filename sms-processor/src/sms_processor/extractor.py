"""XML parsing for SMS Backup & Restore format."""

from __future__ import annotations

import html
import logging
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any

log = logging.getLogger("sms-processor")

SMS_TYPE_MAP = {
    "1": "Inbox",
    "2": "Sent",
    "3": "Failed",
    "4": "Draft",
}


def parse_timestamp(value: str) -> datetime | None:
    """Parse SMS Backup & Restore timestamp like '2026-08-01 14:23:00'."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        pass
    # Fallback: epoch milliseconds
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=UTC)
    except (ValueError, OSError, OverflowError):
        return None


def extract_contact_name(elem: ET.Element) -> str | None:
    """Try to find the contact name from <person> attribute or sub-element."""
    person = elem.get("person")
    if person and person.strip():
        return person.strip()
    for child in elem:
        tag = child.tag.split("}")[-1]
        if tag == "person" and (text := (child.text or "").strip()):
            return text
    return None


def extract_protocol(elem: ET.Element) -> str | None:
    """Extract protocol (SMS/RCS) from <protocol> sub-element."""
    for child in elem:
        tag = child.tag.split("}")[-1]
        if tag == "protocol" and (text := (child.text or "").strip()):
            return text
    proto = elem.get("protocol")
    if proto:
        return proto
    return None


def extract_sms_messages(root: ET.Element) -> list[dict[str, Any]]:
    """Parse <sms> elements from a backup file."""
    messages: list[dict[str, Any]] = []
    for elem in root:
        tag = elem.tag.split("}")[-1]
        if tag not in ("sms", "mms"):
            continue

        address_raw = (elem.get("address") or "").strip()
        if not address_raw:
            continue

        address = address_raw
        date_str = elem.get("date") or ""
        ts = parse_timestamp(date_str)
        type_label = SMS_TYPE_MAP.get(elem.get("type", ""), "Unknown")

        body_parts: list[str] = []
        protocol = extract_protocol(elem)
        service_center = None
        subject = None

        for child in elem:
            child_tag = child.tag.split("}")[-1]
            if child_tag == "body" and (text := (child.text or "").strip()):
                body_parts.append(html.unescape(text))
            elif child_tag == "sc":
                service_center = child.get("address")
            elif child_tag == "subject" and (text := (child.text or "").strip()):
                subject = text

        attachments: list[dict[str, str]] = []
        for child in elem:
            child_tag = child.tag.split("}")[-1]
            if child_tag == "part":
                part_type = child.get("ct") or ""
                part_name = child.get("name") or child.get("tn", "")
                part_loc = child.get("loc") or (child.text or "")
                if part_loc:
                    attachments.append(
                        {"type": part_type, "name": part_name, "location": part_loc}
                    )

        body = "\n".join(body_parts) if body_parts else "(empty message)"
        contact = extract_contact_name(elem)

        messages.append(
            {
                "address": address,
                "timestamp": ts,
                "date_str": date_str,
                "type": type_label,
                "body": body,
                "protocol": protocol,
                "contact": contact,
                "service_center": service_center,
                "subject": subject,
                "attachments": attachments,
                "is_mms": tag == "mms",
            }
        )

    return messages

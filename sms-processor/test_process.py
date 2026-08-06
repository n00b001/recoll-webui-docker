"""Tests for sms-processor."""

import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from process import (
    extract_sms_messages,
    parse_timestamp,
    process_xml_file,
)

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<backup op_id="6376594f2a9576d9" app_version="9.6" backup_time="Fri Aug 01 14:30:00 2026">
  <sms address="+15551234567" date="1722051780000" protocol="0" type="1" sub_id="0">
    <person>Mom</person>
    <body>Hey, running late tonight!</body>
    <date>2026-08-01 14:23:00</date>
    <type>1</type>
    <protocol>0</protocol>
    <status>-1</status>
    <service_center>+15559998888</service_center>
  </sms>
  <sms address="+15551234567" date="1722051900000" protocol="0" type="2" sub_id="0">
    <person>Mom</person>
    <body>No worries, I&apos;ll be here a while.</body>
    <date>2026-08-01 14:25:00</date>
    <type>2</type>
    <protocol>0</protocol>
    <status>-1</status>
  </sms>
  <sms address="+15559876543" date="1722052800000" protocol="0" type="1" sub_id="0">
    <body>Package delivered to front door</body>
    <date>2026-08-01 14:40:00</date>
    <type>1</type>
    <protocol>0</protocol>
    <status>-1</status>
  </sms>
  <mms address="+15551112222" date="1722053400000" protocol="0" type="1" sub_id="0">
    <person>Chloe</person>
    <body>Check out this photo!</body>
    <date>2026-08-01 14:50:00</date>
    <type>1</type>
    <protocol>0</protocol>
    <status>-1</status>
    <subject>Photo</subject>
    <part ct="image/jpeg" name="photo.jpg" loc="/storage/emulated/0/Pictures/photo.jpg"/>
  </mms>
</backup>
"""


def test_parse_timestamp():
    ts = parse_timestamp("2026-08-01 14:23:00")
    assert ts is not None
    assert ts.year == 2026
    assert ts.month == 8
    assert ts.day == 1
    assert ts.hour == 14
    assert ts.minute == 23
    print("  parse_timestamp OK")


def test_extract_messages():
    root = ET.fromstring(SAMPLE_XML)
    msgs = extract_sms_messages(root)

    assert len(msgs) == 4, f"Expected 4 messages, got {len(msgs)}"

    # First message
    assert msgs[0]["address"] == "+15551234567"
    assert msgs[0]["type"] == "Inbox"
    assert "running late" in msgs[0]["body"]
    assert msgs[0]["contact"] == "Mom"

    # Second message (sent)
    assert msgs[1]["type"] == "Sent"
    assert "&apos;" not in msgs[1]["body"]  # HTML entities decoded
    assert "'" in msgs[1]["body"]

    # Third message (no contact name)
    assert msgs[2]["address"] == "+15559876543"
    assert msgs[2]["contact"] is None
    assert "Package delivered" in msgs[2]["body"]

    # Fourth message (MMS with attachment)
    assert msgs[3]["is_mms"] is True
    assert len(msgs[3]["attachments"]) == 1
    assert msgs[3]["attachments"][0]["name"] == "photo.jpg"
    assert msgs[3]["subject"] == "Photo"

    print("  extract_messages OK")


def test_process_xml_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        inp = Path(tmpdir) / "input"
        out = Path(tmpdir) / "output"
        inp.mkdir()
        out.mkdir()

        user_dir = inp / "alex"
        user_dir.mkdir()
        (user_dir / "test.xml").write_text(SAMPLE_XML)

        updated = process_xml_file(user_dir / "test.xml", out, "alex")

        # Should have 3 contact files:
        # - Mom (+15551234567)
        # - +15559876543
        # - Chloe (+15551112222)
        assert len(updated) == 3, f"Expected 3 contacts, got {len(updated)}: {updated}"

        # Check Mom's file
        mom_file = out / "alex" / "Mom (+15551234567).md"
        assert mom_file.exists(), f"Missing file: {mom_file}"
        content = mom_file.read_text()
        assert "running late" in content
        assert "Inbox" in content
        assert "Sent" in content
        print("  process_xml_file OK")

        # Check unknown contact
        unknown_file = out / "alex" / "+15559876543.md"
        assert unknown_file.exists(), f"Missing file: {unknown_file}"
        assert "Package delivered" in unknown_file.read_text()
        print("  unknown contact OK")

        # Check MMS contact
        chloe_file = out / "alex" / "Chloe (+15551112222).md"
        assert chloe_file.exists(), f"Missing file: {chloe_file}"
        chloe_content = chloe_file.read_text()
        assert "[MMS]" in chloe_content
        assert "photo.jpg" in chloe_content
        print("  MMS contact OK")


def test_empty_backup():
    empty_xml = """<?xml version="1.0"?>
<backup><call><number>123</number></call></backup>
"""
    root = ET.fromstring(empty_xml)
    msgs = extract_sms_messages(root)
    assert len(msgs) == 0
    print("  empty backup OK")


def main():
    print("test_parse_timestamp:")
    test_parse_timestamp()
    print("test_extract_messages:")
    test_extract_messages()
    print("test_process_xml_file:")
    test_process_xml_file()
    print("test_empty_backup:")
    test_empty_backup()
    print("\nAll tests passed!")


if __name__ == "__main__":
    main()

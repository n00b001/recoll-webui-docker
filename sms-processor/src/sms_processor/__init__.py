"""SMS/RCS Backup Processor.

Reads SMS Backup & Restore XML files and organizes messages by phone number
into Recoll-indexable markdown files.
"""

from sms_processor.core import main

__all__ = ["main"]

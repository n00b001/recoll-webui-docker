"""Tests for transcribe.py — state management, file discovery, model URLs."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

import transcribe


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def tmp_input(tmp_path: Path) -> Path:
    """Create a temporary input directory with test audio files."""
    inp = tmp_path / "input"
    inp.mkdir()

    (inp / "song.mp3").write_bytes(b"fake mp3 data")
    (inp / "voice.ogg").write_bytes(b"fake ogg data")
    (inp / "video.mp4").write_bytes(b"fake mp4 data")
    (inp / "readme.txt").write_text("not audio")

    nested = inp / "subdir"
    nested.mkdir()
    (nested / "recording.wav").write_bytes(b"fake wav data")

    return inp


@pytest.fixture()
def tmp_output(tmp_path: Path) -> Path:
    """Create a temporary output directory."""
    out = tmp_path / "output"
    out.mkdir()
    return out


# ---------------------------------------------------------------------------
# Test: compute_file_hash
# ---------------------------------------------------------------------------
class TestFileHash:
    def test_compute_file_hash_deterministic(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.bin"
        data = b"hello world" * 1000
        test_file.write_bytes(data)

        hash1 = transcribe.compute_file_hash(test_file)
        hash2 = transcribe.compute_file_hash(test_file)

        assert hash1 == hash2
        assert len(hash1) == 32

    def test_different_content_different_hash(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.bin"
        f2 = tmp_path / "b.bin"
        f1.write_bytes(b"data one")
        f2.write_bytes(b"data two")

        assert transcribe.compute_file_hash(f1) != transcribe.compute_file_hash(f2)

    def test_empty_file(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.bin"
        empty.write_bytes(b"")
        h = transcribe.compute_file_hash(empty)
        assert h == hashlib.md5(b"").hexdigest()


# ---------------------------------------------------------------------------
# Test: state management
# ---------------------------------------------------------------------------
class TestStateManagement:
    @pytest.fixture()
    def patched_state(self, tmp_output: Path):
        """Patch STATE_FILE to use tmp_output."""
        original = transcribe.STATE_FILE
        transcribe.STATE_FILE = tmp_output / ".transcribed.json"
        yield tmp_output
        transcribe.STATE_FILE = original

    def test_load_empty_state(self, patched_state: Path) -> None:
        state = transcribe.load_state()
        assert state == {}

    def test_save_and_load_state(self, patched_state: Path) -> None:
        test_state = {"file1.mp3": "abc123", "subdir/file2.wav": "def456"}
        transcribe.save_state(test_state)
        loaded = transcribe.load_state()

        assert loaded == test_state

    def test_corrupt_state_recovers(self, patched_state: Path) -> None:
        state_file = patched_state / ".transcribed.json"
        state_file.write_text("{invalid json")
        state = transcribe.load_state()

        assert state == {}

    def test_state_overwrite(self, patched_state: Path) -> None:
        transcribe.save_state({"a.mp3": "hash1"})
        transcribe.save_state({"b.mp3": "hash2"})
        loaded = transcribe.load_state()

        assert loaded == {"b.mp3": "hash2"}


# ---------------------------------------------------------------------------
# Test: model URL construction
# ---------------------------------------------------------------------------
class TestModelURL:
    @pytest.mark.parametrize(
        "model_name,expected",
        [
            (
                "tiny",
                "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin",
            ),
            (
                "base",
                "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin",
            ),
            (
                "small",
                "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin",
            ),
            (
                "medium",
                "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin",
            ),
            (
                "large",
                "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large.bin",
            ),
        ],
    )
    def test_url_construction(self, model_name: str, expected: str) -> None:
        assert transcribe.get_model_url(model_name) == expected


# ---------------------------------------------------------------------------
# Test: file discovery
# ---------------------------------------------------------------------------
class TestFileDiscovery:
    def test_find_audio_files(self, tmp_input: Path) -> None:
        found = transcribe.find_audio_files(tmp_input)
        filenames = {p.name for p in found}

        assert "song.mp3" in filenames
        assert "voice.ogg" in filenames
        assert "video.mp4" in filenames
        assert "readme.txt" not in filenames
        assert any(p.name == "recording.wav" for p in found)

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        result = transcribe.find_audio_files(tmp_path / "does_not_exist")
        assert result == []

    def test_empty_dir(self, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        result = transcribe.find_audio_files(empty_dir)
        assert result == []


# ---------------------------------------------------------------------------
# Test: needs_transcode
# ---------------------------------------------------------------------------
class TestNeedsTranscode:
    @pytest.mark.parametrize(
        "ext,expected",
        [
            (".mp3", True),
            (".wav", False),
            (".ogg", True),
            (".m4a", True),
            (".flac", True),
            (".opus", True),
            (".aac", True),
            (".mp4", True),
            (".mov", True),
        ],
    )
    def test_transcode_check(self, ext: str, expected: bool) -> None:
        fake_path = Path("/fake/file" + ext)
        assert transcribe.needs_transcode(fake_path) == expected


# ---------------------------------------------------------------------------
# Test: environment configuration
# ---------------------------------------------------------------------------
class TestEnvConfig:
    def test_default_values(self) -> None:
        # Module was imported with default env — check defaults
        assert transcribe.WHISPER_MODEL in (
            "tiny",
            "base",
            "small",
            "medium",
            "large",
        )
        assert transcribe.WHISPER_LANGUAGE == "auto"

    def test_all_extensions_covered(self) -> None:
        expected = {
            ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac",
            ".webm", ".mp4", ".mov", ".mkv",
        }
        assert transcribe.ALL_EXTENSIONS == expected


# ---------------------------------------------------------------------------
# Test: transcribe_file transcript location fallback
# ---------------------------------------------------------------------------
class TestTranscribeFile:
    def _run_transcribe(
        self, tmp_path: Path, monkeypatch, *, writes_to_cwd: bool
    ) -> Path:
        """Run transcribe_file with a FAKE whisper.cpp.

        Writes the transcript to the absolute -of target (as a well-behaved
        whisper.cpp does), or to the process CWD (as the buggy build in the
        container does). Returns what transcribe_file returns.
        """
        wav = tmp_path / "clip.wav"
        wav.write_bytes(b"fake wav")
        model = tmp_path / "ggml-model.bin"
        model.write_bytes(b"fake model")
        output = tmp_path / "output"
        output.mkdir()

        def fake_whisper(cmd, **kwargs):
            of = cmd[cmd.index("-of") + 1]
            if writes_to_cwd:
                # whisper.cpp ignores -of and writes <stem>.txt in CWD
                (Path.cwd() / f"{Path(of).stem}.txt").write_text("transcript")
            else:
                Path(of + ".txt").write_text("transcript")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(transcribe.subprocess, "run", fake_whisper)

        return transcribe.transcribe_file(wav, model, output, language="auto")

    def test_transcript_in_output_dir(self, tmp_path, monkeypatch) -> None:
        """Absolute -of honoured: transcript lands at target, no fallback."""
        ret = self._run_transcribe(tmp_path, monkeypatch, writes_to_cwd=False)
        assert ret == tmp_path / "output" / "clip.txt"
        assert (tmp_path / "output" / "clip.txt").read_text() == "transcript"

    def test_transcript_written_to_cwd(self, tmp_path, monkeypatch) -> None:
        """whisper.cpp writes <stem>.txt to process CWD (/app) — fallback."""
        ret = self._run_transcribe(tmp_path, monkeypatch, writes_to_cwd=True)
        assert ret == tmp_path / "output" / "clip.txt"
        assert (tmp_path / "output" / "clip.txt").read_text() == "transcript"
        # Moved out of CWD, not copied — no stray copy left behind
        assert not (Path.cwd() / "clip.txt").exists()

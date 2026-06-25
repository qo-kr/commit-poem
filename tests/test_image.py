from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from commitpoem.image import (
    ImageGenError,
    _build_image_prompt,
    _parse_thread_id,
    generate_image,
)

THREAD_ID = "019efdde-ee25-7fb2-823e-efaacdd9ddf9"
PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-image-data"
POEM = "🇺🇸 A quiet dawn over the sea\n🇰🇷 고요한 새벽 바다"


def _stdout(thread_id: str | None = THREAD_ID) -> str:
    """Build a fake codex --json JSONL stdout stream."""
    lines: list[str] = []
    if thread_id is not None:
        lines.append(json.dumps({"type": "thread.started", "thread_id": thread_id}))
    lines.append(json.dumps({"type": "turn.started"}))
    lines.append(json.dumps({"type": "turn.completed"}))
    return "\n".join(lines) + "\n"


def _proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def patch_run(result_or_exc: object):
    """Patch commitpoem.image.subprocess.run to return a value or raise an exception."""
    if isinstance(result_or_exc, BaseException):
        return patch("commitpoem.image.subprocess.run", side_effect=result_or_exc)
    return patch("commitpoem.image.subprocess.run", return_value=result_or_exc)


@pytest.fixture
def codex_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    monkeypatch.delenv("CODEX_BIN", raising=False)
    return tmp_path


def _write_png(
    home: Path, *, thread_id: str = THREAD_ID, name: str = "ig_test.png", data: bytes = PNG_BYTES
) -> Path:
    directory = home / "generated_images" / thread_id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(data)
    return path


# ---------------------------------------------------------------------------
# _parse_thread_id / _build_image_prompt
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_parse_thread_id_found(self) -> None:
        assert _parse_thread_id(_stdout()) == THREAD_ID

    def test_parse_thread_id_missing(self) -> None:
        assert _parse_thread_id(_stdout(thread_id=None)) is None

    def test_parse_thread_id_ignores_garbage_lines(self) -> None:
        stream = "not json\n" + _stdout()
        assert _parse_thread_id(stream) == THREAD_ID

    def test_prompt_includes_poem_and_constraints(self) -> None:
        prompt = _build_image_prompt(POEM)
        assert POEM in prompt
        assert "image_gen" in prompt
        assert "no text" in prompt.lower()


# ---------------------------------------------------------------------------
# generate_image — happy path
# ---------------------------------------------------------------------------


class TestGenerateImageHappy:
    def test_returns_png_bytes(self, codex_home: Path) -> None:
        _write_png(codex_home)
        with patch_run(_proc(stdout=_stdout())):
            result = generate_image(POEM)
        assert result == PNG_BYTES

    def test_invokes_codex_exec_json(self, codex_home: Path) -> None:
        _write_png(codex_home)
        with patch_run(_proc(stdout=_stdout())) as mock_run:
            generate_image(POEM)
        args = mock_run.call_args[0][0]
        assert args[0] == "codex"
        assert "exec" in args and "--json" in args

    def test_honours_codex_bin_env(self, codex_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CODEX_BIN", "/opt/codex")
        _write_png(codex_home)
        with patch_run(_proc(stdout=_stdout())) as mock_run:
            generate_image(POEM)
        assert mock_run.call_args[0][0][0] == "/opt/codex"

    def test_picks_newest_png(self, codex_home: Path) -> None:
        older = _write_png(codex_home, name="ig_old.png", data=b"old")
        newer = _write_png(codex_home, name="ig_new.png", data=b"new")
        os.utime(older, (1000, 1000))
        os.utime(newer, (2000, 2000))
        with patch_run(_proc(stdout=_stdout())):
            assert generate_image(POEM) == b"new"


# ---------------------------------------------------------------------------
# generate_image — failure modes
# ---------------------------------------------------------------------------


class TestGenerateImageErrors:
    def test_codex_missing(self, codex_home: Path) -> None:
        with patch_run(FileNotFoundError()):
            with pytest.raises(ImageGenError, match="not found"):
                generate_image(POEM)

    def test_timeout(self, codex_home: Path) -> None:
        with patch_run(subprocess.TimeoutExpired(cmd="codex", timeout=1)):
            with pytest.raises(ImageGenError, match="timed out"):
                generate_image(POEM)

    def test_nonzero_exit(self, codex_home: Path) -> None:
        with patch_run(_proc(returncode=1, stderr="boom")):
            with pytest.raises(ImageGenError, match="boom"):
                generate_image(POEM)

    def test_no_thread_id(self, codex_home: Path) -> None:
        with patch_run(_proc(stdout=_stdout(thread_id=None))):
            with pytest.raises(ImageGenError, match="thread id"):
                generate_image(POEM)

    def test_no_png_produced(self, codex_home: Path) -> None:
        with patch_run(_proc(stdout=_stdout())):
            with pytest.raises(ImageGenError, match="no image"):
                generate_image(POEM)

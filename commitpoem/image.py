from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

__all__ = ["generate_image", "ImageGenError"]

_CODEX_HOME_ENV = "CODEX_HOME"
_CODEX_BIN_ENV = "CODEX_BIN"
_DEFAULT_TIMEOUT = 300.0


class ImageGenError(Exception):
    """Raised on any failure to generate an image via the codex CLI."""


def _codex_home() -> Path:
    """Return the codex home directory ($CODEX_HOME or ~/.codex)."""
    env = os.environ.get(_CODEX_HOME_ENV)
    return Path(env) if env else Path.home() / ".codex"


def _build_image_prompt(poem: str) -> str:
    """Build the codex prompt that drives the built-in image_gen tool from a poem."""
    return (
        "Use the built-in image_gen tool to generate exactly one image. "
        "Call image_gen directly — do not read skill files or run shell commands first.\n\n"
        "Create a single evocative, atmospheric, painterly image that captures the mood "
        "and imagery of the poem below. Soft and abstract is welcome; let it feel like the "
        "feeling behind the words, not a literal illustration.\n"
        "Absolutely no text, letters, words, captions, or signatures anywhere in the image.\n\n"
        f"Poem:\n{poem}"
    )


def _parse_thread_id(stdout: str) -> str | None:
    """Extract the codex thread id from a ``--json`` JSONL stdout stream."""
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "thread.started":
            thread_id = event.get("thread_id")
            if thread_id:
                return str(thread_id)
    return None


def generate_image(poem: str, *, timeout: float = _DEFAULT_TIMEOUT) -> bytes:
    """Generate an image for *poem* using the codex CLI's built-in image tool.

    Runs ``codex exec`` non-interactively, locates the PNG codex saves under
    ``<codex_home>/generated_images/<thread_id>/`` and returns its raw bytes.

    The codex binary is taken from the ``CODEX_BIN`` env var (default ``codex``),
    and the codex home from ``CODEX_HOME`` (default ``~/.codex``). Generation runs
    under codex's existing authentication (e.g. a ChatGPT subscription), so no
    separate image API key is required.

    Args:
        poem: The poem whose mood the image should capture.
        timeout: Maximum seconds to wait for codex before giving up.

    Returns:
        The generated PNG image as raw bytes.

    Raises:
        ImageGenError: If codex is missing, times out, exits non-zero, or produces no image.
    """
    codex_bin = os.environ.get(_CODEX_BIN_ENV) or "codex"
    prompt = _build_image_prompt(poem)
    try:
        proc = subprocess.run(
            [
                codex_bin,
                "exec",
                "--json",
                "--skip-git-repo-check",
                "-c",
                "model_reasoning_effort=low",
                prompt,
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise ImageGenError(
            f"codex CLI not found ({codex_bin!r}); install it or set CODEX_BIN."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ImageGenError(f"codex image generation timed out after {timeout}s.") from exc

    if proc.returncode != 0:
        raise ImageGenError(
            f"codex exec failed (exit {proc.returncode}): {proc.stderr.strip()[:500]}"
        )

    thread_id = _parse_thread_id(proc.stdout)
    if thread_id is None:
        raise ImageGenError("Could not determine codex thread id from its JSON output.")

    image_dir = _codex_home() / "generated_images" / thread_id
    pngs = sorted(image_dir.glob("*.png"), key=lambda p: p.stat().st_mtime)
    if not pngs:
        raise ImageGenError(f"codex produced no image in {image_dir}.")

    return pngs[-1].read_bytes()

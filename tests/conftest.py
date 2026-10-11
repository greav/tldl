"""What the tests share: a home folder of their own, a configuration file and Recordings in it, stand-in
Engines."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from stand_in_engine import StandInEngine

from tldl.engines import ENGINES

USERS_OWN_HOME = Path.home()
"""The home folder the suite was started in, noted before any test is given another."""


@pytest.fixture(scope="session")
def silent_track(tmp_path_factory):
    """Makes a Track of the given number of seconds holding digital silence; returns its path."""
    folder = tmp_path_factory.mktemp("silent-tracks")

    def make(seconds: float) -> Path:
        track = folder / f"{seconds}.flac"
        if not track.exists():
            subprocess.run(
                ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono"]
                + ["-t", str(seconds), "-c:a", "flac", track],
                check=True,
            )
        return track

    return make


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    """A home folder for each test, whether it asks for one or not: `~/tldl/` and the configuration file
    are under it, out of reach of the user's own. The speech models stay where they were downloaded."""
    models = os.environ.get("HF_HOME") or str(USERS_OWN_HOME / ".cache" / "huggingface")
    monkeypatch.setenv("HF_HOME", models)
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def configure(home):
    """Writes the given text as the configuration file, `~/.config/tldl/config.toml`; returns its path."""

    def write(text: str) -> Path:
        file = home / ".config" / "tldl" / "config.toml"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)
        return file

    return write


@pytest.fixture
def make_recording(home, silent_track):
    """Puts a Recording under `~/tldl/`, as `tldl record` leaves one; returns its folder.

    `root` is the Recordings root to put it under instead.
    """

    def make(
        name: str = "2026-10-10_1946",
        *,
        root: Path | None = None,
        started: str = "2026-10-10T19:46:05+02:00",
        track_starts: tuple[float | None, float | None] = (100.0, 100.0),
        mic_seconds: float = 3,
        system_seconds: float = 3,
    ) -> Path:
        recording = (root or home / "tldl") / name
        recording.mkdir(parents=True)
        shutil.copy(silent_track(mic_seconds), recording / "mic.flac")
        shutil.copy(silent_track(system_seconds), recording / "system.flac")
        metadata = {
            "started": started,
            "track_starts": dict(zip(("mic", "system"), track_starts)),
            "output_route": "headphones",
            "output_transport": "bluetooth",
        }
        (recording / "recording.json").write_text(json.dumps(metadata))
        return recording

    return make


@pytest.fixture
def stand_in(monkeypatch):
    """Puts a stand-in Engine under the name `name`, by default in the place of `parakeet-v3`; returns it."""

    def put(name: str = "parakeet-v3", *, mic=(), system=(), language=None, accepts=None) -> StandInEngine:
        engine = StandInEngine(mic, system, language, accepts)
        monkeypatch.setitem(ENGINES, name, engine)
        return engine

    return put

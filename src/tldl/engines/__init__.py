"""The Engines `tldl transcribe` can use, by name.

Adding an Engine is one adapter module beside this file and one entry in `ENGINES`. An adapter imports
its speech recognition library only when it is first asked to recognise a Track, so naming an Engine
here costs nothing until it runs.
"""

from tldl.engines.parakeet import Parakeet
from tldl.engines.seam import Engine, Segment
from tldl.engines.whisper import Whisper

__all__ = ["DEFAULT_ENGINE", "ENGINES", "Engine", "Segment"]

ENGINES: dict[str, Engine] = {
    "parakeet-v3": Parakeet("mlx-community/parakeet-tdt-0.6b-v3"),
    "whisper-large-v3": Whisper("mlx-community/whisper-large-v3-mlx"),
}
"""Every Engine, under the name that chooses it and that its Transcripts carry in their file names."""

DEFAULT_ENGINE = "parakeet-v3"

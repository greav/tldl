"""The weights of the speech models, from Hugging Face.

They are downloaded the first time an Engine runs and kept in Hugging Face's cache; from then on the
Engine runs without the network.
"""

import sys
from collections.abc import Sequence
from pathlib import Path


def weights_folder(weights: str, files: Sequence[str]) -> Path:
    """The folder on this Mac that holds `files` of the speech model `weights` names on Hugging Face."""
    # Imported here and not at the top: only a run of an Engine should pay for it.
    from huggingface_hub import hf_hub_download
    from huggingface_hub.errors import LocalEntryNotFoundError

    def folder(**how) -> Path:
        return Path([hf_hub_download(weights, file, **how) for file in files][-1]).parent

    try:
        # From the cache alone: once the weights are there, nothing asks Hugging Face about them.
        return folder(local_files_only=True)
    except LocalEntryNotFoundError:
        print(f"Downloading the speech model {weights}, this once.", file=sys.stderr, flush=True)
        return folder()

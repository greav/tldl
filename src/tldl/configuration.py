"""The user's defaults, read from the configuration file.

The file is TOML. Every key is optional, and so is the file itself:

    recordings_root  the folder Recordings go into and are looked for in; `~` is the home folder
    engine           the name of the Engine `tldl transcribe` uses
    language         the language spoken on the Recordings, as a code such as `en` or `ru`; without it
                     the language is left to the Engine
"""

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

from tldl.engines import DEFAULT_ENGINE
from tldl.recording import DEFAULT_RECORDINGS_ROOT

CONFIGURATION_FILE = Path("~/.config/tldl/config.toml")


@dataclass(frozen=True)
class Configuration:
    """What the tool uses where the command line does not say otherwise."""

    recordings_root: Path = DEFAULT_RECORDINGS_ROOT
    engine: str = DEFAULT_ENGINE
    language: str | None = None


class UnreadableConfiguration(Exception):
    """The configuration file cannot be used. The message is a sentence for the user, without its full
    stop, naming the file and the problem."""

    def __init__(self, file: Path, problem: str) -> None:
        super().__init__(f"Cannot read the configuration file {file}: {problem}")


def read_configuration() -> Configuration:
    """The defaults the configuration file sets, with the built-in default for every key it leaves out.

    Without the file, every default is the built-in one.
    """
    file = CONFIGURATION_FILE.expanduser()
    try:
        with file.open("rb") as content:
            keys = tomllib.load(content)
    except FileNotFoundError:
        return Configuration()
    except OSError as problem:
        raise UnreadableConfiguration(file, problem.strerror) from problem
    except UnicodeDecodeError as problem:
        raise UnreadableConfiguration(file, "it is not UTF-8 text") from problem
    except tomllib.TOMLDecodeError as problem:
        raise UnreadableConfiguration(file, str(problem)) from problem

    known = [field.name for field in fields(Configuration)]
    for key, value in keys.items():
        # A key the tool does not know is refused, not passed over: every key is optional, so a
        # misspelt one would otherwise leave the user on the built-in default with nothing said.
        if key not in known:
            raise UnreadableConfiguration(file, f"there is no key named {key}; the keys are {', '.join(known)}")
        if not isinstance(value, str):
            raise UnreadableConfiguration(file, f"{key} must be text in quotes")
    if "recordings_root" in keys:
        keys["recordings_root"] = Path(keys["recordings_root"])
    return Configuration(**keys)

"""Parser factory for TrackDeck."""

from pathlib import Path
from typing import Union

from track_deck.parsers.base import BaseSessionParser
from track_deck.parsers.folder import FolderMultitrackParser
from track_deck.parsers.sesx import AuditionSesxParser


def get_session_parser(path_str: Union[str, Path]) -> BaseSessionParser:
    """Return appropriate parser based on input file or directory."""
    p = Path(path_str).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"Project path does not exist: {path_str}")

    if p.is_file():
        suffix = p.suffix.lower()
        if suffix == ".sesx":
            return AuditionSesxParser(p)
        else:
            raise ValueError(f"Unsupported session file type: {suffix}. Supported: .sesx (Adobe Audition)")

    if p.is_dir():
        # Check if an Audition .sesx exists inside this directory
        sesx_files = list(p.glob("*.sesx"))
        if sesx_files:
            return AuditionSesxParser(sesx_files[0])
        # Otherwise, treat as folder of multitrack WAVs
        return FolderMultitrackParser(p)

    raise ValueError(f"Cannot parse path: {p}")

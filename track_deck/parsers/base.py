"""Base classes and data models for multitrack session parsers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class ClipInfo:
    """Information about an audio clip on a multitrack timeline."""
    name: str
    file_path: Path
    start_sample: int
    end_sample: int
    source_in: int = 0
    source_out: int = 0
    volume: float = 1.0


@dataclass
class TrackInfo:
    """Information about a multitrack audio track."""
    track_id: str
    name: str
    clips: List[ClipInfo] = field(default_factory=list)


@dataclass
class MarkerInfo:
    """Information about a session marker or song cue."""
    marker_id: str
    name: str
    start_sample: int
    duration_samples: int
    sample_rate: int
    marker_type: str = "Range"  # "Range", "Cue", or "Track"

    @property
    def start_sec(self) -> float:
        return self.start_sample / float(self.sample_rate) if self.sample_rate > 0 else 0.0

    @property
    def duration_sec(self) -> float:
        return self.duration_samples / float(self.sample_rate) if self.sample_rate > 0 else 0.0

    @property
    def end_sec(self) -> float:
        return self.start_sec + self.duration_sec

    @property
    def end_sample(self) -> int:
        return self.start_sample + self.duration_samples

    def formatted_start(self) -> str:
        s = int(self.start_sec)
        m, sec = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{sec:02d}"

    def formatted_duration(self) -> str:
        s = int(self.duration_sec)
        m, sec = divmod(s, 60)
        return f"{m:02d}:{sec:02d}"


class BaseSessionParser(ABC):
    """Abstract interface for session parsers (Audition, SoundCraft, altered-audio, folder)."""

    @abstractmethod
    def get_sample_rate(self) -> int:
        """Return session audio sample rate in Hz."""
        pass

    @abstractmethod
    def get_tracks(self) -> List[TrackInfo]:
        """Return list of multitrack audio tracks."""
        pass

    @abstractmethod
    def get_markers(self) -> List[MarkerInfo]:
        """Return list of session markers."""
        pass

    @abstractmethod
    def get_total_duration_sec(self) -> float:
        """Return total timeline duration in seconds."""
        pass

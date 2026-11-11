"""Plain multitrack folder parser (for Soundcraft/Behringer direct WAV recordings)."""

from pathlib import Path
from typing import List

import soundfile as sf

from track_deck.parsers.base import BaseSessionParser, ClipInfo, MarkerInfo, TrackInfo


class FolderMultitrackParser(BaseSessionParser):
    """Parser for a directory of raw multitrack WAV stems."""

    def __init__(self, folder_path: Path):
        self.folder_path = Path(folder_path).resolve()
        if not self.folder_path.is_dir():
            raise NotADirectoryError(f"Directory not found: {folder_path}")

        self._sample_rate: int = 48000
        self._tracks: List[TrackInfo] = []
        self._markers: List[MarkerInfo] = []
        self._total_duration_samples: int = 0

        self._parse_folder()

    def _parse_folder(self):
        wav_files = sorted(list(self.folder_path.glob("*.wav")) + list(self.folder_path.glob("*.WAV")))
        max_samples = 0

        for idx, f in enumerate(wav_files, start=1):
            try:
                info = sf.info(str(f))
                if info.samplerate > 0 and self._sample_rate == 48000:
                    self._sample_rate = info.samplerate

                clip = ClipInfo(
                    name=f.stem,
                    file_path=f,
                    start_sample=0,
                    end_sample=info.frames,
                    source_in=0,
                    source_out=info.frames
                )
                self._tracks.append(TrackInfo(track_id=str(idx), name=f.stem, clips=[clip]))
                if info.frames > max_samples:
                    max_samples = info.frames
            except Exception:
                continue

        self._total_duration_samples = max_samples

    def get_sample_rate(self) -> int:
        return self._sample_rate

    def get_tracks(self) -> List[TrackInfo]:
        return self._tracks

    def get_markers(self) -> List[MarkerInfo]:
        return self._markers

    def get_total_duration_sec(self) -> float:
        return self._total_duration_samples / float(self._sample_rate) if self._sample_rate > 0 else 0.0

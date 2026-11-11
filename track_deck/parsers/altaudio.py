"""Altered Audio Editor (.altaudio) Session Parser."""

import json
from pathlib import Path
from typing import Dict, List, Optional

from track_deck.parsers.base import BaseSessionParser, ClipInfo, MarkerInfo, TrackInfo


class AltAudioParser(BaseSessionParser):
    """Parser for Altered Audio Editor JSON session files (.altaudio)."""

    def __init__(self, altaudio_path: Path):
        self.altaudio_path = Path(altaudio_path).resolve()
        if not self.altaudio_path.is_file():
            raise FileNotFoundError(f"Altered Audio session not found: {altaudio_path}")

        try:
            self.data = json.loads(self.altaudio_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise ValueError(f"Failed to parse .altaudio JSON: {e}")

        self.session_dir = self.altaudio_path.parent
        self._sample_rate: int = int(self.data.get("sample_rate", 48000))
        self._tracks: List[TrackInfo] = []
        self._markers: List[MarkerInfo] = []
        self._total_duration_samples: int = 0

        self._parse_session()

    def _parse_session(self):
        # 1. Resolve media files map: media_id -> Path
        media_map: Dict[str, Path] = {}
        for m in self.data.get("media", []):
            m_id = m.get("id")
            rel_path = m.get("relative_path")
            abs_path = m.get("path")

            resolved: Optional[Path] = None
            if rel_path:
                cand = self.session_dir / rel_path
                if cand.is_file():
                    resolved = cand
                else:
                    # Normalized slashes
                    cand2 = self.session_dir / rel_path.replace("\\", "/")
                    if cand2.is_file():
                        resolved = cand2

            if not resolved and abs_path:
                cand3 = Path(abs_path)
                if cand3.is_file():
                    resolved = cand3

            if m_id and resolved:
                media_map[m_id] = resolved

        # 2. Parse tracks and clips
        max_sample = 0
        for t_idx, t in enumerate(self.data.get("tracks", []), start=1):
            t_id = str(t.get("id", t_idx))
            t_name = t.get("name", f"Track {t_idx}").strip()

            clips: List[ClipInfo] = []
            for c in t.get("clips", []):
                m_id = c.get("media_id")
                fpath = media_map.get(m_id)
                if not fpath:
                    continue

                start = int(c.get("start", 0))
                src_in = int(c.get("source_in", 0))
                src_out = int(c.get("source_out", src_in))
                dur = src_out - src_in
                end = start + dur

                gain_db = float(c.get("gain_db", 0.0))
                is_muted = bool(c.get("muted", False))
                vol = (10.0 ** (gain_db / 20.0)) if not is_muted else 0.0

                clips.append(ClipInfo(
                    name=c.get("name", fpath.stem),
                    file_path=fpath,
                    start_sample=start,
                    end_sample=end,
                    source_in=src_in,
                    source_out=src_out,
                    volume=vol
                ))

                if end > max_sample:
                    max_sample = end

            if clips:
                self._tracks.append(TrackInfo(track_id=t_id, name=t_name, clips=clips))

        self._total_duration_samples = max_sample

        # 3. Parse Markers
        for idx, m in enumerate(self.data.get("markers", []), start=1):
            name = m.get("name", f"Marker {idx}").strip()
            pos = int(m.get("position", 0))
            dur = int(m.get("duration", 0))
            kind = m.get("kind", "cue")

            m_type = "Range" if dur > 0 else "Cue"

            self._markers.append(MarkerInfo(
                marker_id=f"marker-{idx:03d}",
                name=name,
                start_sample=pos,
                duration_samples=dur,
                sample_rate=self._sample_rate,
                marker_type=m_type
            ))

        # Sort markers chronologically
        self._markers.sort(key=lambda m: m.start_sample)

    def get_sample_rate(self) -> int:
        return self._sample_rate

    def get_tracks(self) -> List[TrackInfo]:
        return self._tracks

    def get_markers(self) -> List[MarkerInfo]:
        return self._markers

    def get_total_duration_sec(self) -> float:
        return self._total_duration_samples / float(self._sample_rate) if self._sample_rate > 0 else 0.0

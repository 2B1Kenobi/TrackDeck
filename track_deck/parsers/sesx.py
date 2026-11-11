"""Adobe Audition (.sesx) Session Parser."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional

import soundfile as sf

from track_deck.parsers.base import BaseSessionParser, ClipInfo, MarkerInfo, TrackInfo


class AuditionSesxParser(BaseSessionParser):
    """Parser for Adobe Audition Multitrack XML Session files (.sesx)."""

    def __init__(self, sesx_path: Path):
        self.sesx_path = Path(sesx_path).resolve()
        if not self.sesx_path.is_file():
            raise FileNotFoundError(f"Audition session not found: {sesx_path}")

        self.root = ET.parse(self.sesx_path).getroot()
        self.session_dir = self.sesx_path.parent
        self._sample_rate: int = 48000
        self._tracks: List[TrackInfo] = []
        self._markers: List[MarkerInfo] = []
        self._total_duration_samples: int = 0

        self._parse_session()

    def _parse_session(self):
        # 1. Parse referenced files map: fileID -> Path
        files_map: Dict[str, Path] = {}
        for f_elem in self.root.findall(".//file"):
            f_id = f_elem.attrib.get("id")
            rel_path = f_elem.attrib.get("relativePath")
            if not rel_path and f_elem.find("relativePath") is not None:
                rel_path = f_elem.find("relativePath").text
            abs_path = f_elem.attrib.get("absolutePath")

            resolved_path: Optional[Path] = None
            if rel_path:
                cand = self.session_dir / rel_path
                if cand.is_file():
                    resolved_path = cand
                else:
                    # Windows separator normalization
                    clean_rel = rel_path.replace("\\", "/")
                    cand2 = self.session_dir / clean_rel
                    if cand2.is_file():
                        resolved_path = cand2

            if not resolved_path and abs_path:
                cand3 = Path(abs_path)
                if cand3.is_file():
                    resolved_path = cand3
                else:
                    # Check in Recorded folder sibling
                    fname = cand3.name
                    cand4 = self.session_dir / f"{self.sesx_path.stem}_Recorded" / fname
                    if cand4.is_file():
                        resolved_path = cand4
                    else:
                        for sub in self.session_dir.glob("*Recorded*"):
                            if (sub / fname).is_file():
                                resolved_path = sub / fname
                                break

            if f_id and resolved_path:
                files_map[f_id] = resolved_path

        # Determine sample rate from first resolved file
        for p in files_map.values():
            try:
                info = sf.info(str(p))
                if info.samplerate > 0:
                    self._sample_rate = info.samplerate
                    break
            except Exception:
                pass

        # 2. Parse tracks and clips
        max_sample = 0
        for track_elem in self.root.findall(".//audioTrack"):
            t_id = track_elem.attrib.get("id", "0")
            name_elem = track_elem.find("name")
            track_name = name_elem.text.strip() if (name_elem is not None and name_elem.text) else None

            clips: List[ClipInfo] = []
            for c_elem in track_elem.findall(".//audioClip"):
                c_name = c_elem.find("name").text if c_elem.find("name") is not None else ""
                f_id = c_elem.attrib.get("fileID")
                f_path = files_map.get(f_id)
                if not f_path or not f_path.is_file():
                    continue

                start = int(c_elem.attrib.get("startPoint", 0))
                end = int(c_elem.attrib.get("endPoint", 0))
                src_in = int(c_elem.attrib.get("sourceIn", 0))
                src_out = int(c_elem.attrib.get("sourceOut", 0))

                clips.append(ClipInfo(
                    name=c_name or f_path.stem,
                    file_path=f_path,
                    start_sample=start,
                    end_sample=end,
                    source_in=src_in,
                    source_out=src_out
                ))
                if end > max_sample:
                    max_sample = end

            if not clips:
                continue

            # If track name was not explicitly set in Audition, infer from clip filename
            if not track_name:
                first_clip_file = clips[0].file_path.stem
                # E.g. "DRUM HIGH_001_1" -> "DRUM HIGH"
                inferred = re.sub(r"_\d+(_\d+)?$", "", first_clip_file).strip()
                track_name = inferred or f"Track {t_id}"

            self._tracks.append(TrackInfo(track_id=t_id, name=track_name, clips=clips))

        self._total_duration_samples = max_sample

        # 3. Parse Markers from XMP Metadata
        self._parse_markers()

    def _parse_markers(self):
        """Extract song markers from Audition XMP Metadata."""
        xmp_elem = self.root.find(".//xmpMetadata")
        if xmp_elem is None or not xmp_elem.text:
            return

        xmp_text = xmp_elem.text
        try:
            # Parse inner XML
            xmp_root = ET.fromstring(xmp_text)
        except Exception:
            return

        # Look for marker tags across namespaces
        raw_markers = []
        for elem in xmp_root.iter():
            tag_lower = elem.tag.lower()
            if "marker" in tag_lower and elem.find(".//{*}name") is not None or elem.find(".//{*}startTime") is not None:
                name_el = elem.find(".//{*}name")
                start_el = elem.find(".//{*}startTime")
                dur_el = elem.find(".//{*}duration")
                type_el = elem.find(".//{*}type") or elem.find(".//{*}cuePointType")

                name = name_el.text.strip() if name_el is not None and name_el.text else "Marker"
                start = int(start_el.text.strip()) if start_el is not None and start_el.text and start_el.text.isdigit() else 0
                dur = int(dur_el.text.strip()) if dur_el is not None and dur_el.text and dur_el.text.isdigit() else 0
                m_type = type_el.text.strip() if type_el is not None and type_el.text else ("Range" if dur > 0 else "Cue")

                raw_markers.append({
                    "name": name,
                    "start": start,
                    "duration": dur,
                    "type": m_type
                })

        # Sort markers by start time
        raw_markers.sort(key=lambda m: m["start"])

        # Convert to MarkerInfo
        for idx, rm in enumerate(raw_markers):
            start = rm["start"]
            dur = rm["duration"]
            m_type = rm["type"]

            # If it's a cue point marker with duration 0, extend to next marker or total duration
            if dur == 0:
                if idx + 1 < len(raw_markers):
                    dur = max(0, raw_markers[idx + 1]["start"] - start)
                else:
                    dur = max(0, self._total_duration_samples - start)

            self._markers.append(MarkerInfo(
                marker_id=f"marker-{idx+1:03d}",
                name=rm["name"],
                start_sample=start,
                duration_samples=dur,
                sample_rate=self._sample_rate,
                marker_type=m_type
            ))

    def get_sample_rate(self) -> int:
        return self._sample_rate

    def get_tracks(self) -> List[TrackInfo]:
        return self._tracks

    def get_markers(self) -> List[MarkerInfo]:
        return self._markers

    def get_total_duration_sec(self) -> float:
        return self._total_duration_samples / float(self._sample_rate) if self._sample_rate > 0 else 0.0

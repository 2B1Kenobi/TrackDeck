"""High-Headroom 32-bit Float Audio Bus Summer for StemDeck."""

import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf

from track_deck.parsers.base import BaseSessionParser, TrackInfo

STEM_NAMES = ["drums", "bass", "guitar", "piano", "vocals", "other"]


def sum_and_render_stems(
    parser: BaseSessionParser,
    mapping: Dict[str, str],
    start_sample: int,
    end_sample: int,
    output_dir: Path,
    target_lufs: float = -14.0
) -> Dict[str, Path]:
    """Sum multitrack channels into 6 discrete stems and master mix without AI separation artifacts.
    
    Returns dict mapping stem name to generated WAV file path.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    sample_rate = parser.get_sample_rate()
    total_frames = end_sample - start_sample

    if total_frames <= 0:
        raise ValueError(f"Invalid frame range: start={start_sample}, end={end_sample}")

    # Allocate 32-bit float stereo accumulation buffers for each stem
    buffers: Dict[str, np.ndarray] = {
        stem: np.zeros((total_frames, 2), dtype=np.float32) for stem in STEM_NAMES
    }

    tracks = parser.get_tracks()
    rendered_tracks_count = 0

    print(f"[*] Summing {len(tracks)} multitrack channels into 6 lossless stems...")
    print(f"    Timeline Range: samples {start_sample} to {end_sample} ({total_frames / sample_rate:.2f}s)")

    for track in tracks:
        target_stem = mapping.get(track.name, "other").lower().strip()
        if target_stem == "ignore" or target_stem not in buffers:
            continue

        for clip in track.clips:
            # Check overlap between clip [clip.start_sample, clip.end_sample) and [start_sample, end_sample)
            c_start = clip.start_sample
            c_end = clip.end_sample

            overlap_start = max(c_start, start_sample)
            overlap_end = min(c_end, end_sample)

            if overlap_end <= overlap_start:
                continue

            # Calculate offsets inside audio file
            offset_in_clip = overlap_start - c_start
            length_to_read = overlap_end - overlap_start

            read_file_start = clip.source_in + offset_in_clip
            read_file_stop = read_file_start + length_to_read

            try:
                clip_audio, sr = sf.read(
                    str(clip.file_path),
                    start=read_file_start,
                    stop=read_file_stop,
                    dtype="float32",
                    always_2d=True
                )
            except Exception as e:
                print(f"[!] Warning: Failed to read clip {clip.name} from {clip.file_path.name}: {e}")
                continue

            if clip_audio.shape[0] == 0:
                continue

            # If mono, replicate to 2 channels
            if clip_audio.shape[1] == 1:
                clip_audio = np.repeat(clip_audio, 2, axis=1)

            # Apply clip volume if specified
            if clip.volume != 1.0:
                clip_audio = clip_audio * float(clip.volume)

            # Destination indices in stem buffer
            dest_start = overlap_start - start_sample
            dest_end = dest_start + clip_audio.shape[0]

            buffers[target_stem][dest_start:dest_end] += clip_audio
            rendered_tracks_count += 1

    # 4. Synthesize Full Master Mix Buffer
    mix_buffer = np.zeros((total_frames, 2), dtype=np.float32)
    for stem_buf in buffers.values():
        mix_buffer += stem_buf

    # 5. Headroom & Peak Normalization
    # Check max peak across the entire mix
    mix_peak = float(np.max(np.abs(mix_buffer)))
    scale_factor = 1.0

    if mix_peak > 0.0:
        if mix_peak > 0.95:
            # Prevent digital clipping: scale down so master peak reaches -0.5 dBFS (0.944)
            scale_factor = 0.944 / mix_peak
            print(f"[*] Attenuating mix by {20 * math.log10(scale_factor):.1f} dBFS to prevent summing clipping.")
        elif mix_peak < 0.25:
            # Boost quiet live recording to reasonable audition level (-1.0 dBFS peak)
            scale_factor = min(4.0, 0.891 / mix_peak)
            print(f"[*] Boosting quiet recording by +{20 * math.log10(scale_factor):.1f} dBFS.")

    # Apply scaling across all stems and master mix proportionally
    if scale_factor != 1.0:
        mix_buffer *= scale_factor
        for stem_name in buffers:
            buffers[stem_name] *= scale_factor

    # 6. Write Audio Files to Output Directory
    result_paths: Dict[str, Path] = {}
    print(f"[*] Exporting 24-bit PCM stems to: {output_dir.name}/")

    for stem_name, stem_data in buffers.items():
        out_wav = output_dir / f"{stem_name}.wav"
        sf.write(str(out_wav), stem_data, sample_rate, subtype="PCM_24")
        result_paths[stem_name] = out_wav

    # Write mix.wav and source.wav
    mix_wav = output_dir / "mix.wav"
    sf.write(str(mix_wav), mix_buffer, sample_rate, subtype="PCM_24")
    result_paths["mix"] = mix_wav

    source_wav = output_dir.parent / "source.wav"
    sf.write(str(source_wav), mix_buffer, sample_rate, subtype="PCM_24")
    result_paths["source"] = source_wav

    return result_paths

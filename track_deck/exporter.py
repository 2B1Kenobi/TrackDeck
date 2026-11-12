"""TrackDeck Cloud & Rehearsal Player Exporter.

Prepares and exports StemDeck jobs into static web stem players (like 4StemPlayer / PWA)
for weekly rehearsal distribution with dynamic N-stem faders, waveforms, and lyrics.
"""

import json
import re
import secrets
import string
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from track_deck.injector import get_default_stemdeck_jobs_dir


def sanitize_folder_name(name: str) -> str:
    """Sanitize song title into safe folder and filename prefix."""
    s = re.sub(r'[^a-zA-Z0-9_\-]', '', name.strip().replace(" ", ""))
    return s or "Song"


def compute_audio_peaks(audio_path: Path, sample_rate: int = 8000, samples_per_pixel: int = 512) -> List[float]:
    """Compute normalized peak envelope matching 4StemPlayer / Web Audio canvas specs."""
    try:
        proc = subprocess.run(
            [
                "ffmpeg", "-v", "error",
                "-i", str(audio_path),
                "-ac", "1",
                "-ar", str(sample_rate),
                "-f", "f32le",
                "pipe:1"
            ],
            capture_output=True,
            check=True
        )
        samples = np.frombuffer(proc.stdout, dtype=np.float32)
        if len(samples) == 0:
            return []

        num_chunks = int(np.ceil(len(samples) / samples_per_pixel))
        peaks = []
        for i in range(num_chunks):
            chunk = samples[i * samples_per_pixel : (i + 1) * samples_per_pixel]
            if len(chunk) > 0:
                peaks.append(round(float(np.max(np.abs(chunk))), 4))
            else:
                peaks.append(0.0)
        return peaks
    except Exception as e:
        print(f"    [!] Warning: Failed to compute peaks for {audio_path.name}: {e}")
        return []


def export_job_to_target(
    job_id: str,
    target_root: Path,
    jobs_dir: Optional[Path] = None,
    bitrate: str = "256k"
) -> Optional[Dict[str, Any]]:
    """Export a single StemDeck job into the target static player repository."""
    jobs_dir = jobs_dir or get_default_stemdeck_jobs_dir()
    job_dir = jobs_dir / job_id
    if not job_dir.is_dir():
        print(f"[!] Error: StemDeck job directory not found: {job_dir}")
        return None

    stems_dir = job_dir / "stems"
    if not stems_dir.is_dir():
        print(f"[!] Error: Stems directory not found for job: {job_id}")
        return None

    # Load job metadata
    meta_path = job_dir / "metadata.json"
    metadata: Dict[str, Any] = {}
    if meta_path.is_file():
        try:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # If metadata is empty or missing title, inspect registry.json
    registry_file = jobs_dir / "registry.json"
    if registry_file.is_file():
        try:
            reg_data = json.loads(registry_file.read_text(encoding="utf-8"))
            for j in reg_data.get("jobs", []):
                if j.get("id") == job_id:
                    for k, v in j.items():
                        if k not in metadata or not metadata[k]:
                            metadata[k] = v
                    break
        except Exception:
            pass

    title = metadata.get("title") or job_id
    artist = metadata.get("artist") or "Worship Team"
    key = metadata.get("key") or "C"
    bpm = metadata.get("bpm") or 120
    dur = float(metadata.get("duration_sec") or 0.0)
    sections = metadata.get("sections") or []

    folder_name = sanitize_folder_name(title)

    # Determine song directories (support both static/songs and public/songs if present)
    target_dirs = []
    if (target_root / "static").is_dir():
        target_dirs.append(target_root / "static" / "songs" / folder_name)
    if (target_root / "public").is_dir():
        target_dirs.append(target_root / "public" / "songs" / folder_name)
    if not target_dirs:
        # Fallback to direct songs folder
        target_dirs.append(target_root / "songs" / folder_name)

    primary_song_dir = target_dirs[0]
    for d in target_dirs:
        d.mkdir(parents=True, exist_ok=True)

    print(f"[*] Exporting '{title}' ({job_id}) -> {primary_song_dir.name}/")

    # Preferred order of stems; any additional stems found will follow
    standard_order = ["vocals", "guitar", "piano", "keys", "strings", "drums", "bass", "fx", "other"]
    all_stem_files = list(stems_dir.glob("*.wav")) + list(stems_dir.glob("*.flac")) + list(stems_dir.glob("*.mp3"))
    all_stems_dict = {f.stem.lower(): f for f in all_stem_files}

    ordered_stem_names = [s for s in standard_order if s in all_stems_dict]
    for s in sorted(all_stems_dict.keys()):
        if s not in ordered_stem_names:
            ordered_stem_names.append(s)

    found_stems = {}
    peaks_map = {}

    for stem_name in ordered_stem_names:
        wav_file = all_stems_dict[stem_name]

        out_mp3_name = f"{folder_name}_{stem_name}.mp3"
        out_peaks_name = f"{folder_name}_{stem_name}.peaks.json"

        # Transcode to MP3 in all target directories
        print(f"    - Transcoding stem: {stem_name} ({bitrate} MP3)...")
        first_mp3 = primary_song_dir / out_mp3_name
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error",
                "-i", str(wav_file),
                "-b:a", bitrate,
                str(first_mp3)
            ],
            check=True
        )

        # Compute waveform peaks
        print(f"    - Computing waveform peaks: {stem_name}...")
        peaks = compute_audio_peaks(first_mp3)
        peaks_payload = {
            "sampleRate": 8000,
            "samplesPerPixel": 512,
            "peaks": peaks
        }
        first_peaks_file = primary_song_dir / out_peaks_name
        first_peaks_file.write_text(json.dumps(peaks_payload), encoding="utf-8")

        # Copy to other target dirs if multi-target (e.g. public/)
        import shutil
        for other_dir in target_dirs[1:]:
            shutil.copy2(first_mp3, other_dir / out_mp3_name)
            shutil.copy2(first_peaks_file, other_dir / out_peaks_name)

        found_stems[stem_name] = f"/songs/{folder_name}/{out_mp3_name}"
        peaks_map[stem_name] = f"/songs/{folder_name}/{out_peaks_name}"

    # If duration wasn't in metadata, probe the first audio stem
    if dur <= 0 and found_stems and primary_song_dir:
        first_stem_name = list(found_stems.keys())[0]
        test_file = primary_song_dir / f"{folder_name}_{first_stem_name}.mp3"
        if test_file.is_file():
            try:
                probe_res = subprocess.run(
                    [
                        "ffprobe", "-v", "error",
                        "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1",
                        str(test_file)
                    ],
                    capture_output=True,
                    text=True,
                    check=True
                )
                dur = float(probe_res.stdout.strip())
            except Exception:
                pass

    # Generate song.json
    song_json_data = {
        "title": title,
        "artist": artist,
        "key": key,
        "bpm": int(round(bpm)),
        "timeSignature": "4/4",
        "duration": f"{int(dur // 60)}:{int(dur % 60):02d}",
        "durationSeconds": int(round(dur)),
        "sections": [
            {
                "label": s.get("name") or s.get("label", f"Section {i+1}"),
                "start": int(round(s.get("start", 0)))
            }
            for i, s in enumerate(sections)
        ]
    }

    for d in target_dirs:
        (d / "song.json").write_text(json.dumps(song_json_data, indent=2) + "\n", encoding="utf-8")

    # Copy lyrics if available
    lyrics_txt = job_dir / "lyrics.txt"
    lyrics_json = job_dir / "lyrics.json"
    chordpro_file = job_dir / "song.chordpro"

    lyrics_content = ""
    if lyrics_txt.is_file():
        lyrics_content = lyrics_txt.read_text(encoding="utf-8")
    elif lyrics_json.is_file():
        try:
            lj = json.loads(lyrics_json.read_text(encoding="utf-8"))
            lines = [line.get("text", "") for line in lj.get("lines", []) if line.get("text")]
            lyrics_content = "\n".join(lines)
        except Exception:
            pass

    if not lyrics_content and chordpro_file.is_file():
        lyrics_content = chordpro_file.read_text(encoding="utf-8")

    if lyrics_content:
        for d in target_dirs:
            (d / "lyrics.md").write_text(lyrics_content.strip() + "\n", encoding="utf-8")

    manifest_entry = {
        "id": folder_name,
        "folder": folder_name,
        "title": title,
        "artist": artist,
        "bpm": int(round(bpm)),
        "key": key,
        "timeSignature": "4/4",
        "songJsonUrl": f"/songs/{folder_name}/song.json",
        "lyricsUrl": f"/songs/{folder_name}/lyrics.md" if lyrics_content else "",
        "stems": found_stems,
        "peaks": peaks_map
    }

    print(f"[+] Successfully exported '{title}' with {len(found_stems)} stems.")
    return manifest_entry


def update_manifest_file(songs_dir: Path, new_entries: List[Dict[str, Any]]) -> None:
    """Update or create manifest.json in the songs root directory."""
    manifest_file = songs_dir / "manifest.json"
    data = {"generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "songs": []}

    if manifest_file.is_file():
        try:
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception:
            data = {"generatedAt": "", "songs": []}

    existing_songs = {s["id"]: s for s in data.get("songs", [])}
    for entry in new_entries:
        existing_songs[entry["id"]] = entry

    data["generatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    data["songs"] = list(existing_songs.values())

    manifest_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"[+] Updated manifest: {manifest_file} ({len(data['songs'])} total songs)")


def rotate_rehearsal_auth(target_root: Path) -> Optional[Dict[str, Any]]:
    """Generate and write a new weekly time-bounded passkey tied to Philippine time (PHT / UTC+8)."""
    import secrets
    from datetime import datetime, timedelta, timezone

    # Philippine Time is UTC+8
    pht = timezone(timedelta(hours=8))
    now_pht = datetime.now(pht)
    days_ahead = (6 - now_pht.weekday()) % 7
    if days_ahead == 0 and (now_pht.hour >= 23 and now_pht.minute >= 59):
        days_ahead = 7

    # Calculate expiration timestamp for Monday 06:00:00 AM PHT after upcoming Sunday
    target_sunday = now_pht + timedelta(days=days_ahead)
    after_sunday = target_sunday + timedelta(days=1)
    expiry_pht = after_sunday.replace(hour=6, minute=0, second=0, microsecond=0)
    expiry_utc = expiry_pht.astimezone(timezone.utc)
    expiry_ts = int(expiry_utc.timestamp())

    # 100% cryptographically random 128-bit entropy passkey (no predictable dates or patterns)
    alphabet = string.ascii_letters + string.digits
    raw_key = "".join(secrets.choice(alphabet) for _ in range(16))
    weekly_key = f"{raw_key[0:4]}-{raw_key[4:8]}-{raw_key[8:12]}-{raw_key[12:16]}"
    key_id = f"set-{secrets.token_hex(6)}"
    salt = secrets.token_hex(32)
    expires_str = expiry_pht.strftime("%A, %b %d, %Y %I:%M:%S %p PHT (UTC+8)")

    functions_dir = target_root / "functions"
    if not functions_dir.is_dir():
        return None

    config_js = functions_dir / "auth_config.js"
    content = (
        f"// Generated automatically by TrackDeck export\n"
        f"export const authConfig = {{\n"
        f'  weeklyKey: "{weekly_key}",\n'
        f'  keyId: "{key_id}",\n'
        f"  validUntil: {expiry_ts},\n"
        f'  expiresPHT: "{expires_str}",\n'
        f'  salt: "{salt}"\n'
        f"}};\n"
    )
    config_js.write_text(content, encoding="utf-8")
    return {
        "weekly_key": weekly_key,
        "valid_until_ts": expiry_ts,
        "expires_str": expires_str,
        "target_sunday": target_sunday
    }


def export_jobs_command(target_dir_str: str, job_ids: List[str]) -> int:
    """Execute the 'trackdeck export <target_dir> <job_id>...' command."""
    target_root = Path(target_dir_str).expanduser().resolve()
    if not target_root.is_dir():
        print(f"[!] Error: Target directory does not exist: {target_dir_str}")
        print("    Please specify the root of the rehearsal player git repository.")
        return 1

    if not job_ids:
        print("[!] Error: No job IDs specified.")
        print("    Usage: trackdeck export <target-directory> <job_id> [job_id ...]")
        return 1

    print("=" * 78)
    print(f"  TrackDeck Export: Rehearsal Player Static Assets")
    print(f"  Target Repository: {target_root}")
    print(f"  Jobs to Export:    {len(job_ids)}")
    print("=" * 78)

    exported_entries = []
    for jid in job_ids:
        entry = export_job_to_target(jid, target_root)
        if entry:
            exported_entries.append(entry)

    if not exported_entries:
        print("[!] Warning: No jobs were exported.")
        return 1

    # Update manifest.json in both static/songs and public/songs if present
    if (target_root / "static" / "songs").is_dir():
        update_manifest_file(target_root / "static" / "songs", exported_entries)
    if (target_root / "public" / "songs").is_dir():
        update_manifest_file(target_root / "public" / "songs", exported_entries)
    if not (target_root / "static").is_dir() and not (target_root / "public").is_dir():
        update_manifest_file(target_root / "songs", exported_entries)

    # Roll weekly time-bounded passkey if target has functions/
    auth_info = rotate_rehearsal_auth(target_root)

    print("\n" + "=" * 78)
    print(f"[+] Export complete! {len(exported_entries)} song(s) prepared in {target_root.name}/.")
    if auth_info:
        print("-" * 78)
        print("  Weekly Rehearsal Security (Philippine Standard Time, UTC+8):")
        print(f"    Weekly Passcode:  {auth_info['weekly_key']}")
        print(f"    Valid Through:    {auth_info['expires_str']}")
        print(f"    1-Tap Team Link:  https://jiamakati-practice.pages.dev/#{auth_info['weekly_key']}")
        print("-" * 78)
    print("    Ready to deploy:")
    print(f"      cd \"{target_root}\" && git add . && git commit -m \"Update rehearsal set\" && git push")
    print("=" * 78)
    return 0

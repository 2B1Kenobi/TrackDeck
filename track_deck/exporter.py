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


def format_nerv_minimal_lyrics(text: str) -> str:
    """Format lyrics into minimal, non-repeating NERV sectioned markdown."""
    if not text or not text.strip():
        return ""

    # Strip YAML frontmatter if present
    cleaned = re.sub(r"^---[\s\S]*?---\s*", "", text.strip())

    header_bracket_re = re.compile(r"^\s*\[\s*([^\]]+?)\s*(?:\([^\)]+\))?\s*\]\s*$")
    header_colon_re = re.compile(r"^\s*([A-Za-z0-9\s_-]+):\s*$")

    lines = cleaned.splitlines()
    sections = []
    curr_header = ""
    curr_lines = []

    for line in lines:
        raw_l = line.strip()
        # Skip ChordPro directives
        if raw_l.startswith("{") and raw_l.endswith("}"):
            continue

        m_b = header_bracket_re.match(raw_l)
        m_c = header_colon_re.match(raw_l)

        if m_b or m_c:
            if curr_lines or curr_header:
                sections.append((curr_header, curr_lines))
                curr_lines = []
            curr_header = m_b.group(1).title() if m_b else m_c.group(1).title()
            continue

        if not raw_l:
            if curr_lines:
                sections.append((curr_header, curr_lines))
                curr_header = ""
                curr_lines = []
            continue

        # Strip inline chords like [Em7]
        clean_l = re.sub(r"\[[^\]]*\]", "", raw_l).strip()
        clean_l = re.sub(r"\s+", " ", clean_l)
        if clean_l:
            curr_lines.append(clean_l)

    if curr_lines or curr_header:
        sections.append((curr_header, curr_lines))

    # Deduplicate non-unique sections (keep only unique stanzas)
    seen_content = set()
    out_sections = []

    for header, s_lines in sections:
        if not s_lines:
            continue
        # Signature based on alphanumeric lowercase text
        sig = " ".join(re.sub(r"[^a-z0-9]", "", l.lower()) for l in s_lines)
        if not sig or sig in seen_content:
            continue
        seen_content.add(sig)

        formatted_block = []
        if header:
            formatted_block.append(header.rstrip(":") + ":")
        formatted_block.extend(s_lines)
        out_sections.append("\n".join(formatted_block))

    return "\n\n".join(out_sections).strip()


def resolve_job_lyrics(job_dir: Path, title: str) -> str:
    """Resolve job lyrics with nerv.md as top priority, formatted minimally."""
    exports_dir = Path.home() / "Documents" / "StemDeck" / "exports"
    safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip()

    seen_cands = set()
    nerv_candidates = [
        job_dir / "song.nerv.md",
        *job_dir.glob("*.nerv.md"),
    ]
    if exports_dir.is_dir():
        nerv_candidates.extend([
            exports_dir / f"{title}.nerv.md",
            exports_dir / f"{safe_title}.nerv.md",
            *exports_dir.glob(f"*{safe_title}*.nerv.md"),
        ])

    # 1. Priority 1: *.nerv.md
    for cand in nerv_candidates:
        if cand in seen_cands:
            continue
        seen_cands.add(cand)
        if cand.is_file():
            try:
                raw_text = cand.read_text(encoding="utf-8", errors="replace")
                formatted = format_nerv_minimal_lyrics(raw_text)
                if formatted:
                    return formatted
            except Exception:
                pass

    # 2. Priority 2: lyrics.txt
    lyrics_txt = job_dir / "lyrics.txt"
    if lyrics_txt.is_file():
        try:
            raw_text = lyrics_txt.read_text(encoding="utf-8", errors="replace")
            formatted = format_nerv_minimal_lyrics(raw_text)
            if formatted:
                return formatted
        except Exception:
            pass

    # 3. Priority 3: lyrics.json
    lyrics_json = job_dir / "lyrics.json"
    if lyrics_json.is_file():
        try:
            lj = json.loads(lyrics_json.read_text(encoding="utf-8"))
            lines = [line.get("text", "") for line in lj.get("lines", []) if line.get("text")]
            raw_text = "\n".join(lines)
            formatted = format_nerv_minimal_lyrics(raw_text)
            if formatted:
                return formatted
        except Exception:
            pass

    # 4. Priority 4: song.chordpro
    chordpro_file = job_dir / "song.chordpro"
    if chordpro_file.is_file():
        try:
            raw_text = chordpro_file.read_text(encoding="utf-8", errors="replace")
            formatted = format_nerv_minimal_lyrics(raw_text)
            if formatted:
                return formatted
        except Exception:
            pass

    return ""


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


def get_default_player_dir() -> Path:
    """Resolve default static rehearsal player repository directory."""
    import os
    env_dir = os.environ.get("TRACKDECK_PLAYER_DIR")
    if env_dir and Path(env_dir).is_dir():
        return Path(env_dir).expanduser().resolve()

    default_proj = Path.home() / "Projects" / "4StemPlayer"
    if default_proj.is_dir():
        return default_proj

    cwd = Path.cwd()
    if (cwd / "functions").is_dir() or (cwd / "static" / "songs").is_dir() or (cwd / "public" / "songs").is_dir():
        return cwd

    return default_proj


def export_job_to_target(
    job_id: str,
    target_root: Path,
    jobs_dir: Optional[Path] = None,
    bitrate: str = "256k"
) -> Optional[Dict[str, Any]]:
    """Export a single StemDeck job into the target static player repository."""
    jobs_dir = jobs_dir or get_default_stemdeck_jobs_dir()
    if job_id == "latest":
        job_folders = [p for p in jobs_dir.iterdir() if p.is_dir() and p.name not in ("failed", "exports")]
        if not job_folders:
            print("[!] Error: No jobs found in StemDeck jobs directory.")
            return None
        job_dir = max(job_folders, key=lambda p: p.stat().st_mtime)
        job_id = job_dir.name
    else:
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

    # Resolve lyrics (Priority: nerv.md -> lyrics.txt -> lyrics.json -> song.chordpro)
    lyrics_content = resolve_job_lyrics(job_dir, title)
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


def clean_player_songs(target_root: Path) -> List[str]:
    """Clean all prior songs and their folders from target player repository."""
    import shutil
    cleaned_songs = []
    song_roots = []
    if (target_root / "static" / "songs").is_dir():
        song_roots.append(target_root / "static" / "songs")
    if (target_root / "public" / "songs").is_dir():
        song_roots.append(target_root / "public" / "songs")
    if not song_roots and (target_root / "songs").is_dir():
        song_roots.append(target_root / "songs")

    for s_root in song_roots:
        for item in list(s_root.iterdir()):
            if item.is_dir():
                try:
                    shutil.rmtree(item)
                    if item.name not in cleaned_songs:
                        cleaned_songs.append(item.name)
                except Exception as e:
                    print(f"    [!] Warning: Could not remove {item}: {e}")
            elif item.name == "manifest.json":
                try:
                    item.unlink(missing_ok=True)
                except Exception:
                    pass
    return cleaned_songs


def update_manifest_file(songs_dir: Path, new_entries: List[Dict[str, Any]], clean: bool = False) -> None:
    """Update or create manifest.json in the songs root directory."""
    manifest_file = songs_dir / "manifest.json"
    data = {"generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "songs": []}

    if not clean and manifest_file.is_file():
        try:
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception:
            data = {"generatedAt": "", "songs": []}

    existing_songs = {s["id"]: s for s in data.get("songs", [])} if not clean else {}
    for entry in new_entries:
        existing_songs[entry["id"]] = entry

    data["generatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    data["songs"] = list(existing_songs.values())

    manifest_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"[+] Updated manifest: {manifest_file} ({len(data['songs'])} total songs)")


def rotate_rehearsal_auth(target_root: Path, force: bool = True) -> Optional[Dict[str, Any]]:
    """Generate or retrieve weekly time-bounded passkey tied to Philippine time (PHT / UTC+8)."""
    import re
    import secrets
    from datetime import datetime, timedelta, timezone

    # Philippine Time is UTC+8
    pht = timezone(timedelta(hours=8))
    now_pht = datetime.now(pht)
    now_ts = int(datetime.now(timezone.utc).timestamp())

    functions_dir = target_root / "functions"
    if not functions_dir.is_dir():
        return None

    config_js = functions_dir / "auth_config.js"

    # If not forcing rotation (e.g. incremental export adding to active week set), reuse active passkey
    if not force and config_js.is_file():
        try:
            content = config_js.read_text(encoding="utf-8")
            m_key = re.search(r'weeklyKey:\s*"([^"]+)"', content)
            m_exp = re.search(r'validUntil:\s*(\d+)', content)
            if m_key and m_exp:
                valid_until = int(m_exp.group(1))
                if valid_until > now_ts:
                    return {
                        "weekly_key": m_key.group(1),
                        "valid_until_ts": valid_until,
                        "is_reused": True
                    }
        except Exception:
            pass

    # Calculate expiration timestamp for Monday 06:00:00 AM PHT after upcoming Sunday
    days_ahead = (6 - now_pht.weekday()) % 7
    if days_ahead == 0 and (now_pht.hour >= 23 and now_pht.minute >= 59):
        days_ahead = 7

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

    content = (
        f"// Generated automatically by TrackDeck\n"
        f"export const authConfig = {{\n"
        f'  weeklyKey: "{weekly_key}",\n'
        f'  keyId: "{key_id}",\n'
        f"  validUntil: {expiry_ts},\n"
        f'  salt: "{salt}"\n'
        f"}};\n"
    )
    config_js.write_text(content, encoding="utf-8")
    return {
        "weekly_key": weekly_key,
        "valid_until_ts": expiry_ts,
        "expires_str": expires_str,
        "target_sunday": target_sunday,
        "is_reused": False
    }


def export_jobs_command(target_dir_str: Optional[str], job_ids: List[str], clean: bool = False) -> int:
    """Execute 'trackdeck export' (incremental add) or 'trackdeck publish' (clean fresh cycle)."""
    action_label = "Publish (Fresh Cycle)" if clean else "Export (Additive)"
    if target_dir_str:
        target_root = Path(target_dir_str).expanduser().resolve()
    else:
        target_root = get_default_player_dir()

    if not target_root.is_dir():
        print(f"[!] Error: Target directory does not exist: {target_root}")
        print("    Please specify the root of the rehearsal player git repository via --dir.")
        return 1

    if not job_ids:
        print("[!] Error: No job IDs specified.")
        cmd_name = "publish" if clean else "export"
        print(f"    Usage: trackdeck {cmd_name} <job_id> [job_id ...]")
        return 1

    print("=" * 78)
    print(f"  TrackDeck {action_label}: Rehearsal Player Static Assets")
    print(f"  Target Repository: {target_root}")
    print(f"  Jobs to Process:   {len(job_ids)}")
    print("=" * 78)

    if clean:
        cleaned_songs = clean_player_songs(target_root)
        if cleaned_songs:
            print(f"[*] Cleaned {len(cleaned_songs)} prior song(s) from {target_root.name} for fresh cycle:")
            for s in cleaned_songs:
                print(f"    - Removed prior song: {s}")
        else:
            print(f"[*] Songs directory is clean in {target_root.name}.")

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
        update_manifest_file(target_root / "static" / "songs", exported_entries, clean=clean)
    if (target_root / "public" / "songs").is_dir():
        update_manifest_file(target_root / "public" / "songs", exported_entries, clean=clean)
    if not (target_root / "static").is_dir() and not (target_root / "public").is_dir():
        update_manifest_file(target_root / "songs", exported_entries, clean=clean)

    # Roll or preserve weekly time-bounded passkey if target has functions/
    auth_info = rotate_rehearsal_auth(target_root, force=clean)

    print("\n" + "=" * 78)
    if clean:
        print(f"[+] Publish complete! Fresh cycle with {len(exported_entries)} song(s) published in {target_root.name}/.")
    else:
        print(f"[+] Export complete! {len(exported_entries)} song(s) exported into {target_root.name}/.")

    if auth_info:
        reused_tag = " (active weekly key preserved)" if auth_info.get("is_reused") else " (new cycle passkey generated)"
        print("-" * 78)
        print(f"  Weekly Rehearsal Security{reused_tag}:")
        print(f"    Weekly Passcode:  {auth_info['weekly_key']}")
        if auth_info.get("expires_str"):
            print(f"    Valid Through:    {auth_info['expires_str']}")
        print(f"    1-Tap Team Link:  https://jiamakati-practice.pages.dev/#{auth_info['weekly_key']}")
        print("-" * 78)
    print("    Ready to deploy:")
    print(f"      trackdeck sync \"Update rehearsal set\"")
    print("=" * 78)
    return 0


def sync_rehearsal_repo(target_dir_str: Optional[str], message: str) -> int:
    """Commit and push rehearsal player repository to GitHub."""
    target_root = Path(target_dir_str).expanduser().resolve() if target_dir_str else get_default_player_dir()
    if not (target_root / ".git").is_dir():
        print(f"[!] Error: Target directory is not a git repository: {target_root}")
        return 1

    print("=" * 78)
    print(f"  TrackDeck Sync: Rehearsal Player Repository Deployment")
    print(f"  Target Repository: {target_root}")
    print(f"  Commit Message:    \"{message}\"")
    print("=" * 78)

    # Check working tree status
    try:
        status_res = subprocess.run(
            ["git", "-C", str(target_root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True
        )
    except Exception as e:
        print(f"[!] Git status check failed: {e}")
        return 1

    if status_res.stdout.strip():
        print(f"[*] Staging all changes in {target_root.name}/...")
        subprocess.run(["git", "-C", str(target_root), "add", "-A"], check=True)

        print(f"[*] Committing changes...")
        subprocess.run(["git", "-C", str(target_root), "commit", "-m", message], check=True)
    else:
        print(f"[*] Working tree is clean in {target_root.name}/.")

    # Check if there are any unpushed commits
    unpushed_res = subprocess.run(
        ["git", "-C", str(target_root), "cherry", "-v"],
        capture_output=True,
        text=True
    )
    if not unpushed_res.stdout.strip():
        print(f"[+] {target_root.name}/ is already up to date with remote.")
        return 0

    print(f"[*] Pushing to GitHub remote repository...")
    push_res = subprocess.run(
        ["git", "-C", str(target_root), "push"],
        capture_output=True,
        text=True
    )
    if push_res.returncode != 0:
        print(f"[!] Git push failed:\n{push_res.stderr}")
        return 1

    print(f"[+] Successfully synced and pushed {target_root.name}/ to GitHub!")
    return 0

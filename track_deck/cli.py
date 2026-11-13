"""TrackDeck Command Line Interface."""

import argparse
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from track_deck.dialog import interactive_mapping_dialog
from track_deck.exporter import export_jobs_command
from track_deck.injector import inject_job_into_stemdeck, notify_stemdeck_rescan
from track_deck.parsers import get_session_parser
from track_deck.parsers.base import BaseSessionParser, MarkerInfo
from track_deck.profiles import delete_profile, list_profiles, load_profile
from track_deck.stemdeck_patcher import find_stemdeck_dir, patch_stemdeck, is_stemdeck_patched
from track_deck.summer import sum_and_render_stems


def parse_time_str(time_val: str) -> float:
    """Parse time string (HH:MM:SS, MM:SS, or seconds) into float seconds."""
    s = str(time_val).strip()
    if not s:
        return 0.0

    parts = s.split(":")
    if len(parts) == 3:
        # HH:MM:SS
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        # MM:SS
        return float(parts[0]) * 60 + float(parts[1])
    else:
        return float(s)


def markers_action(session_path_str: str) -> int:
    """List all detected song markers in session."""
    try:
        parser = get_session_parser(session_path_str)
    except Exception as e:
        print(f"[!] Error loading session: {e}")
        return 1

    markers = parser.get_markers()
    sr = parser.get_sample_rate()
    total_sec = parser.get_total_duration_sec()

    print("\n" + "=" * 78)
    print(f"  Detected Songs / Markers in: {Path(session_path_str).name}")
    print("=" * 78)
    print(f"Sample Rate: {sr:,} Hz | Session Duration: {int(total_sec // 60)}m {int(total_sec % 60)}s ({total_sec:.1f}s)")
    print("-" * 78)

    if not markers:
        print("[!] Notice: No markers found in this session.")
        print("    Tip: In Adobe Audition, select a song on the timeline and press 'M' to add a Range Marker.")
        print("    Or run with manual timestamps: trackdeck session <file> --start 03:15 --end 07:45 --title \"Song\"")
        print("=" * 78)
        return 0

    print(f"{'#':<4} | {'Song / Marker Title':<28} | {'Start Time':<10} | {'Duration':<10} | {'Type'}")
    print("-" * 78)
    for idx, m in enumerate(markers, start=1):
        print(f"{idx:<4} | {m.name:<28} | {m.formatted_start():<10} | {m.formatted_duration():<10} | {m.marker_type}")

    print("=" * 78)
    print("\nUsage Tips:")
    print("  * Ingest a single song:  trackdeck session <file> --marker \"May Galak\"")
    print("  * Batch-ingest all:      trackdeck session <file> --all-markers")
    return 0


def profiles_action(args) -> int:
    """Manage channel routing profiles."""
    if getattr(args, "show", None):
        mapping = load_profile(args.show)
        if not mapping:
            print(f"[!] Profile not found: {args.show}")
            return 1
        print(f"\n=== Channel Routing Profile: {args.show} ===")
        for trk, stem in mapping.items():
            print(f"  * {trk:<24} -> {stem}")
        return 0

    if getattr(args, "delete", None):
        ok = delete_profile(args.delete)
        if ok:
            print(f"[+] Deleted profile: {args.delete}")
            return 0
        else:
            print(f"[!] Profile not found: {args.delete}")
            return 1

    # Default: list profiles
    profs = list_profiles()
    print("\n=== Available TrackDeck Routing Profiles ===")
    if not profs:
        print("  (No profiles saved yet. Run 'trackdeck session' to create one.)")
    else:
        for p in profs:
            print(f"  * {p['name']:<18} ({p['mappings_count']} tracks) - {p['description']}")
    print("\nTip: To load a profile during ingestion, pass: --profile <name>")
    return 0


def process_song_range(
    parser: BaseSessionParser,
    mapping: Dict[str, str],
    title: str,
    start_sample: int,
    end_sample: int,
) -> bool:
    """Sum and inject a single song range into StemDeck."""
    with tempfile.TemporaryDirectory(prefix=f"trackdeck_{title[:10]}_") as tmpdir:
        tmp_out = Path(tmpdir)
        try:
            stems_map = sum_and_render_stems(
                parser=parser,
                mapping=mapping,
                start_sample=start_sample,
                end_sample=end_sample,
                output_dir=tmp_out
            )
            job_dir = inject_job_into_stemdeck(title=title, stems_map=stems_map)
            return job_dir.is_dir()
        except Exception as e:
            print(f"[!] Ingestion failed for '{title}': {e}")
            import traceback
            traceback.print_exc()
            return False


def session_command(args) -> int:
    """Ingest multitrack session (Adobe Audition, full service recording)."""
    session_path = Path(args.session_path).expanduser()
    try:
        parser = get_session_parser(session_path)
    except Exception as e:
        print(f"[!] Error loading session: {e}")
        return 1

    # 1. Resolve Channel Routing
    tracks = parser.get_tracks()
    if not tracks:
        print(f"[!] No audio tracks found in session: {session_path}")
        return 1

    track_names = [t.name for t in tracks]
    preset_mapping: Optional[Dict[str, str]] = None

    if getattr(args, "profile", None):
        preset_mapping = load_profile(args.profile)
        if not preset_mapping:
            print(f"[!] Error: Could not find requested profile '{args.profile}'.")
            print("    Run 'trackdeck profiles' to see all saved profiles.")
            return 1
        print(f"[*] Loaded channel routing profile: {args.profile}")

    mapping, _ = interactive_mapping_dialog(
        track_names=track_names,
        preset_mapping=preset_mapping,
        non_interactive=bool(getattr(args, "yes", False))
    )

    # 2. Determine Song Boundaries
    sr = parser.get_sample_rate()
    markers = parser.get_markers()

    # Mode A: Batch Ingest All Markers
    if getattr(args, "all_markers", False):
        if not markers:
            print("[!] Cannot use --all-markers: No markers found in session.")
            return 1

        print(f"\n[*] Batch ingesting {len(markers)} songs from session markers...")
        successes = 0
        for m in markers:
            print(f"\n---> Ingesting Song: {m.name} ({m.formatted_start()} to {m.formatted_duration()})")
            ok = process_song_range(
                parser=parser,
                mapping=mapping,
                title=m.name,
                start_sample=m.start_sample,
                end_sample=m.end_sample
            )
            if ok:
                successes += 1
        print(f"\n[+] Batch ingestion completed: {successes}/{len(markers)} songs injected into StemDeck.")
        return 0 if successes > 0 else 1

    # Mode B: Specific Marker
    marker_query = getattr(args, "marker", None)
    if marker_query:
        matching = [m for m in markers if marker_query.lower() in m.name.lower()]
        if not matching:
            print(f"[!] Marker matching '{marker_query}' not found.")
            markers_action(str(session_path))
            return 1
        target_marker = matching[0]
        title = getattr(args, "title", None) or target_marker.name
        print(f"[*] Found marker: '{target_marker.name}' ({target_marker.formatted_start()} -> {target_marker.formatted_duration()})")
        ok = process_song_range(
            parser=parser,
            mapping=mapping,
            title=title,
            start_sample=target_marker.start_sample,
            end_sample=target_marker.end_sample
        )
        return 0 if ok else 1

    # Mode C: Manual Timestamp Range (--start, --end)
    if getattr(args, "start", None) is not None and getattr(args, "end", None) is not None:
        start_sec = parse_time_str(args.start)
        end_sec = parse_time_str(args.end)
        start_samp = int(start_sec * sr)
        end_samp = int(end_sec * sr)
        title = getattr(args, "title", None) or f"{session_path.stem} ({args.start}-{args.end})"
        ok = process_song_range(
            parser=parser,
            mapping=mapping,
            title=title,
            start_sample=start_samp,
            end_sample=end_samp
        )
        return 0 if ok else 1

    # Mode D: Single marker if exactly one exists, or prompt user
    if len(markers) == 1:
        m = markers[0]
        title = getattr(args, "title", None) or m.name
        print(f"[*] Ingesting single detected marker: {m.name}")
        ok = process_song_range(
            parser=parser,
            mapping=mapping,
            title=title,
            start_sample=m.start_sample,
            end_sample=m.end_sample
        )
        return 0 if ok else 1
    elif len(markers) > 1:
        print("[!] Multiple markers detected in session. Please specify:")
        print("    --marker \"Song Name\"   (to ingest a specific song)")
        print("    --all-markers          (to ingest all songs in batch)")
        markers_action(str(session_path))
        return 1

    # Mode E: Full timeline fallback
    title = getattr(args, "title", None) or session_path.stem
    total_samp = int(parser.get_total_duration_sec() * sr)
    print(f"[*] Ingesting full session timeline as single song: {title}")
    ok = process_song_range(
        parser=parser,
        mapping=mapping,
        title=title,
        start_sample=0,
        end_sample=total_samp
    )
    return 0 if ok else 1


def single_command(args) -> int:
    """Ingest a single multitrack song (folder of WAVs or standalone song session)."""
    target_path = Path(args.path).expanduser()
    try:
        parser = get_session_parser(target_path)
    except Exception as e:
        print(f"[!] Error loading multitrack path: {e}")
        return 1

    tracks = parser.get_tracks()
    if not tracks:
        print(f"[!] No audio tracks found in: {target_path}")
        return 1

    track_names = [t.name for t in tracks]
    preset_mapping: Optional[Dict[str, str]] = None

    if getattr(args, "profile", None):
        preset_mapping = load_profile(args.profile)
        if not preset_mapping:
            print(f"[!] Error: Could not find requested profile '{args.profile}'.")
            return 1
        print(f"[*] Loaded channel routing profile: {args.profile}")

    mapping, _ = interactive_mapping_dialog(
        track_names=track_names,
        preset_mapping=preset_mapping,
        non_interactive=bool(getattr(args, "yes", False))
    )

    sr = parser.get_sample_rate()
    total_samp = int(parser.get_total_duration_sec() * sr)
    title = getattr(args, "title", None) or target_path.stem

    ok = process_song_range(
        parser=parser,
        mapping=mapping,
        title=title,
        start_sample=0,
        end_sample=total_samp
    )
    return 0 if ok else 1


def patch_stemdeck_action(custom_dir: Optional[str]) -> int:
    """Patch StemDeck backend with /api/jobs/rescan route."""
    sd_dir = find_stemdeck_dir(custom_dir)
    if not sd_dir:
        print("[!] Could not locate StemDeck installation directory.")
        print("    Please provide --stemdeck-dir PATH (e.g. ~/Applications/StemDeck or /opt/stemdeck).")
        return 1

    print(f"[*] Found StemDeck directory at: {sd_dir}")
    patched, status_msg = is_stemdeck_patched(sd_dir)
    if patched:
        print(f"[+] {status_msg}")
        return 0

    ok, msg = patch_stemdeck(sd_dir)
    if ok:
        print(f"[+] {msg}")
        print("    Note: Please restart StemDeck once to activate the new live rescan endpoint.")
        return 0
    else:
        print(f"[!] {msg}")
        return 1


def rescan_action(port: int = 10000) -> int:
    """Trigger StemDeck live library rescan via API."""
    print(f"[*] Requesting StemDeck live rescan at http://127.0.0.1:{port}/api/jobs/rescan...")
    ok = notify_stemdeck_rescan(port=port)
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(
        prog="trackdeck",
        description="Multitrack Session Ingestion & Lossless Stem Bus Middleware for StemDeck",
        epilog="Tip: 'trackdeck session <file>' ingests full-session recordings; 'trackdeck single <file>' ingests single songs."
    )
    parser.add_argument("-v", "--version", action="version", version="TrackDeck 0.1.0")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: session
    sess_parser = subparsers.add_parser("session", help="Ingest a full-session multitrack recording (with markers / multiple songs)")
    sess_parser.add_argument("session_path", type=str, help="Path to Adobe Audition .sesx file or session directory")
    sess_parser.add_argument("--marker", type=str, default=None, help="Ingest a specific song by marker name")
    sess_parser.add_argument("--all-markers", action="store_true", help="Batch-ingest all range markers into individual StemDeck songs")
    sess_parser.add_argument("--start", type=str, default=None, help="Start time for custom time range (HH:MM:SS or seconds)")
    sess_parser.add_argument("--end", type=str, default=None, help="End time for custom time range (HH:MM:SS or seconds)")
    sess_parser.add_argument("--title", type=str, default=None, help="Song title override")
    sess_parser.add_argument("-p", "--profile", type=str, default=None, help="Explicitly load channel routing profile (never loaded by default)")
    sess_parser.add_argument("-y", "--yes", action="store_true", help="Non-interactive mode (accept suggested channel mapping)")

    # Command: single
    single_parser = subparsers.add_parser("single", help="Ingest a single multitrack song (entire timeline or folder of WAVs)")
    single_parser.add_argument("path", type=str, help="Path to session file or folder containing multitrack WAVs")
    single_parser.add_argument("--title", type=str, default=None, help="Song title override (default: folder or session name)")
    single_parser.add_argument("-p", "--profile", type=str, default=None, help="Explicitly load channel routing profile (never loaded by default)")
    single_parser.add_argument("-y", "--yes", action="store_true", help="Non-interactive mode (accept suggested channel mapping)")

    # Command: markers
    markers_parser = subparsers.add_parser("markers", help="List detected song markers in a multitrack session")
    markers_parser.add_argument("session_path", type=str, help="Path to Adobe Audition .sesx file")

    # Command: profiles
    prof_parser = subparsers.add_parser("profiles", help="List or manage saved channel routing profiles")
    prof_parser.add_argument("--list", action="store_true", help="List all saved profiles")
    prof_parser.add_argument("--show", type=str, metavar="NAME", help="Show channel mapping for a saved profile")
    prof_parser.add_argument("--delete", type=str, metavar="NAME", help="Delete a saved profile")

    # Command: completion
    comp_parser = subparsers.add_parser("completion", help="Generate or install Fish shell completions")
    comp_parser.add_argument("shell", nargs="?", default="fish", choices=["fish"], help="Target shell (default: fish)")
    comp_parser.add_argument("--install", action="store_true", help="Install completions into ~/.config/fish/completions/")

    # Command: patch-stemdeck
    patch_parser = subparsers.add_parser("patch-stemdeck", help="Patch StemDeck backend with /api/jobs/rescan for zero-restart live ingestion")
    patch_parser.add_argument("--stemdeck-dir", type=str, default=None, help="Path to StemDeck app directory (default: auto-detect)")

    # Command: rescan
    rescan_parser = subparsers.add_parser("rescan", help="Trigger StemDeck live library rescan via API")
    rescan_parser.add_argument("--port", type=int, default=10000, help="StemDeck backend port (default: 10000)")

    # Command: export
    export_parser = subparsers.add_parser("export", help="Add StemDeck jobs into static rehearsal player repository (incremental)")
    export_parser.add_argument("jobs", nargs="+", type=str, help="One or more StemDeck job IDs (or 'latest') to export")
    export_parser.add_argument("-d", "--dir", dest="target_dir", type=str, default=None, help="Target player repository directory (default: ~/Projects/4StemPlayer)")

    # Command: publish
    publish_parser = subparsers.add_parser("publish", help="Publish a fresh weekly set into static rehearsal player (cleans prior songs)")
    publish_parser.add_argument("jobs", nargs="+", type=str, help="One or more StemDeck job IDs (or 'latest') to publish")
    publish_parser.add_argument("-d", "--dir", dest="target_dir", type=str, default=None, help="Target player repository directory (default: ~/Projects/4StemPlayer)")

    # Command: sync
    sync_parser = subparsers.add_parser("sync", help="Commit and push rehearsal player repository to GitHub")
    sync_parser.add_argument("message", type=str, help="Git commit message")
    sync_parser.add_argument("-d", "--dir", dest="target_dir", type=str, default=None, help="Target player repository directory (default: ~/Projects/4StemPlayer)")

    if len(sys.argv) == 1:
        parser.print_help()
        return 0

    args = parser.parse_args()

    if args.command == "markers":
        return markers_action(args.session_path)

    if args.command == "profiles":
        return profiles_action(args)

    if args.command == "patch-stemdeck":
        return patch_stemdeck_action(getattr(args, "stemdeck_dir", None))

    if args.command == "rescan":
        return rescan_action(getattr(args, "port", 10000))

    if args.command in ("export", "publish"):
        raw_jobs = args.jobs
        target_dir = getattr(args, "target_dir", None)
        if not target_dir and len(raw_jobs) > 1 and Path(raw_jobs[0]).expanduser().is_dir():
            target_dir = raw_jobs[0]
            job_ids = raw_jobs[1:]
        else:
            job_ids = raw_jobs
        clean = (args.command == "publish")
        return export_jobs_command(target_dir, job_ids, clean=clean)

    if args.command == "sync":
        from track_deck.exporter import sync_rehearsal_repo
        return sync_rehearsal_repo(getattr(args, "target_dir", None), args.message)

    if args.command == "completion":
        from track_deck.completions import generate_fish_completions, install_fish_completions
        if getattr(args, "install", False):
            ok, msg = install_fish_completions()
            print(msg)
            return 0 if ok else 1
        print(generate_fish_completions())
        return 0

    if args.command == "session":
        return session_command(args)

    if args.command == "single":
        return single_command(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

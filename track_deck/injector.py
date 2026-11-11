"""StemDeck Job Injector & Registry Updater."""

import json
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from track_deck.analyzer import generate_stemdeck_artifacts


def notify_stemdeck_rescan(port: int = 10000) -> bool:
    """Notify running StemDeck backend to dynamically rescan its library."""
    url = f"http://127.0.0.1:{port}/api/jobs/rescan"
    req = urllib.request.Request(
        url,
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                count = body.get("count", 0)
                print(f"[+] Notified StemDeck: Live library rescan successful ({count} songs available).")
                return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("[!] Notice: StemDeck backend is running, but /api/jobs/rescan endpoint was not found.")
            print("    Run 'trackdeck patch-stemdeck' and restart StemDeck to enable zero-restart live reload.")
        else:
            print(f"[!] StemDeck backend returned HTTP {e.code} during rescan.")
    except Exception:
        print("[*] Note: StemDeck backend is not currently running.")
        print("    Song injected to disk; it will appear automatically next time StemDeck opens.")
    return False


def get_default_stemdeck_jobs_dir() -> Path:
    """Resolve StemDeck jobs directory (~/Documents/StemDeck/jobs)."""
    p = Path.home() / "Documents" / "StemDeck" / "jobs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def inject_job_into_stemdeck(
    title: str,
    stems_map: Dict[str, Path],
    job_id: Optional[str] = None
) -> Path:
    """Inject a pre-separated, lossless multitrack song directly into StemDeck.
    
    Returns the path to the created job directory.
    """
    jobs_dir = get_default_stemdeck_jobs_dir()
    jid = job_id or uuid.uuid4().hex[:12]
    job_dir = jobs_dir / jid
    stems_dir = job_dir / "stems"
    stems_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Injecting job '{title}' ({jid}) into StemDeck...")

    # 1. Move or link generated stem WAVs into target job folder
    for stem_name in ["drums", "bass", "guitar", "piano", "vocals", "other", "mix"]:
        src = stems_map.get(stem_name)
        if src and src.is_file():
            dest = stems_dir / f"{stem_name}.wav"
            if src.resolve() != dest.resolve():
                import shutil
                shutil.copy2(src, dest)

    source_src = stems_map.get("source") or stems_map.get("mix")
    if source_src and source_src.is_file():
        dest_source = job_dir / "source.wav"
        if source_src.resolve() != dest_source.resolve():
            import shutil
            shutil.copy2(source_src, dest_source)

    # 2. Synthesize visual peaks, beatgrid, and metadata
    metadata = generate_stemdeck_artifacts(stems_dir, title=title)

    # 3. Register Job in StemDeck's registry.json
    print("    [3/3] Registering job in StemDeck library catalog...")
    registry_file = jobs_dir / "registry.json"
    registry_data: Dict[str, Any] = {"version": 1, "jobs": []}

    if registry_file.is_file():
        try:
            registry_data = json.loads(registry_file.read_text(encoding="utf-8"))
        except Exception:
            registry_data = {"version": 1, "jobs": []}

    job_entry = {
        "status": "done",
        "stage_message": "Done",
        "id": jid,
        "auto_sections": True,
        "duration_sec": metadata["duration_sec"],
        "scale": metadata["scale"],
        "mix_url": f"/api/jobs/{jid}/stems/mix.wav",
        "has_lyrics": False,
        "video_status": "ok",
        "vocal_split": "none",
        "trashed_at": None,
        "peak_db": metadata["peak_db"],
        "compute_device": "cpu",
        "title": title,
        "progress": 1.0,
        "created_at": time.time(),
        "stage_timings": metadata["stage_timings"],
        "key": metadata["key"],
        "stems": [
            {"name": s, "url": f"/api/jobs/{jid}/stems/{s}.wav"}
            for s in ["vocals", "drums", "bass", "guitar", "piano", "other"]
        ]
    }

    # Prepend or replace existing entry
    existing_jobs = [j for j in registry_data.get("jobs", []) if j.get("id") != jid]
    existing_jobs.insert(0, job_entry)
    registry_data["jobs"] = existing_jobs

    tmp_reg = jobs_dir / "registry.json.tmp"
    tmp_reg.write_text(json.dumps(registry_data, indent=2), encoding="utf-8")
    tmp_reg.replace(registry_file)

    print(f"[+] Successfully injected job into StemDeck: {job_dir.name}")
    print(f"    Title: {title} | Key: {metadata['key']} | BPM: {metadata['bpm']} | Duration: {metadata['duration_sec']}s")

    # Notify running StemDeck backend to rescan immediately
    notify_stemdeck_rescan()

    return job_dir

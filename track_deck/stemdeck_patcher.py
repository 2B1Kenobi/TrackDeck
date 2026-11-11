"""StemDeck Backend Patcher for Live Ingestion Rescan."""

import py_compile
import shutil
from pathlib import Path
from typing import Optional, Tuple

SEARCH_DIRS = [
    Path.home() / "Applications" / "StemDeck",
    Path("/opt/stemdeck"),
    Path.home() / ".local" / "opt" / "stemdeck",
    Path.home() / "StemDeck",
]

RESCAN_SNIPPET = '''
@router.api_route("/rescan", methods=["GET", "POST"])
def rescan_jobs() -> dict:
    """Reload persisted jobs and scan for orphan completed jobs on disk."""
    registry_restore(JOBS_DIR)
    jobs = [j for j in registry_all_jobs().values() if j.status == "done" and j.trashed_at is None]
    return {"ok": True, "count": len(jobs)}
'''


def find_stemdeck_dir(custom_path: Optional[str] = None) -> Optional[Path]:
    """Locate the StemDeck installation directory."""
    if custom_path:
        p = Path(custom_path).expanduser().resolve()
        if (p / "backend" / "app" / "api" / "jobs.py").is_file():
            return p
        return None

    for candidate in SEARCH_DIRS:
        if (candidate / "backend" / "app" / "api" / "jobs.py").is_file():
            return candidate
    return None


def get_target_jobs_files(stemdeck_dir: Path) -> list[Path]:
    """Find all app/api/jobs.py files in StemDeck installation (backend and site-packages)."""
    targets: list[Path] = []
    backend_jobs = stemdeck_dir / "backend" / "app" / "api" / "jobs.py"
    if backend_jobs.is_file():
        targets.append(backend_jobs)

    for p in stemdeck_dir.glob("python/lib/python*/site-packages/app/api/jobs.py"):
        if p.is_file() and p not in targets:
            targets.append(p)

    return targets


def is_stemdeck_patched(stemdeck_dir: Path) -> Tuple[bool, str]:
    """Check if the StemDeck installation already has the rescan endpoint."""
    targets = get_target_jobs_files(stemdeck_dir)
    if not targets:
        return False, f"Could not find jobs.py under {stemdeck_dir}"

    all_patched = True
    for t in targets:
        content = t.read_text(encoding="utf-8")
        if not ('def rescan_jobs()' in content or '"/rescan"' in content):
            all_patched = False
            break

    if all_patched:
        return True, "StemDeck backend is already patched with /api/jobs/rescan."
    return False, "Rescan endpoint is not yet present in all StemDeck runtime files."


def _patch_single_file(jobs_py: Path) -> Tuple[bool, str]:
    content = jobs_py.read_text(encoding="utf-8")
    if 'def rescan_jobs()' in content or '"/rescan"' in content:
        return True, f"{jobs_py.name} already patched."

    # Backup original
    backup_file = jobs_py.with_suffix(".py.bak")
    if not backup_file.exists():
        shutil.copy2(jobs_py, backup_file)

    # 1. Ensure registry_restore is imported
    if "registry_restore" not in content:
        target_import = "from app.core.registry import requeue_if_capacity as registry_requeue_if_capacity"
        if target_import in content:
            content = content.replace(
                target_import,
                target_import + "\nfrom app.core.registry import restore as registry_restore"
            )
        else:
            return False, f"Could not find registry import insertion point in {jobs_py}"

    # 2. Add /rescan route after list_jobs
    marker = "@router.post(\"/{job_id}/trash\")"
    if marker in content:
        content = content.replace(
            marker,
            RESCAN_SNIPPET.strip() + "\n\n\n" + marker
        )
    else:
        return False, f"Could not find route insertion point in {jobs_py}"

    # Write temporarily to test compilation
    tmp_file = jobs_py.with_suffix(".py.tmp")
    tmp_file.write_text(content, encoding="utf-8")

    try:
        py_compile.compile(str(tmp_file), doraise=True)
    except Exception as e:
        tmp_file.unlink(missing_ok=True)
        return False, f"Syntax verification failed on {jobs_py}: {e}"

    tmp_file.replace(jobs_py)
    return True, f"Patched {jobs_py} (backup: {backup_file.name})"


def patch_stemdeck(stemdeck_dir: Path) -> Tuple[bool, str]:
    """Apply the /api/jobs/rescan route to all StemDeck backend targets."""
    targets = get_target_jobs_files(stemdeck_dir)
    if not targets:
        return False, f"Error: Cannot find any jobs.py files under {stemdeck_dir}"

    patched_msgs = []
    for t in targets:
        ok, msg = _patch_single_file(t)
        if not ok:
            return False, msg
        patched_msgs.append(msg)

    return True, f"Successfully patched StemDeck ({', '.join(patched_msgs)})."

"""Routing Profiles Manager for TrackDeck."""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def get_profiles_dir() -> Path:
    """Return path to user profile directory (~/.config/trackdeck/profiles)."""
    p = Path.home() / ".config" / "trackdeck" / "profiles"
    p.mkdir(parents=True, exist_ok=True)
    return p


def list_profiles() -> List[Dict[str, str]]:
    """List all available routing profiles."""
    p_dir = get_profiles_dir()
    profiles = []
    for f in sorted(p_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            desc = data.get("description", "User defined channel routing profile")
            profiles.append({
                "name": f.stem,
                "path": str(f),
                "description": desc,
                "mappings_count": len(data.get("mapping", {}))
            })
        except Exception:
            continue
    return profiles


def load_profile(name_or_path: str) -> Optional[Dict[str, str]]:
    """Load a profile by name or explicit file path.
    
    NOTE: Profiles are NEVER loaded by default. They must be explicitly
    requested via the --profile switch.
    """
    path = Path(name_or_path).expanduser()
    if not path.is_file():
        # Check ~/.config/trackdeck/profiles/<name>.json
        cand = get_profiles_dir() / f"{name_or_path}.json"
        if cand.is_file():
            path = cand
        else:
            return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("mapping", data)
    except Exception:
        return None


def save_profile(name: str, mapping: Dict[str, str], description: str = "") -> Tuple[bool, Path]:
    """Save a routing profile to ~/.config/trackdeck/profiles/<name>.json."""
    clean_name = "".join(c for c in name if c.isalnum() or c in ("-", "_")).strip()
    if not clean_name:
        clean_name = "default_routing"
    target = get_profiles_dir() / f"{clean_name}.json"
    payload = {
        "name": clean_name,
        "description": description or f"TrackDeck mapping profile for {clean_name}",
        "mapping": mapping
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return True, target


def delete_profile(name: str) -> bool:
    """Delete a profile by name."""
    cand = get_profiles_dir() / f"{name}.json"
    if cand.is_file():
        cand.unlink()
        return True
    return False

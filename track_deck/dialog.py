"""Interactive Ingestion Dialog & Track-to-Stem Classifier."""

import re
import sys
from typing import Dict, List, Optional, Tuple

STEM_TARGETS = ["drums", "bass", "guitar", "piano", "vocals", "other", "ignore"]


def classify_track_heuristic(track_name: str) -> str:
    """Classify track name to a StemDeck target stem using standard audio mixing terminology.
    
    Standard Industry Conventions:
    - VOCALS: VOX, VOCAL, MIC, LEAD, BGV, BACKING, HARMONY, CHOIR
    - DRUMS: DRUM, KICK, SNARE, TOM, HAT, CYMBAL, OVERHEAD (OH), PERC
    - BASS: BASS, BS
    - GUITAR: GUITAR, GTR, ACOUSTIC, ELECTRIC (EG)
    - PIANO: KEY, KEYS, PIANO, SYNTH, ORGAN, RHODES, KEYBOARD, PAD
    - OTHER: ROOM, AMBIENT, AUDIENCE, TALK, SPEECH, CLICK, GUIDE, AUX, FX
    
    Setup-specific names (e.g. brand names, custom hardware labels) fall back
    to 'other' unless explicitly specified via a routing profile (--profile).
    """
    tn = track_name.lower().strip()

    # Common non-musical or utility channels
    if re.search(r"\b(talk|speech|speaker|room|amb|ambient|audience|crowd|click|guide|aux|fx)\b", tn):
        return "other"

    # Drums & Percussion
    if re.search(r"\b(drum|drums|kick|bd|snare|sn|tom|toms|hat|hihat|hi-hat|cym|cymbal|cymbals|overhead|oh|perc|percussion)\b", tn):
        return "drums"

    # Bass
    if re.search(r"\b(bass|bs)\b", tn):
        return "bass"

    # Guitar (Acoustic / Electric)
    if re.search(r"\b(guitar|guitars|gtr|acoustic|ac|electric|eg)\b", tn):
        return "guitar"

    # Piano / Keys / Synths / Organs
    if re.search(r"\b(key|keys|key1|key2|piano|synth|organ|rhodes|keyboard|keyboards|pad)\b", tn):
        return "piano"

    # Vocals (Mic, Vox, Vocal, Lead, Backing)
    if re.search(r"\b(vox|vocal|vocals|mic\s*\d*|lead|backing|bgv|harmony|singer|choir)\b", tn):
        return "vocals"

    # Default fallback for arbitrary or unclassified track names
    return "other"


def interactive_mapping_dialog(
    track_names: List[str],
    preset_mapping: Optional[Dict[str, str]] = None,
    non_interactive: bool = False
) -> Tuple[Dict[str, str], Optional[str]]:
    """Run an interactive track-to-stem assignment dialog.
    
    Returns (mapping, saved_profile_name_or_none).
    """
    # 1. Initialize mapping using preset or heuristic defaults
    current_mapping: Dict[str, str] = {}
    for name in track_names:
        if preset_mapping and name in preset_mapping:
            current_mapping[name] = preset_mapping[name]
        else:
            current_mapping[name] = classify_track_heuristic(name)

    if non_interactive or not sys.stdin.isatty():
        return current_mapping, None

    print("\n" + "=" * 76)
    print("  TrackDeck Multitrack Ingestion: Channel Routing Setup")
    print("=" * 76)
    print("Detected tracks from your session and suggested StemDeck stem targets:")
    print("-" * 76)

    saved_profile_name: Optional[str] = None

    while True:
        print(f"{'#':<4} | {'Track Name':<28} | {'Assigned Stem':<12} | {'Action'}")
        print("-" * 76)
        for idx, name in enumerate(track_names, start=1):
            stem = current_mapping.get(name, "other")
            print(f"{idx:<4} | {name:<28} | {stem:<12} | [Enter number to change]")

        print("-" * 76)
        print("Valid stems: drums, bass, guitar, piano, vocals, other, ignore")
        print("\nCommands:")
        print("  <number>  : Change stem assignment for a specific track")
        print("  p         : Save current routing to a reusable profile")
        print("  c (or ↵)  : Confirm mapping and proceed with audio bus summing")
        print("  q         : Cancel ingestion and exit")

        try:
            choice = input("\nSelect an option [c]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(1)

        if choice in ("", "c", "continue", "proceed"):
            # Check if user wants to save as profile if not already saved
            if not saved_profile_name and not preset_mapping:
                try:
                    save_q = input("\nSave this channel routing as a named profile for future use? (y/N): ").strip().lower()
                    if save_q in ("y", "yes"):
                        prof_name = input("Profile name (e.g. xr18_sunday): ").strip()
                        if prof_name:
                            from track_deck.profiles import save_profile
                            ok, ppath = save_profile(prof_name, current_mapping, description=f"Channel profile for {prof_name}")
                            if ok:
                                print(f"[+] Saved profile to {ppath.name}. In future sessions, use: --profile {prof_name}")
                                saved_profile_name = prof_name
                except (EOFError, KeyboardInterrupt):
                    pass
            break

        elif choice == "q":
            print("Ingestion cancelled.")
            sys.exit(0)

        elif choice == "p":
            prof_name = input("Enter profile name to save (e.g. xr18_sunday): ").strip()
            if prof_name:
                from track_deck.profiles import save_profile
                ok, ppath = save_profile(prof_name, current_mapping, description=f"Channel profile for {prof_name}")
                if ok:
                    print(f"[+] Saved profile to {ppath}. In future sessions, use: --profile {prof_name}")
                    saved_profile_name = prof_name
            continue

        elif choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(track_names):
                target_track = track_names[idx - 1]
                print(f"\nSelect target stem for '{target_track}':")
                for s_idx, stem in enumerate(STEM_TARGETS, start=1):
                    print(f"  [{s_idx}] {stem}")
                try:
                    s_choice = input(f"Enter stem (1-7 or name) [{current_mapping[target_track]}]: ").strip().lower()
                    if s_choice.isdigit():
                        s_num = int(s_choice)
                        if 1 <= s_num <= len(STEM_TARGETS):
                            current_mapping[target_track] = STEM_TARGETS[s_num - 1]
                    elif s_choice in STEM_TARGETS:
                        current_mapping[target_track] = s_choice
                except (EOFError, KeyboardInterrupt):
                    pass
            else:
                print(f"[!] Invalid track index: {choice}")
        else:
            print("[!] Unrecognized command.")

    return current_mapping, saved_profile_name

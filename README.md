# TrackDeck

> **Multitrack Session Ingestion & Lossless Stem Bus Middleware for StemDeck**

TrackDeck bridges discrete multitrack live recordings (e.g. Behringer XR-18, SoundCraft, Altered Audio Editor, Adobe Audition) directly into **StemDeck** without running AI separation.

By summing discrete microphone and DI lines directly into StemDeck's 6 canonical stem targets (`drums`, `bass`, `guitar`, `piano`, `vocals`, `other`), TrackDeck:
1. **Eliminates AI Artifacts**: No cymbal flanging, phase smearing, or spectral vocal bleed caused by neural separation models.
2. **Instant Ingestion**: Sums and injects an entire 5-minute song in under 3 seconds instead of 2–3 minutes of Demucs processing.
3. **Preserves 100% Studio Fidelity**: 32-bit float internal summing with automatic peak headroom protection.

---

## Supported Session Formats & DAWs

- **Altered Audio Editor (`.altaudio`)**: Native JSON multitrack session format with first-class cue & range markers, clip volume gain envelopes, and track routing.
- **Adobe Audition (`.sesx`)**: XML multitrack sessions with XMP timeline markers.
- **Raw Multitrack Folders**: Directories containing discrete, numbered/named `.wav` files (e.g. direct USB multitrack capture from mixers).

---

## Full-Session Workflow with Markers

Live band sessions and Sunday services are typically recorded as continuous 30-to-90-minute multitrack sessions containing multiple songs. TrackDeck uses DAW **Range Markers** to slice songs automatically.

### 1. Placing Markers
- **In Altered Audio Editor**: Set cue/range markers on the timeline named with the song titles (e.g. `JIA Makati Welcome Song`, `Great is the Lord`).
- **In Adobe Audition**: Open Markers panel (`Alt + 8`), make a time selection over each song, press **`M`** to create Range Markers, and name them after the song titles.

### 2. Inspecting Detected Markers via CLI
```bash
trackdeck markers "2026-09-06 SUNDAY SERVICE.altaudio"
```
Output:
```text
==============================================================================
  Detected Songs / Markers in: 2026-09-06 SUNDAY SERVICE.altaudio
==============================================================================
Sample Rate: 48,000 Hz | Session Duration: 149m 31s (8971.3s)
------------------------------------------------------------------------------
#    | Song / Marker Title          | Start Time | Duration   | Type
------------------------------------------------------------------------------
1    | JIA Makati Welcome Song      | 00:05:45   | 02:45      | Range
2    | Great is the Lord            | 00:08:49   | 05:31      | Range
==============================================================================
```

### 3. Ingesting Songs into StemDeck

#### Ingest a Specific Song by Marker Name
```bash
trackdeck session "2026-09-06 SUNDAY SERVICE.altaudio" --marker "Great is the Lord"
```

#### Batch Ingest All Marked Songs in One Command
```bash
trackdeck session "2026-09-06 SUNDAY SERVICE.altaudio" --all-markers
```

#### Manual Timestamp Slicing (If Markers Were Not Added)
```bash
trackdeck session "2026-09-06 SUNDAY SERVICE.altaudio" --start 03:12 --end 07:45 --title "May Galak"
```

---

## Single Song Ingestion

For standalone multitrack song folders or single-song projects:

```bash
trackdeck single /path/to/multitrack_folder/ --title "May Galak"
```

---

## Channel Routing & Profiles

TrackDeck automatically classifies track names into StemDeck's 6 canonical stem targets using universal audio engineering standards (`VOX`/`MIC` -> `vocals`, `KICK`/`SNARE`/`OH` -> `drums`, `GTR` -> `guitar`, etc.).

### Standard Channel Classification Heuristics

When running without an explicit profile, TrackDeck automatically classifies tracks using standard mixing desk conventions:

| Target Stem | Recognized Industry Keywords & Abbreviations |
| :--- | :--- |
| **`vocals`** | `VOX`, `VOCAL`, `VOCALS`, `MIC`, `LEAD`, `BGV`, `BACKING`, `HARMONY`, `SINGER`, `CHOIR` |
| **`drums`** | `DRUM`, `DRUMS`, `KICK`, `BD`, `SNARE`, `SN`, `TOM`, `TOMS`, `HAT`, `HIHAT`, `CYMBAL`, `OVERHEAD`, `OH`, `PERC`, `PERCUSSION` |
| **`bass`** | `BASS`, `BS` |
| **`guitar`** | `GUITAR`, `GTR`, `ACOUSTIC`, `AC`, `ELECTRIC`, `EG` |
| **`piano`** | `KEY`, `KEYS`, `PIANO`, `SYNTH`, `ORGAN`, `RHODES`, `KEYBOARD`, `PAD` |
| **`other`** | `ROOM`, `AMBIENT`, `AUDIENCE`, `TALK`, `SPEECH`, `CLICK`, `GUIDE`, `AUX`, `FX` |

> **Setup-Specific Labels**: Custom hardware names, stagebox labels, or brand-specific mic channels (e.g., `SHURE`, `BEH1`, `WIRELESS_A`) are treated as arbitrary and fall back to `other` by default. They should be mapped during the interactive prompt or saved into a reusable profile (`--profile <name>`).

### Interactive Dialog
When running without a pre-loaded profile, TrackDeck displays:
```text
============================================================================
  TrackDeck Multitrack Ingestion: Channel Routing Setup
============================================================================
#    | Track Name                   | Assigned Stem | Action
----------------------------------------------------------------------------
1    | GUITAR                       | guitar        | [Enter number to change]
2    | KEY1                         | piano         | [Enter number to change]
3    | KEY2                         | piano         | [Enter number to change]
4    | BASS                         | bass          | [Enter number to change]
5    | DRUM LOW                     | drums         | [Enter number to change]
6    | DRUM HIGH                    | drums         | [Enter number to change]
7    | DRUM SNARE                   | drums         | [Enter number to change]
8    | MIC1                         | vocals        | [Enter number to change]
9    | ROOM                         | other         | [Enter number to change]
10   | AMBIENT                      | other         | [Enter number to change]
----------------------------------------------------------------------------
```
You can reassign any channel, proceed (`c`), or save the mapping as a reusable profile (`p`).

### Profile Rules & Switching
- **Profiles are NEVER loaded by default**.
- To load a profile, explicitly pass the `--profile` switch:
  ```bash
  trackdeck session "service.sesx" --profile xr18_sunday --all-markers
  ```

### Managing Profiles
```bash
trackdeck profiles --list
trackdeck profiles --show xr18_sunday
trackdeck profiles --delete xr18_sunday
```

---

## CLI Reference Summary

| Command | Description |
| :--- | :--- |
| `trackdeck session <file>` | Ingest full-session multitrack recording with marker slicing |
| `trackdeck single <path>` | Ingest a single multitrack song or folder of WAVs |
| `trackdeck markers <file>` | List detected song markers in session |
| `trackdeck profiles` | List and manage channel routing profiles |
| `trackdeck patch-stemdeck` | Patch StemDeck backend with `/api/jobs/rescan` for zero-restart live reload |
| `trackdeck rescan` | Manually trigger StemDeck live library rescan via API |
| `trackdeck completion` | Output Fish completion script (`--install` to install) |

---

## Installation & Release Integration

### 1. One-Command Quick Install
From the TrackDeck repository:
```bash
./install.sh
```
This script:
1. Links to StemDeck's bundled Python environment (or system Python 3.9+).
2. Verifies audio dependencies (`numpy`, `soundfile`, `scipy`).
3. Installs `trackdeck` and `track-deck` commands into `~/.local/bin/`.
4. Automatically installs Fish shell completions into `~/.config/fish/completions/`.
5. Checks and patches StemDeck with the live rescan endpoint.

### 2. StemDeck Live Rescan Integration
StemDeck's backend maintains its job library in an in-memory dictionary loaded at startup. Without a live reload hook, externally injected jobs require restarting StemDeck.

TrackDeck includes a non-destructive patcher:
```bash
trackdeck patch-stemdeck
```
- **What it does**: Adds a lightweight `@router.api_route("/rescan", methods=["GET", "POST"])` endpoint to StemDeck's `app/api/jobs.py` (with automatic `.bak` backups).
- **Zero-Restart Reactivity**: Whenever TrackDeck finishes injecting a song, it automatically calls `POST /api/jobs/rescan`. StemDeck's frontend picks up the new songs immediately as soon as the app window is focused!
- **Idempotent**: Safe to run repeatedly across StemDeck updates or reinstallations.

---

## Ecosystem: TrackDeck + StemDeck + ChordDeck

TrackDeck and ChordDeck together form a complete lossless workflow for live audio:

```text
[ Live Console Multitrack (XR-18, etc.) ]
                    │
                    ▼
          [ TrackDeck Middleware ]
       (Lossless stem summing & marker slicing)
                    │
                    ▼  (Zero AI artifacts; instant ingestion)
            [ StemDeck App ]
   (Playback, mixdown, timeline section editing)
                    │
                    ▼
          [ ChordDeck Middleware ]
     (Autonomous chord recognition & ChordPro/PDFs)
```


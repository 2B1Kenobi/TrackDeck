# TrackDeck

> **Multitrack Session Ingestion & Lossless Stem Bus Middleware for StemDeck**

TrackDeck bridges discrete multitrack live recordings (e.g. Behringer XR-18, SoundCraft, multi-channel USB stageboxes) directly into **StemDeck** without running AI separation.

By summing discrete microphone and DI lines directly into StemDeck's 6 canonical stem targets (`drums`, `bass`, `guitar`, `piano`, `vocals`, `other`), TrackDeck:
1. **Eliminates AI Artifacts**: No cymbal flanging, phase smearing, or spectral vocal bleed caused by neural separation models.
2. **Instant Ingestion**: Sums and injects an entire 5-minute song in under 3 seconds instead of 2–3 minutes of Demucs processing.
3. **Preserves 100% Studio Fidelity**: 32-bit float internal summing with automatic peak headroom protection.

---

## Installation & Setup

TrackDeck runs on Linux and is designed to execute with StemDeck's Python runtime or any Python 3.9+ environment.

```bash
cd /home/deck/Projects/TrackDeck
pip install -e .
```

### Install Shell Completions (Fish)
TrackDeck includes dynamic, context-aware Fish shell completions:

```bash
trackdeck completion --install
```
This registers tab autocompletions for all subcommands, markers, flags, and saved routing profiles.

---

## Full-Session Workflow with Adobe Audition Markers

Live band sessions and Sunday services are typically recorded as continuous 30-to-90-minute multitrack sessions containing multiple songs. TrackDeck uses Adobe Audition **Range Markers** to slice songs without touching audio editors manually.

### 1. Placing Markers in Adobe Audition
1. Open your multitrack session (`.sesx`) in Adobe Audition.
2. Open the **Markers Panel** (`Alt + 8` or `Window > Markers`).
3. Make a time selection over the span of a song.
4. Press **`M`** to create a Range Marker.
5. In the Markers panel, rename the marker to the song's title (e.g. `May Galak`, `Pasayahin Ang Langit`).
6. Save the session (`Ctrl + S`).

### 2. Inspecting Detected Markers via CLI
```bash
trackdeck markers "2026-09-06 SUNDAY SERVICE.sesx"
```
Output:
```text
=== Detected Songs / Markers in: 2026-09-06 SUNDAY SERVICE.sesx ===
Sample Rate: 48,000 Hz | Session Duration: 149m 31s (8971.3s)
------------------------------------------------------------------------------
#    | Song / Marker Title          | Start Time | Duration   | Type
------------------------------------------------------------------------------
1    | May Galak                    | 00:03:12   | 04:33      | Range
2    | Pasayahin Ang Langit         | 00:08:10   | 04:25      | Range
3    | Mahal na Mahal Kita          | 00:13:00   | 05:22      | Range
```

### 3. Ingesting Songs into StemDeck

#### Ingest a Specific Song by Marker Name
```bash
trackdeck session "2026-09-06 SUNDAY SERVICE.sesx" --marker "May Galak"
```

#### Batch Ingest All Marked Songs in One Command
```bash
trackdeck session "2026-09-06 SUNDAY SERVICE.sesx" --all-markers
```

#### Manual Timestamp Slicing (If Markers Were Not Added)
```bash
trackdeck session "2026-09-06 SUNDAY SERVICE.sesx" --start 03:12 --end 07:45 --title "May Galak"
```

---

## Single Song Ingestion

For standalone multitrack song folders or single-song projects:

```bash
trackdeck single /path/to/multitrack_folder/ --title "May Galak"
```

---

## Channel Routing Profiles

TrackDeck features an interactive terminal dialog that automatically classifies track names (e.g. `DRUM LOW` -> `drums`, `KEY1` -> `piano`, `MIC1` -> `vocals`, `SHURE` / `BEH` -> `other`).

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
9    | SHURE                        | other         | [Enter number to change]
10   | BEH1                         | other         | [Enter number to change]
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
| `trackdeck completion` | Output Fish completion script (`--install` to install) |

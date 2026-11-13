# TrackDeck Project Guidelines & Architectural Invariants

## 1. Project Role & System Boundaries
* **TrackDeck is Multitrack Ingestion Middleware for StemDeck:** It takes multitrack sessions (Adobe Audition, Reaper, raw stems) and synthesizes standard StemDeck jobs into `~/Documents/StemDeck/jobs/<job_id>/`.
* **StemDeck Data Contract:** TrackDeck strictly adheres to StemDeck's job schema:
  - 6 canonical 24-bit PCM WAV stems (`drums.wav`, `bass.wav`, `guitar.wav`, `piano.wav`, `vocals.wav`, `other.wav`) and the master sum (`mix.wav` / `source.wav`).
  - Bit-for-bit compatible waveform peaks (`peaks.json`) using 3,000-point min/max arrays.
  - Beatgrid (`beats.json`) containing tempo, beat times, and downbeats.
  - Job registration in `registry.json` with status `"done"`.
  - Atomic file writes (`.tmp` -> replace) to prevent race conditions with StemDeck file watchers.

## 2. Audio Ground Truth & Gain Staging
* **32-Bit Float Summing:** All stem bus summing must be executed in 32-bit floating point precision to eliminate intermediate digital clipping.
* **Peak Headroom Control:** If mix peak exceeds 0.95, proportionally attenuate all stems to `-0.5 dBFS`.

## 3. Profiles & Channel Routing Invariant
* **No Implicit Profiles:** Channel routing profiles are NEVER loaded automatically; they must be explicitly supplied with `--profile`.
* **Universal Audio Heuristics Only:** Default track naming heuristics must follow standard professional audio conventions (`VOX`, `GTR`, `KICK`, etc.). Never hardcode brand- or hardware-specific names (`SHURE`, `WIRELESS_1`).

## 4. Maintenance of Shell Completions
* Any modification to `track_deck/cli.py` (flags, subcommands, arguments) requires updating `track_deck/completions.py` in lockstep.

## 5. Rehearsal Player Export & CLI Standards
* **Static Rehearsal Export:** `trackdeck export <job> [Nth-job ...]` exports StemDeck jobs into a static rehearsal web player (e.g. `4StemPlayer` on Cloudflare Pages).
* **Target Directory Resolution:**
  - Default target repository is `~/Projects/4StemPlayer` (or configurable via `TRACKDECK_PLAYER_DIR` or `--dir / -d`).
  - If the first positional argument is an existing directory, it is gracefully accepted as `target_dir` with subsequent arguments treated as `jobs`.
* **Dynamic Job Completion:** Fish completions for `export` dynamically query `~/Documents/StemDeck/jobs`, extracting job IDs with their song titles, offering `latest`, and filtering out already-selected jobs across all Nth-job positions.

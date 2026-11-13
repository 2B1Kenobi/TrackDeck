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

## 5. Rehearsal Player Export, Publish & CLI Standards
* **Rehearsal Player Distribution (`export` vs. `publish`):**
  - **`trackdeck publish <job> [Nth-job ...]` (Fresh Cycle):** Starts the rehearsal cycle for the next weekly loop. Automatically cleans all prior songs from the target player repository (`4StemPlayer`), exports the newly specified jobs, creates a fresh `manifest.json`, and generates a new weekly 128-bit time-bounded passkey in `auth_config.js`.
  - **`trackdeck export <job> [Nth-job ...]` (Additive / Incremental):** Adds or updates songs within an active weekly set without removing existing songs. Merges entries into `manifest.json` and preserves the current valid weekly passkey.
* **Rehearsal Deployment Pipeline (`sync`):**
  - **`trackdeck sync "<commit message>"`:** Automated pipeline to stage all changes (`git add -A`), commit with the provided message, and push directly to GitHub in the target rehearsal player repository (`4StemPlayer`).
* **Target Directory & Player URL Resolution:**
  - Default target repository is `~/Projects/4StemPlayer` (or configurable via `TRACKDECK_PLAYER_DIR` or `--dir / -d`).
  - Default 1-tap link target is `https://jiamakaticma.pages.dev` (or configurable via `TRACKDECK_PLAYER_URL`).
  - If the first positional argument is an existing directory, it is gracefully accepted as `target_dir` with subsequent arguments treated as `jobs`.
* **Dynamic Job Completion:** Fish completions for `export` and `publish` dynamically query `~/Documents/StemDeck/jobs/registry.json` filtering for `status == "done"`, extracting job IDs with their clean song titles, offering `latest`, and filtering out already-selected jobs across all Nth-job positions.
* **Lyrics Resolution & Minimal NERV Invariant:**
  - `lyrics.md` exported for 4StemPlayer resolves `*.nerv.md` (`job_dir/song.nerv.md`, `exports/<title>.nerv.md`) as **first priority**, followed by `lyrics.txt`, `lyrics.json`, and `song.chordpro`.
  - All published lyrics are normalized into minimal NERV format: YAML frontmatter stripped, inline chords removed, and non-unique repeating stanzas deduplicated so only unique sections are displayed.
* **Isolated Stems Invariant (Exclusion of Master Reference Tracks):**
  - Master sum/reference tracks (`mix.wav`, `source.wav`, `master.wav`, `reference.wav`, `preview.wav`, `full.wav`) stored in StemDeck job directories are strictly excluded during export.
  - Rehearsal players strictly receive isolated constituent stems (`vocals`, `drums`, `bass`, `guitar`, `piano`, `keys`, `strings`, `fx`, `other`) so playback never doubles the master mix or breaks mute/solo isolation.

## 6. Title Sanitation & Trimming Invariant
* **Sanitation Algorithm (`suggest_sanitized_title`):**
  - All job titles exported to rehearsal players are inspected for video descriptors and metadata noise:
    - Encapsulating quotes (`"..."`, `'...'`, `“...”`, `‘...’`, backticks) are stripped.
    - Pipe delimiters and subsequent metadata (`| Tommy Walker`, `| Worship Circle`) are stripped.
    - Bracketed/parenthetical video noise (`(Official Lyric Video)`, `[with lyrics]`, `(Live)`, `(Audio)`, `(Visualizer)`) is removed.
    - Hyphen-separated artist prefixes/suffixes (`Artist - Title`) are cleanly split using canonical artist metadata or band heuristics.
* **Interactive Trimming Prompt (`resolve_sanitized_title`):**
  - If a title exceeds the length threshold (> 32 characters) or differs after sanitation, the CLI presents:
    - Original title.
    - Proposed sanitized title.
    - Prompt: `Enter title [press Enter to accept suggested]: `
  - Pressing Enter (empty input) accepts the suggested title. A custom entered string overrides the title.
  - In non-interactive mode (`-y` / `--yes` or non-TTY), the sanitized suggestion is accepted automatically without stopping.
* **Downstream Alignment:**
  - The resolved title governs the exported `manifest.json`, `song.json`, clean folder name, and stem file prefixes.

# TrackDeck Middleware Guidelines & Invariants

## 1. Host Application Contract Conformance (StemDeck)
TrackDeck operates as a multitrack ingestion middleware for StemDeck. When synthesizing and registering jobs into `~/Documents/StemDeck/jobs/<job_id>/`, TrackDeck must strictly respect StemDeck's schema:

- **Stem Files**: Output 6 canonical 24-bit PCM WAV stems (`drums.wav`, `bass.wav`, `guitar.wav`, `piano.wav`, `vocals.wav`, `other.wav`) and the master sum (`mix.wav` and `source.wav`).
- **Waveform Peaks (`peaks.json`)**: Fixed 3,000-point min/max array per stem over channel 0, bit-for-bit compatible with StemDeck's `scan_stem` streaming algorithm.
- **Beatgrid (`beats.json`)**: Detected tempo (`bpm`), beat timestamps, and downbeat indices.
- **Job Registration (`registry.json`)**: Atomic update to `jobs/registry.json` matching StemDeck's `Job` model with `"stage_message": "Done"` and `"progress": 1.0`.
- **Atomic File Writes**: Always write files using atomic replacement (write to `.tmp` then `replace`) to avoid race conditions with StemDeck file watchers.

## 2. Lossless Stem Bus Summing & Gain Staging
- All audio channel summing must be performed in **32-bit floating point precision** to prevent intermediate clipping.
- **Peak Headroom Control**: If the master mix peak exceeds `0.95` (clipping threshold), apply proportional attenuation across all stems so the peak is held at `-0.5 dBFS` with zero digital distortion.
- If the recording is quiet (`peak < 0.25`), apply transparent proportional gain boost.

## 3. Profiles & Channel Heuristics Invariant
- **No Implicit Profile Loading**: Channel routing profiles are **NEVER loaded by default**.
- Profiles must be explicitly requested by the user via the `--profile <name_or_path>` switch.
- When no profile is passed, TrackDeck runs an interactive track-to-stem assignment dialog (or uses heuristic naming defaults if `-y` is passed).
- **Universal Industry Heuristics Only**: Default track name heuristics must strictly stick to professional audio mixing standards:
  - `vocals`: `VOX`, `VOCAL`, `MIC`, `LEAD`, `BGV`, `BACKING`, `HARMONY`, `CHOIR`
  - `drums`: `DRUM`, `KICK`, `BD`, `SNARE`, `SN`, `TOM`, `HAT`, `HIHAT`, `CYMBAL`, `OH`, `OVERHEAD`, `PERC`
  - `bass`: `BASS`, `BS`
  - `guitar`: `GUITAR`, `GTR`, `ACOUSTIC`, `ELECTRIC`, `EG`
  - `piano`: `KEY`, `KEYS`, `PIANO`, `SYNTH`, `ORGAN`, `RHODES`, `KEYBOARD`, `PAD`
  - `other`: `ROOM`, `AMBIENT`, `AUDIENCE`, `TALK`, `SPEECH`, `CLICK`, `GUIDE`, `AUX`, `FX`
- **Prohibition on Hardware/Brand-Specific Defaults**: Never hardcode user-specific or brand-specific labels (e.g. `SHURE`, `BEH`, `WIRELESS_1`) into default heuristics. They must fall back to `other` unless mapped in an explicit profile.

## 4. Command Structure Invariant
- Preempting ingestion with a generic `process` command is forbidden.
- Use `trackdeck session <session_path>` for full-session multitrack recordings (Adobe Audition, worship sets, full concerts) with marker support.
- Use `trackdeck single <path>` for single-song multitracks or plain WAV folders.
- Use `trackdeck markers <session_path>` to list detected song markers.
- Use `trackdeck profiles` to manage saved channel routing profiles.

## 5. CLI Maintenance & Shell Completions Invariant
- Whenever modifying `track_deck/cli.py` (adding/renaming flags, arguments, or subcommands), the Fish shell completion engine in `track_deck/completions.py` MUST be updated in lockstep.
- **Native Completion Commands**:
  - `trackdeck completion fish`: Prints dynamic Fish completion script to stdout.
  - `trackdeck completion --install`: Installs and links completions directly into `~/.config/fish/completions/trackdeck.fish` and `track-deck.fish`.
- **Pre-Commit Enforcement**:
  - A Git pre-commit hook in `.githooks/pre-commit` automatically verifies and compiles Fish completions whenever `cli.py` or `completions.py` is staged.
  - The hook validates syntax using `fish -n`.

## 6. Attribution & Identity
- Default credit is strictly `"TrackDeck"`.
- Never place personal names in git commit messages, code comments, or generated files.

## 7. Node.js / NVM Policy
- Strictly forbidden to invoke `nvm`, `node`, `npm`, or `npx` or install Node packages without explicit user authorization. All hooks and tools are pure Python and Bash.

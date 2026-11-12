"""Fish shell completions generator and installer for TrackDeck."""

from pathlib import Path
from typing import Tuple


def generate_fish_completions() -> str:
    """Generate complete, dynamic Fish shell completions for trackdeck."""
    return '''# Fish completions for trackdeck
# Generated automatically by TrackDeck built-in completion engine.

function __fish_trackdeck_needs_command
    set -l cmd (commandline -opc)
    if test (count $cmd) -eq 1
        return 0
    end
    return 1
end

function __fish_trackdeck_using_subcommand
    set -l cmd (commandline -opc)
    if test (count $cmd) -ge 2
        if test "$cmd[2]" = "$argv[1]"
            return 0
        end
    end
    return 1
end

function __fish_trackdeck_subcommand_needs_file
    set -l cmd (commandline -opc)
    set -l pos
    for c in $cmd[2..-1]
        if not string match -q -- '-*' $c
            set -a pos $c
        end
    end
    if test (count $pos) -le 1
        return 0
    end
    return 1
end

function __fish_trackdeck_profiles
    set -l prof_dir "$HOME/.config/trackdeck/profiles"
    if not test -d "$prof_dir"
        return
    end
    for p in $prof_dir/*.json
        if test -f "$p"
            set -l pname (basename "$p" .json)
            printf "%s\\t%s\\n" "$pname" "TrackDeck routing profile"
        end
    end
end

for app in trackdeck
    # Disable default file completion unless explicitly triggered
    complete -c $app -f

    # Top-level subcommands
    complete -c $app -n '__fish_trackdeck_needs_command' -a 'session' -d 'Ingest a full-session multitrack recording (with markers)'
    complete -c $app -n '__fish_trackdeck_needs_command' -a 'single' -d 'Ingest a single multitrack song'
    complete -c $app -n '__fish_trackdeck_needs_command' -a 'markers' -d 'List detected song markers in session'
    complete -c $app -n '__fish_trackdeck_needs_command' -a 'profiles' -d 'List or manage saved channel routing profiles'
    complete -c $app -n '__fish_trackdeck_needs_command' -a 'patch-stemdeck' -d 'Patch StemDeck backend for live rescan'
    complete -c $app -n '__fish_trackdeck_needs_command' -a 'rescan' -d 'Trigger StemDeck live library rescan via API'
    complete -c $app -n '__fish_trackdeck_needs_command' -a 'export' -d 'Export StemDeck jobs into static rehearsal player'
    complete -c $app -n '__fish_trackdeck_needs_command' -a 'completion' -d 'Output or install Fish shell completion'

    # Global options
    complete -c $app -s h -l help -d 'Show help'
    complete -c $app -s v -l version -d 'Show version'

    # Subcommand: session
    complete -c $app -n '__fish_trackdeck_using_subcommand session; and __fish_trackdeck_subcommand_needs_file' -r -F
    complete -c $app -n '__fish_trackdeck_using_subcommand session' -l marker -d 'Ingest a specific song by marker title'
    complete -c $app -n '__fish_trackdeck_using_subcommand session' -l all-markers -d 'Batch-ingest all range markers into individual songs'
    complete -c $app -n '__fish_trackdeck_using_subcommand session' -l start -d 'Start time (HH:MM:SS or seconds)'
    complete -c $app -n '__fish_trackdeck_using_subcommand session' -l end -d 'End time (HH:MM:SS or seconds)'
    complete -c $app -n '__fish_trackdeck_using_subcommand session' -l title -d 'Song title override'
    complete -c $app -n '__fish_trackdeck_using_subcommand session' -s p -l profile -x -a '(__fish_trackdeck_profiles)' -d 'Explicitly load channel routing profile'
    complete -c $app -n '__fish_trackdeck_using_subcommand session' -s y -l yes -d 'Non-interactive mode (accept defaults)'

    # Subcommand: single
    complete -c $app -n '__fish_trackdeck_using_subcommand single; and __fish_trackdeck_subcommand_needs_file' -r -F
    complete -c $app -n '__fish_trackdeck_using_subcommand single' -l title -d 'Song title override'
    complete -c $app -n '__fish_trackdeck_using_subcommand single' -s p -l profile -x -a '(__fish_trackdeck_profiles)' -d 'Explicitly load channel routing profile'
    complete -c $app -n '__fish_trackdeck_using_subcommand single' -s y -l yes -d 'Non-interactive mode (accept defaults)'

    # Subcommand: markers
    complete -c $app -n '__fish_trackdeck_using_subcommand markers; and __fish_trackdeck_subcommand_needs_file' -r -F
    complete -c $app -n '__fish_trackdeck_using_subcommand markers' -s h -l help -d 'Show help'

    # Subcommand: profiles
    complete -c $app -n '__fish_trackdeck_using_subcommand profiles' -l list -d 'List all saved routing profiles'
    complete -c $app -n '__fish_trackdeck_using_subcommand profiles' -l show -x -a '(__fish_trackdeck_profiles)' -d 'Display profile mapping'
    complete -c $app -n '__fish_trackdeck_using_subcommand profiles' -l delete -x -a '(__fish_trackdeck_profiles)' -d 'Delete a profile'

    # Subcommand: export
    complete -c $app -n '__fish_trackdeck_using_subcommand export' -r -F -d 'Target player repository or job ID'

    # Subcommand: completion
    complete -c $app -n '__fish_trackdeck_using_subcommand completion' -l install -d 'Install completions into ~/.config/fish/completions/'
    complete -c $app -n '__fish_trackdeck_using_subcommand completion' -a 'fish' -d 'Generate Fish shell completion'
end
'''


def install_fish_completions() -> Tuple[bool, str]:
    """Install or update Fish completion script for trackdeck."""
    fish_comp_dir = Path.home() / ".config" / "fish" / "completions"
    fish_comp_dir.mkdir(parents=True, exist_ok=True)

    content = generate_fish_completions()
    target_file = fish_comp_dir / "trackdeck.fish"
    alias_file = fish_comp_dir / "track-deck.fish"

    try:
        target_file.write_text(content, encoding="utf-8")
        if alias_file.is_symlink() or alias_file.exists():
            alias_file.unlink(missing_ok=True)

        return True, f"[+] Successfully installed Fish completions to: {target_file}"
    except Exception as e:
        return False, f"[!] Failed to write Fish completions: {e}"

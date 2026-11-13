import io
import unittest
from unittest.mock import patch

from track_deck.exporter import resolve_sanitized_title, suggest_sanitized_title


class TestTitleSanitation(unittest.TestCase):
    def test_suggest_sanitized_title_cleanups(self):
        cases = [
            (
                "\"Only a God Like You\" (Lyric Video) | Tommy Walker",
                "Tommy Walker",
                "Only a God Like You",
                "Only a God Like You"
            ),
            (
                "Darlene Zschech - In Jesus' Name (Official Lyric Video)",
                "Darlene Zschech",
                "",
                "In Jesus' Name"
            ),
            (
                "Stay Amazed - Gateway Worship [with lyrics]",
                "Gateway Worship",
                "Stay Amazed",
                "Stay Amazed"
            ),
            (
                "We Fall Down / Awesome in This Place | Meredith Andrews | Worship Circle FOUNDATIONS",
                "Meredith Andrews",
                "",
                "We Fall Down / Awesome in This Place"
            ),
            (
                "O Praise the Name (Anastasis)",
                "Hillsong Worship",
                "O Praise the Name (Anastasis)",
                "O Praise the Name (Anastasis)"
            ),
            (
                "10,000 Reasons (Bless the Lord) [Official Video]",
                "Matt Redman",
                "10,000 Reasons (Bless the Lord)",
                "10,000 Reasons (Bless the Lord)"
            )
        ]

        for raw, artist, ident, expected in cases:
            with self.subTest(raw=raw):
                clean = suggest_sanitized_title(raw, artist=artist, identity_title=ident)
                self.assertEqual(clean, expected)

    def test_resolve_sanitized_title_non_interactive(self):
        # Non-interactive mode should auto-sanitize without prompting
        raw = "Stay Amazed - Gateway Worship [with lyrics]"
        resolved = resolve_sanitized_title(raw, artist="Gateway Worship", interactive=False)
        self.assertEqual(resolved, "Stay Amazed")

    def test_resolve_sanitized_title_interactive_accept_default(self):
        raw = "\"Only a God Like You\" (Lyric Video) | Tommy Walker"
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value=""):
            resolved = resolve_sanitized_title(raw, artist="Tommy Walker", interactive=True)
            self.assertEqual(resolved, "Only a God Like You")

    def test_resolve_sanitized_title_interactive_user_override(self):
        raw = "We Fall Down / Awesome in This Place | Meredith Andrews | Worship Circle FOUNDATIONS"
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="We Fall Down / Awesome"):
            resolved = resolve_sanitized_title(raw, artist="Meredith Andrews", interactive=True)
            self.assertEqual(resolved, "We Fall Down / Awesome")

    def test_clean_short_title_untouched(self):
        raw = "Way Maker"
        # Should not prompt or change
        resolved = resolve_sanitized_title(raw, artist="Sinach", interactive=True)
        self.assertEqual(resolved, "Way Maker")

    def test_ignored_master_stems_filter(self):
        from track_deck.exporter import get_default_stemdeck_jobs_dir
        # Ensure 'mix', 'source', 'master' are ignored
        ignored = {"mix", "source", "master", "reference", "preview", "full"}
        candidate_stems = ["vocals", "drums", "bass", "guitar", "piano", "mix", "other", "source"]
        filtered = [s for s in candidate_stems if s.lower() not in ignored]
        self.assertEqual(filtered, ["vocals", "drums", "bass", "guitar", "piano", "other"])


if __name__ == "__main__":
    unittest.main()

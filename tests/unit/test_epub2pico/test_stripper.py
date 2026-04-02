"""Tests for epub2pico.stripper -- content stripping heuristics."""

import pytest

from epub2pico.stripper import (
    strip_content,
    detect_copyright_blocks,
    detect_page_numbers,
    detect_dividers,
    detect_toc_duplicates,
    detect_repeated_headers,
)


class TestDetectCopyrightBlocks:
    """Test copyright page detection."""

    def test_typical_copyright_block(self):
        """Block with 2+ copyright keywords is detected."""
        lines = [
            "Copyright 2023 by John Author",
            "All rights reserved. No part of this publication may be reproduced.",
            "Published by Example Press",
            "ISBN 978-0-123456-78-9",
            "Printed in the United States of America",
        ]
        result = detect_copyright_blocks(lines)
        assert len(result) == 1
        assert result[0].reason == "copyright_page"

    def test_minimal_copyright_block(self):
        """Block with exactly 2 keywords is detected."""
        lines = [
            "Copyright 2023 by Author Name",
            "All rights reserved.",
        ]
        result = detect_copyright_blocks(lines)
        assert len(result) == 1

    def test_single_keyword_not_detected(self):
        """A block with only 1 copyright keyword is not flagged."""
        lines = [
            "Copyright 2023 by Author Name",
            "This is just a mention of the year.",
        ]
        result = detect_copyright_blocks(lines)
        assert len(result) == 0

    def test_copyright_in_story_not_detected(self):
        """Normal prose mentioning 'copyright' once is not flagged."""
        lines = [
            'He held the copyright to the song.',
            'It was his greatest achievement.',
        ]
        result = detect_copyright_blocks(lines)
        assert len(result) == 0


class TestDetectPageNumbers:
    """Test page number detection."""

    def test_bare_number(self):
        """Standalone '42' is detected as page number."""
        lines = ["", "42", ""]
        result = detect_page_numbers(lines)
        assert len(result) == 1
        assert result[0].reason == "page_number"

    def test_formatted_number(self):
        """'- 42 -' format is detected."""
        lines = ["", "- 42 -", ""]
        result = detect_page_numbers(lines)
        assert len(result) == 1
        assert result[0].reason == "page_number"

    def test_padded_number(self):
        """'  42  ' with whitespace is detected."""
        lines = ["  42  "]
        result = detect_page_numbers(lines)
        assert len(result) == 1

    def test_number_in_text_preserved(self):
        """'There were 42 of them' is NOT detected."""
        lines = ["There were 42 of them"]
        result = detect_page_numbers(lines)
        assert len(result) == 0

    def test_large_number_not_detected(self):
        """Numbers > 4 digits are not detected (not page numbers)."""
        lines = ["12345"]
        result = detect_page_numbers(lines)
        assert len(result) == 0

    def test_multiple_page_numbers(self):
        """Multiple page numbers throughout text."""
        lines = ["text", "1", "more text", "2", "end text", "3"]
        result = detect_page_numbers(lines)
        assert len(result) == 3


class TestDetectDividers:
    """Test decorative divider detection."""

    def test_dashes(self):
        """'---' is detected as divider."""
        lines = ["---"]
        result = detect_dividers(lines)
        assert len(result) == 1
        assert result[0].reason == "divider"

    def test_asterisks(self):
        """'***' is detected as divider."""
        lines = ["***"]
        result = detect_dividers(lines)
        assert len(result) == 1

    def test_equals(self):
        """'===' is detected as divider."""
        lines = ["==="]
        result = detect_dividers(lines)
        assert len(result) == 1

    def test_spaced_asterisks(self):
        """'* * *' is detected as divider."""
        lines = ["* * *"]
        result = detect_dividers(lines)
        assert len(result) == 1

    def test_spaced_dashes(self):
        """'- - -' is detected as divider."""
        lines = ["- - -"]
        result = detect_dividers(lines)
        assert len(result) == 1

    def test_long_divider(self):
        """Long divider line is detected."""
        lines = ["----------"]
        result = detect_dividers(lines)
        assert len(result) == 1

    def test_em_dash_in_sentence_preserved(self):
        """'She paused---then continued' is NOT a divider."""
        lines = ["She paused---then continued"]
        result = detect_dividers(lines)
        assert len(result) == 0

    def test_dashes_in_text_preserved(self):
        """Dashes within a sentence are preserved."""
        lines = ["The well-known author---famous for her work---spoke."]
        result = detect_dividers(lines)
        assert len(result) == 0


class TestDetectTocDuplicates:
    """Test table of contents duplicate detection."""

    def test_toc_detected(self):
        """A sequence of lines matching chapter titles is detected."""
        chapter_titles = [
            "Chapter 1: The Beginning",
            "Chapter 2: The Middle",
            "Chapter 3: The End",
            "Chapter 4: Epilogue",
        ]
        lines = [
            "Chapter 1: The Beginning",
            "Chapter 2: The Middle",
            "Chapter 3: The End",
            "Chapter 4: Epilogue",
        ]
        result = detect_toc_duplicates(lines, chapter_titles)
        assert len(result) == 1
        assert result[0].reason == "toc_duplicate"

    def test_non_toc_not_detected(self):
        """Regular short lines that don't match titles are not flagged."""
        chapter_titles = ["Chapter 1", "Chapter 2", "Chapter 3"]
        lines = [
            "It was morning.",
            "The sun was up.",
            "Birds sang loudly.",
            "Time to go.",
        ]
        result = detect_toc_duplicates(lines, chapter_titles)
        assert len(result) == 0

    def test_empty_titles_handled(self):
        """Empty chapter title list doesn't cause errors."""
        lines = ["Some text", "More text"]
        result = detect_toc_duplicates(lines, [])
        assert len(result) == 0

    def test_too_few_lines_not_detected(self):
        """Fewer than 3 matching lines is not flagged as TOC."""
        chapter_titles = ["Chapter 1", "Chapter 2"]
        lines = ["Chapter 1", "Chapter 2"]
        result = detect_toc_duplicates(lines, chapter_titles)
        assert len(result) == 0


class TestDetectRepeatedHeaders:
    """Test running header/footer detection."""

    def test_repeated_header_detected(self):
        """A short line appearing at 3+ chapter boundaries is detected."""
        lines = [
            "---CHAPTER: Ch 1---",
            "",
            "Book Title",
            "Some story text here.",
            "",
            "---CHAPTER: Ch 2---",
            "",
            "Book Title",
            "More story text.",
            "",
            "---CHAPTER: Ch 3---",
            "",
            "Book Title",
            "Even more story.",
        ]
        result = detect_repeated_headers(lines)
        assert len(result) >= 3
        assert all(s.reason == "repeated_header" for s in result)

    def test_non_repeated_not_detected(self):
        """Unique text near chapter boundaries is not flagged."""
        lines = [
            "---CHAPTER: Ch 1---",
            "",
            "Unique text one.",
            "",
            "---CHAPTER: Ch 2---",
            "",
            "Unique text two.",
            "",
            "---CHAPTER: Ch 3---",
            "",
            "Unique text three.",
        ]
        result = detect_repeated_headers(lines)
        assert len(result) == 0

    def test_few_chapters_not_detected(self):
        """With fewer than 3 chapters, no repeated headers detected."""
        lines = [
            "---CHAPTER: Ch 1---",
            "Header",
            "Text",
            "---CHAPTER: Ch 2---",
            "Header",
            "Text",
        ]
        result = detect_repeated_headers(lines)
        assert len(result) == 0


class TestStripContent:
    """Test the full stripping pipeline."""

    def test_copyright_stripped(self):
        """Copyright block is removed from full text."""
        text = (
            "Copyright 2023 by Author\n"
            "All rights reserved.\n"
            "ISBN 978-0-123456-78-9\n"
            "\n"
            "Chapter 1 text here.\n"
            "More story content."
        )
        cleaned, stripped = strip_content(text)
        assert "Copyright" not in cleaned
        assert "ISBN" not in cleaned
        assert "Chapter 1 text here." in cleaned
        assert len(stripped) >= 1

    def test_page_numbers_stripped(self):
        """Standalone page numbers are removed."""
        text = "Story text.\n\n42\n\nMore story."
        cleaned, stripped = strip_content(text)
        assert "\n42\n" not in cleaned
        assert "Story text." in cleaned
        assert "More story." in cleaned

    def test_dividers_stripped(self):
        """Divider lines are removed."""
        text = "Before.\n\n***\n\nAfter."
        cleaned, stripped = strip_content(text)
        assert "***" not in cleaned
        assert "Before." in cleaned
        assert "After." in cleaned

    def test_actual_content_preserved(self):
        """Normal story text is never stripped."""
        text = (
            "The quick brown fox jumped over the lazy dog.\n"
            "\n"
            "She paused---then continued walking through the rain.\n"
            "\n"
            "There were 42 soldiers in the regiment.\n"
            "\n"
            '"Hello," she said. "How are you?"'
        )
        cleaned, stripped = strip_content(text)
        assert "quick brown fox" in cleaned
        assert "She paused---then continued" in cleaned
        assert "42 soldiers" in cleaned

    def test_empty_text(self):
        """Empty text produces empty result."""
        cleaned, stripped = strip_content("")
        assert cleaned == ""
        assert stripped == []

    def test_chapter_titles_passed_for_toc(self):
        """Chapter titles are used for TOC duplicate detection."""
        titles = ["Chapter 1", "Chapter 2", "Chapter 3", "Chapter 4"]
        text = (
            "Chapter 1\n"
            "Chapter 2\n"
            "Chapter 3\n"
            "Chapter 4\n"
            "\n"
            "Actual story content here."
        )
        cleaned, stripped = strip_content(text, chapter_titles=titles)
        assert "Actual story content here." in cleaned
        # The TOC block should have been detected
        toc_stripped = [s for s in stripped if s.reason == "toc_duplicate"]
        assert len(toc_stripped) == 1

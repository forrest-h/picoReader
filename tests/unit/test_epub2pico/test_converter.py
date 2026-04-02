"""Tests for epub2pico.converter -- epub extraction and HTML-to-text."""

import pytest
from unittest.mock import MagicMock
import ebooklib

from epub2pico.converter import (
    html_to_text,
    build_toc_map,
    chapters_to_text,
    count_words,
    extract_chapters,
    _strip_fragment,
)


class TestHtmlToText:
    """Test HTML to plain text conversion."""

    def test_simple_paragraphs(self):
        """Simple <p> tags become double-newline separated text."""
        html = "<html><body><p>Hello</p><p>World</p></body></html>"
        result = html_to_text(html)
        assert result == "Hello\n\nWorld"

    def test_nested_tags(self):
        """Inline tags are stripped, text preserved."""
        html = "<html><body><p>The <em>quick</em> fox</p></body></html>"
        result = html_to_text(html)
        assert result == "The quick fox"

    def test_script_removal(self):
        """Script tags and their content are removed."""
        html = '<html><body><script>var x = 1;</script><p>Text</p></body></html>'
        result = html_to_text(html)
        assert "var x" not in result
        assert "Text" in result

    def test_style_removal(self):
        """Style tags and their content are removed."""
        html = '<html><body><style>body { color: red; }</style><p>Text</p></body></html>'
        result = html_to_text(html)
        assert "color" not in result
        assert "Text" in result

    def test_nav_removal(self):
        """Nav tags and their content are removed."""
        html = '<html><body><nav><a href="#">Link</a></nav><p>Text</p></body></html>'
        result = html_to_text(html)
        assert "Link" not in result
        assert "Text" in result

    def test_whitespace_normalization(self):
        """Excessive whitespace within paragraphs is collapsed."""
        html = "<html><body><p>  too   many   spaces  </p></body></html>"
        result = html_to_text(html)
        assert result == "too many spaces"

    def test_heading_extraction(self):
        """Heading tags are extracted as text blocks."""
        html = "<html><body><h1>Title</h1><p>Content</p></body></html>"
        result = html_to_text(html)
        assert "Title" in result
        assert "Content" in result

    def test_list_items(self):
        """List items are extracted."""
        html = "<html><body><ul><li>One</li><li>Two</li></ul></body></html>"
        result = html_to_text(html)
        assert "One" in result
        assert "Two" in result

    def test_blockquote(self):
        """Blockquote content is extracted."""
        html = "<html><body><blockquote>Quoted text</blockquote></body></html>"
        result = html_to_text(html)
        assert "Quoted text" in result

    def test_no_block_elements_fallback(self):
        """When no block elements exist, raw text extraction is used."""
        html = "<html><body>Just plain text here</body></html>"
        result = html_to_text(html)
        assert "Just plain text here" in result

    def test_empty_html(self):
        """Empty HTML body produces empty string."""
        html = "<html><body></body></html>"
        result = html_to_text(html)
        assert result == ""

    def test_realistic_chapter(self, sample_html_chapter):
        """Realistic epub chapter HTML is converted correctly."""
        result = html_to_text(sample_html_chapter)
        assert "dark and stormy night" in result
        assert "Sarah pulled her coat" in result
        assert "She didn't answer" in result


class TestBuildTocMap:
    """Test TOC flattening."""

    def test_flat_toc(self):
        """Simple flat TOC produces direct mapping."""
        ch1 = MagicMock()
        ch1.href = "ch1.xhtml"
        ch1.title = "Chapter 1"

        ch2 = MagicMock()
        ch2.href = "ch2.xhtml"
        ch2.title = "Chapter 2"

        result = build_toc_map([ch1, ch2])
        assert result == {
            "ch1.xhtml": "Chapter 1",
            "ch2.xhtml": "Chapter 2",
        }

    def test_nested_toc(self, sample_toc):
        """Nested TOC is flattened correctly."""
        result = build_toc_map(sample_toc)
        assert result["part1.xhtml"] == "Part 1"
        assert result["chapter1.xhtml"] == "Chapter 1: The Beginning"
        assert result["chapter2.xhtml"] == "Chapter 2: The Journey"
        assert result["part2.xhtml"] == "Part 2"

    def test_fragment_href_stripped(self, sample_toc):
        """Fragment identifiers in TOC hrefs are stripped."""
        result = build_toc_map(sample_toc)
        # chapter3.xhtml#section1 should be stored as chapter3.xhtml
        assert "chapter3.xhtml" in result
        assert result["chapter3.xhtml"] == "Chapter 3: The End"

    def test_empty_toc(self):
        """Empty TOC returns empty dict."""
        result = build_toc_map([])
        assert result == {}


class TestChaptersToText:
    """Test chapter-to-text assembly with markers."""

    def test_chapter_marker_format(self):
        """Chapters with titles get ---CHAPTER: title--- markers."""
        chapters = [{
            'title': 'The Beginning',
            'html': '<html><body><p>Story text here.</p></body></html>',
            'href': 'ch1.xhtml',
        }]
        result = chapters_to_text(chapters)
        assert "---CHAPTER: The Beginning---" in result
        assert "Story text here." in result

    def test_no_title_no_marker(self):
        """Chapters without titles get no marker."""
        chapters = [{
            'title': '',
            'html': '<html><body><p>Text without title.</p></body></html>',
            'href': 'ch1.xhtml',
        }]
        result = chapters_to_text(chapters)
        assert "---CHAPTER:" not in result
        assert "Text without title." in result

    def test_empty_chapter_dropped(self):
        """Chapters producing no text are silently dropped."""
        chapters = [
            {
                'title': 'Empty Chapter',
                'html': '<html><body></body></html>',
                'href': 'empty.xhtml',
            },
            {
                'title': 'Real Chapter',
                'html': '<html><body><p>Content</p></body></html>',
                'href': 'real.xhtml',
            },
        ]
        result = chapters_to_text(chapters)
        assert "Empty Chapter" not in result
        assert "Real Chapter" in result
        assert "Content" in result

    def test_multiple_chapters(self):
        """Multiple chapters are assembled in order."""
        chapters = [
            {
                'title': 'Chapter 1',
                'html': '<html><body><p>First chapter.</p></body></html>',
                'href': 'ch1.xhtml',
            },
            {
                'title': 'Chapter 2',
                'html': '<html><body><p>Second chapter.</p></body></html>',
                'href': 'ch2.xhtml',
            },
        ]
        result = chapters_to_text(chapters)
        ch1_pos = result.index("Chapter 1")
        ch2_pos = result.index("Chapter 2")
        assert ch1_pos < ch2_pos


class TestCountWords:
    """Test word counting."""

    def test_simple_count(self):
        """Basic word count."""
        text = "one two three four five"
        assert count_words(text) == 5

    def test_multiline_count(self):
        """Words across multiple lines."""
        text = "one two\nthree four\nfive six seven"
        assert count_words(text) == 7

    def test_chapter_markers_excluded(self):
        """Chapter markers are not counted as words."""
        text = "---CHAPTER: Chapter 1---\n\nHere are five real words."
        count = count_words(text)
        assert count == 5

    def test_empty_text(self):
        """Empty text has 0 words."""
        assert count_words("") == 0

    def test_whitespace_only(self):
        """Whitespace-only text has 0 words."""
        assert count_words("   \n\n  \n  ") == 0


class TestExtractChapters:
    """Test chapter extraction from mock epub books."""

    def test_basic_extraction(self, mock_epub_book):
        """Chapters are extracted in spine order."""
        toc_ch1 = MagicMock()
        toc_ch1.href = "ch1.xhtml"
        toc_ch1.title = "Chapter 1"
        toc_ch2 = MagicMock()
        toc_ch2.href = "ch2.xhtml"
        toc_ch2.title = "Chapter 2"

        book = mock_epub_book(
            author="Author",
            title="Title",
            spine_items=[
                {'id': 'ch1', 'href': 'ch1.xhtml', 'html': '<p>First</p>'},
                {'id': 'ch2', 'href': 'ch2.xhtml', 'html': '<p>Second</p>'},
            ],
            toc=[toc_ch1, toc_ch2],
        )

        chapters, skipped = extract_chapters(book)
        assert len(chapters) == 2
        assert chapters[0]['title'] == "Chapter 1"
        assert chapters[1]['title'] == "Chapter 2"

    def test_linear_no_skipped(self, mock_epub_book):
        """Spine items with linear='no' are skipped."""
        book = mock_epub_book(
            spine_items=[
                {'id': 'cover', 'href': 'cover.xhtml', 'linear': 'no',
                 'html': '<p>Cover</p>'},
                {'id': 'ch1', 'href': 'ch1.xhtml',
                 'html': '<p>Content</p>'},
            ],
        )

        chapters, skipped = extract_chapters(book)
        assert len(chapters) == 1
        assert len(skipped) == 1
        assert skipped[0].reason == "front_matter"

    def test_no_toc_entry(self, mock_epub_book):
        """Spine items without TOC entries get empty titles."""
        book = mock_epub_book(
            spine_items=[
                {'id': 'ch1', 'href': 'ch1.xhtml', 'html': '<p>Text</p>'},
            ],
            toc=[],
        )

        chapters, skipped = extract_chapters(book)
        assert len(chapters) == 1
        assert chapters[0]['title'] == ""


class TestStripFragment:
    """Test href fragment stripping."""

    def test_with_fragment(self):
        assert _strip_fragment("chapter1.xhtml#section2") == "chapter1.xhtml"

    def test_without_fragment(self):
        assert _strip_fragment("chapter1.xhtml") == "chapter1.xhtml"

    def test_empty_fragment(self):
        assert _strip_fragment("chapter1.xhtml#") == "chapter1.xhtml"

# Phase 4: Epub Converter — Standalone CLI Tool

> **Dependency:** None. This phase is completely independent of the firmware and can be developed in parallel with any other phase.

**Goal:** Build a standalone, pipx-installable CLI tool that converts .epub files into the picoReader `.txt` format, with automatic metadata extraction, content stripping heuristics, and an interactive review mode.

---

## 1. Package Structure

### Directory layout

```
tools/epub2pico/
  pyproject.toml              # Package metadata, deps, entry point
  epub2pico/
    __init__.py               # Version string
    cli.py                    # Click CLI entry point
    converter.py              # Epub -> ordered chapter text extraction
    stripper.py               # Content stripping heuristics
    formatter.py              # Filename generation from metadata
```

### Why this structure

- **Separate from firmware entirely.** Lives under `tools/` to make it obvious this runs on a desktop, not on the Pico. No shared code, no shared imports.
- **One module per concern.** The converter reads the epub and produces raw text. The stripper cleans it. The formatter names the output file. The CLI orchestrates the pipeline.
- **Small surface area.** Four source files plus the CLI. Easy to test, easy to maintain.

---

## 2. Installation

### pipx (recommended for end users)

```bash
pipx install ./tools/epub2pico
```

This creates an isolated virtualenv and exposes `epub2pico` as a globally-available command. The user never touches a venv manually.

### pip editable (for development)

```bash
pip install -e ./tools/epub2pico
```

Editable install so changes to the source files take effect immediately without reinstalling.

### Post-install verification

```bash
epub2pico --version
epub2pico --help
```

Both must work from any directory after installation.

---

## 3. pyproject.toml

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "epub2pico"
version = "0.1.0"
description = "Convert .epub files to picoReader .txt format"
requires-python = ">=3.9"
dependencies = [
    "ebooklib>=0.18",
    "beautifulsoup4>=4.12",
    "click>=8.0",
    "lxml>=4.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov",
]

[project.scripts]
epub2pico = "epub2pico.cli:main"

[tool.setuptools.packages.find]
where = ["."]
```

### Key decisions

- **ebooklib** for epub parsing. It is the standard Python epub library, handles epub2 and epub3, and exposes spine order and TOC structure.
- **BeautifulSoup + lxml** for HTML-to-text. Epubs are XHTML internally, often malformed. BS4 with lxml handles this gracefully.
- **Click** for CLI. Simple decorator-based interface. Well-known, well-documented, no magic.
- **Python >=3.9** because that is the oldest version still receiving security patches and supports all the type hints we want.
- **No runtime dependency on the firmware.** This tool knows nothing about CircuitPython.

---

## 4. Auto Mode (Default)

### Usage

```bash
epub2pico book.epub                         # Single file -> same directory
epub2pico books_dir/                        # Batch all .epub files in directory
epub2pico book.epub --output-dir /sd/books/ # Custom output directory
epub2pico books_dir/ --output-dir /sd/books/
```

### Pipeline (pseudocode)

```
def convert(epub_path, output_dir):
    # 1. Parse epub
    book = ebooklib.epub.read_epub(epub_path)

    # 2. Extract metadata
    metadata = extract_metadata(book)
    # -> { author, title, series, series_index, genre }

    # 3. Extract chapters in spine order
    chapters = extract_chapters(book)
    # -> [ { title: str, html: str }, ... ]

    # 4. Convert HTML to plain text, insert chapter markers
    text = ""
    for chapter in chapters:
        text += "---CHAPTER: {}---\n\n".format(chapter.title)
        text += html_to_text(chapter.html)
        text += "\n\n"

    # 5. Strip junk content
    text = strip_content(text)

    # 6. Count words
    word_count = count_words(text)

    # 7. Generate filename
    filename = format_filename(metadata, word_count)

    # 8. Write output
    write_output(output_dir / filename, text)

    return filename, word_count
```

### Batch mode behavior

When given a directory:
1. Glob for `*.epub` files
2. Process each in alphabetical order
3. Print progress: `[1/12] Converting: Author - Title...`
4. Print summary at end: `Converted 12 files. 2 skipped (already exist). 1 failed.`
5. On failure: print error, continue to next file (do not abort batch)

### Output collision handling

If the output filename already exists:
- Auto mode: skip and warn (`SKIP: output already exists: filename.txt`)
- Pass `--overwrite` to replace existing files

---

## 5. Review Mode

### Usage

```bash
epub2pico --review book.epub       # Interactive, single file
epub2pico --review books_dir/      # Interactive, batch
```

### Interactive flow (pseudocode)

```
def review_convert(epub_path, output_dir):
    # Run the full pipeline up to (but not including) file write
    metadata, text, stripped_sections, filename = prepare(epub_path)

    # Display results
    print_header("Generated filename:")
    print("  " + filename)

    print_header("Metadata:")
    print_metadata_table(metadata)

    print_header("Chapters found: {}".format(len(chapters)))
    for ch in chapters:
        print("  - " + ch.title)

    print_header("Stripped content ({} sections removed):".format(len(stripped_sections)))
    for section in stripped_sections:
        print_red("  [-] " + section.reason + ": " + section.preview)

    # Prompt
    choice = prompt("[A]ccept / [E]dit filename / [S]kip")

    if choice == 'a':
        write_output(output_dir / filename, text)
    elif choice == 'e':
        new_filename = prompt_filename(filename)
        write_output(output_dir / new_filename, text)
    elif choice == 's':
        print("Skipped.")
```

### What "Edit filename" does

Opens a Click `prompt()` pre-filled with the generated filename. The user can modify any part of it. The tool re-validates the filename format after editing (warns if it does not match the expected pattern, but allows it).

### Color output

- Use Click's `click.style()` for coloring.
- Red: stripped/removed content
- Green: kept content (in diff view)
- Yellow: warnings (missing metadata, heuristic uncertainty)
- Bold: section headers

### Batch review

In batch review mode, each file gets its own interactive prompt. The user can also choose `[Q]uit` to stop processing remaining files.

---

## 6. Stripping Heuristics (`stripper.py`)

### Architecture

The stripper operates on the full extracted text (after HTML-to-text conversion). It returns both the cleaned text and a list of what was stripped (for review mode).

```python
@dataclass
class StrippedSection:
    reason: str       # e.g. "copyright_page", "page_number", "divider"
    content: str      # The actual text that was removed
    line_range: tuple  # (start_line, end_line) in the original text

def strip_content(text: str) -> tuple[str, list[StrippedSection]]:
    """Apply all heuristics. Return (cleaned_text, stripped_sections)."""
```

### Heuristic catalog

| ID | Pattern | Detection | Scope |
|----|---------|-----------|-------|
| `copyright_page` | Copyright notices | Lines containing 2+ of: "Copyright", "All rights reserved", "ISBN", "Published by", "Library of Congress", "Printed in" | Contiguous block (paragraph) |
| `page_numbers` | Standalone numeric lines | Line matches `^\s*\d{1,4}\s*$` or `^\s*-\s*\d+\s*-\s*$` | Single line |
| `dividers` | Decorative separators | Line matches `^\s*[-*=]{3,}\s*$` or `^\s*\*\s+\*\s+\*\s*$` | Single line |
| `toc_duplicate` | Table of contents reproduced as text | Sequence of short lines (< 40 chars) where >60% match chapter titles | Contiguous block |
| `front_matter` | Epub-typed front matter | Spine items with `linear="no"` or epub type `frontmatter`, `titlepage`, `dedication` | Entire spine item |
| `back_matter` | Epub-typed back matter | Spine items with epub type `backmatter`, `index`, `colophon` | Entire spine item |
| `repeated_headers` | Running headers/footers | Short lines (< 30 chars) that appear identically at 3+ chapter boundaries | Single line |

### Design principles

- **Conservative by default.** The stripping should never remove actual story content. It is better to leave a stray page number than to eat a paragraph.
- **Each heuristic is an independent function.** They can be enabled/disabled individually in the future.
- **Stripping happens in a defined order:**
  1. Front/back matter (epub-level, before HTML-to-text)
  2. Copyright pages (paragraph-level)
  3. TOC duplicates (block-level)
  4. Page numbers (line-level)
  5. Dividers (line-level)
  6. Repeated headers (line-level)
- **Order matters** because removing front matter first prevents those sections from triggering false positives in later heuristics.

### Front/back matter detection (epub-level, in `converter.py`)

This heuristic is special: it operates at the epub parsing level, not on extracted text. Spine items that are typed as front or back matter are excluded before text extraction even happens.

```python
SKIP_EPUB_TYPES = {
    'frontmatter', 'titlepage', 'colophon', 'index',
    'toc', 'loi', 'lot',  # list of illustrations, list of tables
}

def should_skip_spine_item(item, book) -> bool:
    """Check epub:type attribute and linear='no' flag."""
```

The result is still recorded as a `StrippedSection` so review mode can show what was skipped.

---

## 7. Metadata Extraction (`formatter.py`)

### Fields and sources

| Field | Primary source | Fallback |
|-------|---------------|----------|
| Author | `dc:creator` | "Unknown" |
| Title | `dc:title` | Epub filename stem |
| Series | `calibre:series` metadata | None (omit from filename) |
| Series index | `calibre:series_index` metadata | None (omit from filename) |
| Genre | `dc:subject` (first entry) | None (omit from filename) |
| Word count | Calculated from extracted text | Always present |

### Extraction pseudocode

```python
def extract_metadata(book) -> dict:
    author = get_first(book.get_metadata('DC', 'creator')) or "Unknown"
    title = get_first(book.get_metadata('DC', 'title')) or stem(epub_path)

    # Calibre series metadata uses OPF namespace
    series = get_calibre_meta(book, 'calibre:series')
    series_index = get_calibre_meta(book, 'calibre:series_index')

    # Genre from subject
    subjects = book.get_metadata('DC', 'subject')
    genre = subjects[0][0] if subjects else None

    return {
        'author': clean_name(author),
        'title': clean_title(title),
        'series': series,
        'series_index': series_index,
        'genre': genre,
    }
```

### Calibre metadata access

Calibre stores series info as OPF `<meta>` elements:
```xml
<meta name="calibre:series" content="The Expanse"/>
<meta name="calibre:series_index" content="1"/>
```

ebooklib exposes these via `book.get_metadata('OPF', 'meta')`. We need to filter by `name` attribute.

```python
def get_calibre_meta(book, name: str) -> str | None:
    for meta in book.get_metadata('OPF', 'meta'):
        attrs = meta[1]  # ebooklib returns (value, attributes)
        if attrs.get('name') == name:
            return attrs.get('content')
    return None
```

### Filename generation

```python
def format_filename(metadata: dict, word_count: int) -> str:
    parts = []

    # Series: "(Series N) " or "(Series) " if no index
    if metadata['series']:
        if metadata['series_index']:
            idx = metadata['series_index']
            # Format index: "1.0" -> "1", "2.5" -> "2.5"
            if idx == int(float(idx)):
                idx = str(int(float(idx)))
            parts.append("({} {}) ".format(metadata['series'], idx))
        else:
            parts.append("({}) ".format(metadata['series']))

    # Genre: "[Genre] "
    if metadata['genre']:
        parts.append("[{}] ".format(metadata['genre']))

    # Author - Title
    parts.append("{} - {}".format(metadata['author'], metadata['title']))

    # Word count
    parts.append(" ({})".format(word_count))

    # Extension
    parts.append(".txt")

    filename = "".join(parts)
    return sanitize_filename(filename)
```

### Filename sanitization

Replace characters that are illegal on FAT32 (SD card filesystem):
```python
ILLEGAL_CHARS = r'<>:"/\|?*'

def sanitize_filename(name: str) -> str:
    for ch in ILLEGAL_CHARS:
        name = name.replace(ch, '_')
    # Collapse multiple spaces/underscores
    name = re.sub(r'[_ ]{2,}', ' ', name)
    return name.strip()
```

### Example outputs

| Epub metadata | Output filename |
|--------------|----------------|
| Author: James S.A. Corey, Title: Leviathan Wakes, Series: The Expanse #1, Genre: Science Fiction | `(The Expanse 1) [Science Fiction] James S.A. Corey - Leviathan Wakes (186423).txt` |
| Author: Patrick Rothfuss, Title: The Name of the Wind, Series: The Kingkiller Chronicle #1, No genre | `(The Kingkiller Chronicle 1) Patrick Rothfuss - The Name of the Wind (248532).txt` |
| Author: Ursula K. Le Guin, Title: The Left Hand of Darkness, No series, No genre | `Ursula K. Le Guin - The Left Hand of Darkness (72610).txt` |
| No author, Title: Mystery Book, No series, Genre: Mystery | `[Mystery] Unknown - Mystery Book (45200).txt` |

---

## 8. Core Extraction Logic (`converter.py`)

### Spine ordering

Epubs define a "spine" -- the reading order of content documents. This is the authoritative sequence for chapter ordering.

```python
def extract_chapters(book) -> list[dict]:
    """Extract chapters in spine order, mapping to TOC for titles."""

    # Build TOC lookup: href -> title
    toc_map = build_toc_map(book.toc)

    chapters = []
    for item_id, linear in book.spine:
        item = book.get_item_with_id(item_id)
        if item is None:
            continue
        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue

        href = item.get_name()
        title = toc_map.get(href, "")
        html = item.get_content().decode('utf-8')

        # Check if this spine item should be skipped (front/back matter)
        if should_skip_spine_item(item, book):
            stripped_sections.append(...)
            continue

        chapters.append({
            'title': title,
            'html': html,
            'href': href,
        })

    return chapters
```

### TOC mapping

The epub TOC can be nested (parts containing chapters). We flatten it to a simple `href -> title` map.

```python
def build_toc_map(toc) -> dict[str, str]:
    """Flatten nested TOC into { href: title } map."""
    result = {}
    for entry in toc:
        if isinstance(entry, tuple):
            # Nested: (Section, [children])
            section, children = entry
            result[section.href] = section.title
            result.update(build_toc_map(children))
        else:
            # Leaf: Link object
            result[entry.href] = entry.title
    return result
```

### HTML-to-text conversion

```python
def html_to_text(html: str) -> str:
    """Convert HTML to plain text preserving paragraph structure."""
    soup = BeautifulSoup(html, 'lxml')

    # Remove script, style, nav elements
    for tag in soup.find_all(['script', 'style', 'nav']):
        tag.decompose()

    # Get text with paragraph separation
    # Strategy: replace block-level elements with double newlines,
    # then collapse whitespace within paragraphs

    blocks = []
    for element in soup.find_all(['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote']):
        text = element.get_text(separator=' ', strip=True)
        if text:
            # Normalize internal whitespace
            text = re.sub(r'\s+', ' ', text)
            blocks.append(text)

    # If no block elements found, fall back to raw text extraction
    if not blocks:
        text = soup.get_text(separator=' ', strip=True)
        text = re.sub(r'\s+', ' ', text)
        return text

    return "\n\n".join(blocks)
```

### Chapter marker insertion

Chapter markers go at the beginning of each chapter's text block. The marker format is:

```
---CHAPTER: Chapter 1 - The Beginning---
```

This format is chosen so that:
- It is visually distinct in the raw .txt file
- It can be parsed by the firmware in Phase 2 (chapter navigation) using a simple `startswith("---CHAPTER:")` check
- It does not interfere with RSVP display (the reader can skip lines starting with `---CHAPTER:`)

If the TOC provides no title for a spine item, no chapter marker is inserted (it is likely a continuation of the previous chapter or a non-chapter section like an image page).

### Edge cases

- **Multi-file chapters:** Some epubs split a single chapter across multiple spine items. When consecutive spine items map to the same TOC entry (or have no TOC entry), they are concatenated under a single chapter marker.
- **Fragment hrefs:** TOC entries often include fragment identifiers (`chapter1.xhtml#section2`). The lookup must strip the fragment before matching.
- **Encoding:** ebooklib returns bytes. Always decode as UTF-8 with `errors='replace'` to handle broken epubs.
- **Empty chapters:** Spine items that produce no text after conversion are silently dropped.

---

## 9. CLI Entry Point (`cli.py`)

### Interface

```python
@click.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--output-dir', '-o', type=click.Path(), default=None,
              help='Output directory. Defaults to same directory as input.')
@click.option('--review', is_flag=True, default=False,
              help='Interactive review mode.')
@click.option('--overwrite', is_flag=True, default=False,
              help='Overwrite existing output files.')
@click.option('--version', is_flag=True, callback=print_version, expose_value=False,
              is_eager=True)
def main(input_path, output_dir, review, overwrite):
    """Convert .epub files to picoReader .txt format."""
```

### Single file vs. directory

```python
input_path = Path(input_path)
if input_path.is_dir():
    epubs = sorted(input_path.glob('*.epub'))
    if not epubs:
        click.echo("No .epub files found in {}".format(input_path))
        return
    for i, epub in enumerate(epubs, 1):
        click.echo("[{}/{}] {}".format(i, len(epubs), epub.name))
        process_one(epub, output_dir, review, overwrite)
else:
    process_one(input_path, output_dir, review, overwrite)
```

### Error handling

- Malformed epub (ebooklib raises exception): catch, print error with filename, continue in batch mode
- Missing metadata: proceed with fallbacks, print yellow warning
- Write permission error: catch, print error, continue in batch mode
- Keyboard interrupt in review mode: graceful exit with count of processed files

### Output

Auto mode output per file:
```
  -> (The Expanse 1) [Science Fiction] James S.A. Corey - Leviathan Wakes (186423).txt
     Chapters: 53 | Words: 186,423 | Stripped: 12 sections
```

Batch summary:
```
Done. 12 converted, 2 skipped (exist), 1 failed.
```

---

## 10. Unit Tests

### Directory structure

```
tests/
  unit/
    test_epub2pico/
      __init__.py
      test_formatter.py
      test_stripper.py
      test_converter.py
      conftest.py            # Shared fixtures (mock epub objects, sample HTML)
```

### Test fixtures (`conftest.py`)

- **`mock_epub_book`**: Factory fixture that creates a mock ebooklib Book object with configurable metadata, spine, and TOC. Does not require actual .epub files on disk.
- **`sample_html_chapter`**: Returns a realistic HTML string from a typical epub chapter.
- **`sample_copyright_html`**: Returns HTML for a typical copyright page.
- **`sample_toc`**: Returns a nested TOC structure for testing flattening.

### test_formatter.py

| Test | Input | Expected |
|------|-------|----------|
| Full metadata | author, title, series #1, genre | `(Series 1) [Genre] Author - Title (N).txt` |
| No series | author, title, genre | `[Genre] Author - Title (N).txt` |
| No genre | author, title, series #3 | `(Series 3) Author - Title (N).txt` |
| No series, no genre | author, title | `Author - Title (N).txt` |
| No author | title only | `Unknown - Title (N).txt` |
| Series without index | author, title, series (no number) | `(Series) Author - Title (N).txt` |
| Fractional series index | series_index = "2.5" | `(Series 2.5) Author - Title (N).txt` |
| Integer series index as float | series_index = "1.0" | `(Series 1) Author - Title (N).txt` |
| Illegal FAT32 characters | title with `:` and `?` | Characters replaced with `_` |
| Calibre metadata extraction | OPF meta tags with calibre:series | Correct series/index returned |

### test_stripper.py

| Test | Input | Expected |
|------|-------|----------|
| Copyright block detected | Text block with "Copyright 2023... All rights reserved... ISBN..." | Block removed, recorded as `copyright_page` |
| Standalone page numbers | "42" on its own line | Line removed |
| Formatted page numbers | "- 42 -" on its own line | Line removed |
| Non-page-number numbers | "There were 42 of them" | Line preserved |
| Divider dashes | "---" on its own line | Line removed |
| Divider asterisks | "* * *" on its own line | Line removed |
| Actual content with dashes | "She paused---then continued" | Line preserved |
| TOC duplicate detection | Sequence of lines matching chapter titles | Block removed |
| Repeated headers | Same short line at 4+ chapter boundaries | Lines removed |
| Conservative behavior | Ambiguous content (could be junk or real) | Content preserved |

### test_converter.py

| Test | Input | Expected |
|------|-------|----------|
| Simple HTML paragraphs | `<p>Hello</p><p>World</p>` | `"Hello\n\nWorld"` |
| Nested tags | `<p>The <em>quick</em> fox</p>` | `"The quick fox"` |
| Script/style removal | HTML with `<script>` and `<style>` tags | Tags and content removed |
| Whitespace normalization | `<p>  too   many   spaces  </p>` | `"too many spaces"` |
| TOC map flattening | Nested TOC with parts and chapters | Flat `{ href: title }` dict |
| Fragment href handling | TOC href `chapter1.xhtml#sec2` | Matches spine item `chapter1.xhtml` |
| Word count accuracy | Known text | Exact word count |
| Empty spine item | Spine item with no text content | Silently dropped |
| Chapter marker format | Chapter with title "The Beginning" | `"---CHAPTER: The Beginning---"` as first line |

---

## 11. Key Decisions Summary

| Decision | Rationale |
|----------|-----------|
| Completely independent of firmware | Different runtime (CPython vs CircuitPython), different purpose, different dependencies. Coupling them gains nothing. |
| Click for CLI | Simple, well-known, no framework magic. Good enough for a tool with 3 flags. |
| ebooklib for epub parsing | Standard Python epub library. Handles epub2/epub3, spine, TOC, metadata. |
| BeautifulSoup + lxml for HTML | Epub HTML is frequently malformed. BS4 with lxml is the most forgiving parser available. |
| Conservative stripping by default | Missing content is worse than extra junk. The RSVP reader can skip a stray page number in a second. A missing paragraph is gone forever. |
| Review mode as opt-in | Most users will use auto mode. Review mode is for when you care about quality on a specific book or want to understand what the tool did. |
| Chapter markers in output | Enables Phase 2 chapter navigation on the firmware side. The `---CHAPTER:` prefix is easy to detect and skip during RSVP display. |
| FAT32 filename sanitization | The output files end up on an SD card formatted as FAT32. Colons, question marks, etc. will break. |
| pipx-installable | Users should not need to manage virtualenvs. `pipx install` gives them a global command in one step. |

---

## Task Order

1. Create `tools/epub2pico/` directory structure and `pyproject.toml`
2. Implement `formatter.py` — metadata extraction and filename generation
3. Write `test_formatter.py` — all filename generation cases, Calibre metadata parsing
4. Implement `stripper.py` — all heuristic functions, `StrippedSection` dataclass
5. Write `test_stripper.py` — all heuristic detection cases
6. Implement `converter.py` — spine reading, TOC mapping, HTML-to-text
7. Write `test_converter.py` — HTML conversion, TOC flattening, chapter markers
8. Implement `cli.py` — auto mode, review mode, batch handling, error handling
9. End-to-end manual test with a real .epub file
10. Verify `pipx install ./tools/epub2pico` works and `epub2pico --help` runs

---

## What Phase 4 Does NOT Include

- Firmware changes to read chapter markers (Phase 2 — chapter navigation)
- DRM-protected epub handling (out of scope entirely; DRM removal is a legal gray area)
- PDF or MOBI conversion (epub only)
- GUI or TUI beyond the Click prompts in review mode
- Automatic download or library management
- Any interaction with the Pico or its filesystem (the user copies files to the SD card themselves)

Phase 4 produces a standalone tool. The firmware consumes its output as plain `.txt` files, same as always.

"""Click CLI entry point for epub2pico."""

import sys
from pathlib import Path

import click

from . import __version__
from .converter import read_epub, extract_chapters, chapters_to_text, count_words
from .formatter import extract_metadata, format_filename
from .stripper import strip_content


def print_version(ctx, param, value):
    """Print version and exit."""
    if not value or ctx.resilient_parsing:
        return
    click.echo("epub2pico {}".format(__version__))
    ctx.exit()


@click.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--output-dir', '-o', type=click.Path(), default=None,
              help='Output directory. Defaults to same directory as input.')
@click.option('--review', is_flag=True, default=False,
              help='Interactive review mode.')
@click.option('--overwrite', is_flag=True, default=False,
              help='Overwrite existing output files.')
@click.option('--version', is_flag=True, callback=print_version,
              expose_value=False, is_eager=True,
              help='Show version and exit.')
def main(input_path, output_dir, review, overwrite):
    """Convert .epub files to picoReader .txt format."""
    input_path = Path(input_path)

    if input_path.is_dir():
        epubs = sorted(input_path.glob('*.epub'))
        if not epubs:
            click.echo("No .epub files found in {}".format(input_path))
            sys.exit(1)

        converted = 0
        skipped = 0
        failed = 0

        for i, epub_path in enumerate(epubs, 1):
            click.echo("[{}/{}] {}".format(i, len(epubs), epub_path.name))
            try:
                result = process_one(epub_path, output_dir, review, overwrite)
                if result == 'converted':
                    converted += 1
                elif result == 'skipped':
                    skipped += 1
                elif result == 'quit':
                    break
            except KeyboardInterrupt:
                click.echo("\nInterrupted. {} converted so far.".format(converted))
                sys.exit(1)
            except Exception as e:
                click.echo(click.style(
                    "  ERROR: {}".format(str(e)), fg='red'
                ))
                failed += 1

        # Summary
        parts = []
        parts.append("{} converted".format(converted))
        if skipped:
            parts.append("{} skipped (exist)".format(skipped))
        if failed:
            parts.append("{} failed".format(failed))
        click.echo("\nDone. {}.".format(", ".join(parts)))
    else:
        if not input_path.suffix.lower() == '.epub':
            click.echo("Error: input file must be an .epub file.")
            sys.exit(1)
        try:
            process_one(input_path, output_dir, review, overwrite)
        except Exception as e:
            click.echo(click.style("ERROR: {}".format(str(e)), fg='red'))
            sys.exit(1)


def process_one(epub_path, output_dir, review, overwrite):
    """Process a single epub file. Returns 'converted', 'skipped', or 'quit'."""
    # Determine output directory
    if output_dir:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = epub_path.parent

    # Parse epub
    book = read_epub(epub_path)

    # Extract metadata
    fallback_title = epub_path.stem
    metadata = extract_metadata(book, fallback_title=fallback_title)

    # Warn about missing metadata
    if metadata['author'] == 'Unknown':
        click.echo(click.style("  WARN: No author metadata found", fg='yellow'))
    if not metadata['series']:
        pass  # Series is optional, no warning needed

    # Extract chapters
    chapters, epub_skipped = extract_chapters(book)

    if not chapters:
        click.echo(click.style("  WARN: No content chapters found", fg='yellow'))
        return 'skipped'

    # Convert to text
    text = chapters_to_text(chapters)

    # Collect chapter titles for stripping heuristics
    chapter_titles = [ch['title'] for ch in chapters if ch.get('title')]

    # Strip junk content
    text, stripped_sections = strip_content(text, chapter_titles=chapter_titles)

    # Combine epub-level and text-level stripped sections for reporting
    all_stripped = epub_skipped + stripped_sections

    # Count words
    word_count = count_words(text)

    # Generate filename
    filename = format_filename(metadata, word_count)
    output_path = out_dir / filename

    if review:
        return _review_mode(
            metadata, chapters, text, all_stripped, filename,
            output_path, word_count, overwrite
        )
    else:
        return _auto_mode(
            text, filename, output_path, chapters, all_stripped,
            word_count, overwrite
        )


def _auto_mode(text, filename, output_path, chapters, stripped, word_count, overwrite):
    """Auto mode: write output, print summary."""
    # Check for existing file
    if output_path.exists() and not overwrite:
        click.echo(click.style(
            "  SKIP: output already exists: {}".format(filename), fg='yellow'
        ))
        return 'skipped'

    # Write output
    output_path.write_text(text, encoding='utf-8')

    # Print summary
    click.echo("  -> {}".format(filename))
    click.echo("     Chapters: {} | Words: {:,} | Stripped: {} sections".format(
        len(chapters), word_count, len(stripped)
    ))

    return 'converted'


def _review_mode(metadata, chapters, text, stripped, filename,
                 output_path, word_count, overwrite):
    """Review mode: show details, prompt for action."""
    # Display filename
    click.echo(click.style("\n  Generated filename:", bold=True))
    click.echo("    {}".format(filename))

    # Display metadata
    click.echo(click.style("\n  Metadata:", bold=True))
    for key, value in metadata.items():
        click.echo("    {}: {}".format(key, value or "(none)"))

    # Display chapters
    click.echo(click.style(
        "\n  Chapters found: {}".format(len(chapters)), bold=True
    ))
    for ch in chapters:
        title = ch.get('title') or "(untitled)"
        click.echo("    - {}".format(title))

    # Display stripped content
    if stripped:
        click.echo(click.style(
            "\n  Stripped content ({} sections removed):".format(len(stripped)),
            bold=True
        ))
        for section in stripped:
            preview = section.content[:80].replace('\n', ' ')
            if len(section.content) > 80:
                preview += "..."
            click.echo(click.style(
                "    [-] {}: {}".format(section.reason, preview), fg='red'
            ))
    else:
        click.echo(click.style("\n  No content stripped.", bold=True))

    click.echo("\n  Words: {:,}".format(word_count))

    # Prompt
    while True:
        choice = click.prompt(
            "\n  [A]ccept / [E]dit filename / [S]kip / [Q]uit",
            type=str, default='a'
        ).strip().lower()

        if choice == 'a':
            if output_path.exists() and not overwrite:
                click.echo(click.style(
                    "  SKIP: output already exists: {}".format(filename),
                    fg='yellow'
                ))
                return 'skipped'
            output_path.write_text(text, encoding='utf-8')
            click.echo(click.style("  Written: {}".format(filename), fg='green'))
            return 'converted'

        elif choice == 'e':
            new_filename = click.prompt("  Filename", default=filename)
            new_path = output_path.parent / new_filename
            if new_path.exists() and not overwrite:
                click.echo(click.style(
                    "  SKIP: output already exists: {}".format(new_filename),
                    fg='yellow'
                ))
                return 'skipped'
            new_path.write_text(text, encoding='utf-8')
            click.echo(click.style(
                "  Written: {}".format(new_filename), fg='green'
            ))
            return 'converted'

        elif choice == 's':
            click.echo("  Skipped.")
            return 'skipped'

        elif choice == 'q':
            click.echo("  Quitting.")
            return 'quit'

        else:
            click.echo("  Invalid choice. Please enter A, E, S, or Q.")

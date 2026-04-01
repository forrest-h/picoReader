def parse_book_filename(filename):
    """Parse '(Series) [Genre] Author - Title (wordcount).txt' into components.

    Returns (title, author, series, wordcount, genre) tuple.
    Missing genre defaults to 'Uncategorized'.
    """
    try:
        name = filename.rsplit('.', 1)[0]
        parts = name.split(' - ', 1)
        if len(parts) == 2:
            author_part, title_part = parts
            # Extract optional (Series) prefix
            if author_part.startswith('('):
                close = author_part.find(')')
                series = author_part[1:close]
                author_part = author_part[close+1:].strip()
            else:
                series = ''
            # Extract optional [Genre] tag
            genre = ''
            if '[' in author_part:
                bracket_open = author_part.index('[')
                bracket_close = author_part.index(']', bracket_open)
                genre = author_part[bracket_open + 1:bracket_close].strip()
                author_part = author_part[bracket_close + 1:].strip()
            author = author_part.strip()
            # Extract title and wordcount
            paren = title_part.rfind('(')
            if paren != -1:
                title = title_part[:paren].strip()
                wordcount = int(title_part[paren+1:title_part.rfind(')')])
            else:
                title = title_part.strip()
                wordcount = 10000
        else:
            title, author, series, wordcount, genre = name, '', '', 10000, ''
    except (IndexError, ValueError):
        title, author, series, wordcount, genre = filename, '', '', 10000, ''
    if not genre:
        genre = 'Uncategorized'
    return title, author, series, wordcount, genre


def clean_word(word):
    return word.replace('\u201c', '"').replace('\u201d', '"').replace('\u2018', "'").replace('\u2019', "'")


def load_reading_font(font_name):
    """Load a PCF font from fonts/ dir. Falls back to Toronto_14.pcf on error."""
    from adafruit_bitmap_font import bitmap_font
    try:
        return bitmap_font.load_font("fonts/{}".format(font_name))
    except OSError:
        return bitmap_font.load_font("fonts/Toronto_14.pcf")

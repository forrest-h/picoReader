def parse_book_filename(filename):
    """Parse '(Series) Author - Title (wordcount).txt' into components."""
    try:
        name = filename.rsplit('.', 1)[0]
        parts = name.split(' - ', 1)
        if len(parts) == 2:
            author_part, title_part = parts
            if author_part.startswith('('):
                close = author_part.find(')')
                series = author_part[1:close]
                author = author_part[close+1:].strip()
            else:
                series = ''
                author = author_part.strip()
            paren = title_part.rfind('(')
            if paren != -1:
                title = title_part[:paren].strip()
                wordcount = int(title_part[paren+1:title_part.rfind(')')])
            else:
                title = title_part.strip()
                wordcount = 10000
        else:
            title, author, series, wordcount = name, '', '', 10000
    except (IndexError, ValueError):
        title, author, series, wordcount = filename, '', '', 10000
    return title, author, series, wordcount


def clean_word(word):
    return word.replace('\u201c', '"').replace('\u201d', '"').replace('\u2018', "'").replace('\u2019', "'")

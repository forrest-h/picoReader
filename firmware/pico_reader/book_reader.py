class BookReader:
    CACHE_LINES = 3

    def __init__(self, books, book_metadata, book_lens):
        self.books = books
        self.book_metadata = book_metadata
        self.book_lens = book_lens
        self.book_id = 0
        self.book = books[0]
        self.book_len = book_lens[0]
        self.line_num = 0
        self.word_idx = 0
        self._cache = []
        self._cache_start = -1
        self.total_lines = 0
        self.chapters = []
        self.chapter_index = -1

    def _ensure_cached(self, line):
        if self._cache_start <= line < self._cache_start + len(self._cache):
            return
        start = max(0, line - 1)
        self._cache = []
        self._cache_start = start
        with open("/sd/books/{}".format(self.book), 'r') as f:
            for _ in range(start):
                if not f.readline():
                    return
            for _ in range(self.CACHE_LINES):
                text = f.readline()
                if not text:
                    break
                self._cache.append(text.strip().split())

    def _get_words(self, line):
        self._ensure_cached(line)
        idx = line - self._cache_start
        if 0 <= idx < len(self._cache):
            return self._cache[idx]
        return []

    def step_forward(self):
        """Return next word, or None at end of book."""
        while True:
            words = self._get_words(self.line_num)
            if words:
                if self.word_idx < len(words):
                    word = words[self.word_idx]
                    self.word_idx += 1
                    return word
                self.line_num += 1
                self.word_idx = 0
            else:
                # [] could be blank line (in cache) or past EOF (not in cache)
                idx = self.line_num - self._cache_start
                if not (0 <= idx < len(self._cache)):
                    return None  # Truly past EOF
                self.line_num += 1
                self.word_idx = 0

    def step_backward(self):
        """Return previous word, or None at start of book."""
        self.word_idx -= 1
        if self.word_idx < 0:
            if self.line_num <= 0:
                self.word_idx = 0
                return None
            self.line_num -= 1
            words = self._get_words(self.line_num)
            self.word_idx = max(0, len(words) - 1) if words else 0
        words = self._get_words(self.line_num)
        if words and 0 <= self.word_idx < len(words):
            return words[self.word_idx]
        return None

    def save_place(self):
        with open("saves/save_{}".format(self.book), 'w') as f:
            f.write("{}:{}".format(self.line_num, self.word_idx))

    def save_backup(self):
        with open("saves/save_prev_{}".format(self.book), 'w') as f:
            f.write("{}:{}".format(self.line_num, self.word_idx))

    def load_place(self):
        try:
            with open("saves/save_{}".format(self.book), 'r') as f:
                data = f.read().strip()
            if ':' in data:
                parts = data.split(':')
                self.line_num = int(parts[0])
                self.word_idx = int(parts[1])
            else:
                self.line_num = int(data)
                self.word_idx = 0
        except (OSError, ValueError):
            self.line_num = 0
            self.word_idx = 0
        self._cache_start = -1
        self._cache = []

    def build_chapter_index(self):
        """Scan book file for ---CHAPTER: title--- markers and count lines."""
        self.chapters = []
        try:
            with open("/sd/books/{}".format(self.book), 'r') as f:
                line_num = 0
                for line in f:
                    stripped = line.strip()
                    if stripped.startswith('---CHAPTER:') and stripped.endswith('---'):
                        title = stripped[11:-3].strip()
                        self.chapters.append((line_num, title))
                    line_num += 1
            self.total_lines = line_num
        except OSError:
            self.chapters = []
            self.total_lines = 0
        self._update_chapter_index()

    def _update_chapter_index(self):
        """Find which chapter the current line_num falls in."""
        self.chapter_index = -1
        for i, (ch_line, _) in enumerate(self.chapters):
            if self.line_num >= ch_line:
                self.chapter_index = i
            else:
                break

    def jump_to_chapter(self, direction):
        """Jump to previous (-1) or next (+1) chapter. Returns chapter title or None."""
        if not self.chapters:
            return None
        target = self.chapter_index + direction
        if target < 0 or target >= len(self.chapters):
            return None
        line_num, title = self.chapters[target]
        self.line_num = line_num + 1  # Skip the marker line itself
        self.word_idx = 0
        self._cache_start = -1
        self._cache = []
        self.chapter_index = target
        return title

    def select_book(self, book_id):
        self.book_id = book_id
        self.book = self.books[book_id]
        self.book_len = self.book_lens[book_id]
        self.load_place()
        self.build_chapter_index()

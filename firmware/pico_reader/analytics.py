import time


class BookStats:
    """Per-book persistent stats (words read, sessions count)."""

    def __init__(self, book_filename):
        self._path = "saves/stats_{}".format(book_filename)
        self.words_read = 0
        self.sessions = 0
        self._load()

    def _load(self):
        try:
            with open(self._path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if ':' in line:
                        key, val = line.split(':', 1)
                        if key == 'words_read':
                            self.words_read = int(val)
                        elif key == 'sessions':
                            self.sessions = int(val)
        except (OSError, ValueError):
            pass

    def save(self):
        with open(self._path, 'w') as f:
            f.write("words_read:{}\n".format(self.words_read))
            f.write("sessions:{}\n".format(self.sessions))

    def increment_word(self):
        self.words_read += 1

    def start_session(self):
        self.sessions += 1
        self.save()

    def words_remaining(self, total_wordcount):
        return max(0, total_wordcount - self.words_read)

    def estimated_minutes(self, current_wpm, total_wordcount):
        remaining = self.words_remaining(total_wordcount)
        if current_wpm <= 0:
            return 0
        return remaining // current_wpm

    def completion_pct(self, total_wordcount):
        if total_wordcount <= 0:
            return 0
        return min(100, self.words_read * 100 // total_wordcount)


class SessionStats:
    """Per-session in-memory stats (rolling WPM, reading time)."""

    def __init__(self):
        self.words = 0
        self.start_time = time.monotonic()
        self._wpm_samples = []
        self._max_samples = 60

    def record_word(self, wpm):
        self.words += 1
        self._wpm_samples.append(wpm)
        if len(self._wpm_samples) > self._max_samples:
            self._wpm_samples.pop(0)

    def average_wpm(self):
        if not self._wpm_samples:
            return 0
        return sum(self._wpm_samples) // len(self._wpm_samples)

    def reading_time_minutes(self):
        return int((time.monotonic() - self.start_time) // 60)

import pytest
from pico_reader.menu import MenuNode, MenuState, build_menu_tree
from pico_reader.utils import parse_book_filename


SAMPLE_BOOKS = [
    "(Earthsea 1) [Fantasy] Ursula K Le Guin - A Wizard Of Earthsea (1835).txt",
    "[Science Fiction] Andy Weir - The Martian (3500).txt",
    "Terry Pratchett - Guards Guards (9200).txt",
    "(Red Rising 1) [Science Fiction] Pierce Brown - Red Rising (5000).txt",
]


@pytest.fixture
def sample_metadata():
    return [parse_book_filename(b) for b in SAMPLE_BOOKS]


@pytest.fixture
def menu_tree(sample_metadata):
    return build_menu_tree(SAMPLE_BOOKS, sample_metadata, [])


@pytest.fixture
def menu_state(menu_tree):
    return MenuState(menu_tree)


# --- Tree building tests ---

class TestBuildMenuTree:
    def test_root_has_six_children(self, menu_tree):
        assert len(menu_tree.children) == 6
        labels = [c.label for c in menu_tree.children]
        assert labels == ["All Books", "Recently Read", "Authors", "Series", "Genres", "Settings"]

    def test_all_books_sorted_by_title(self, menu_tree, sample_metadata):
        all_books = menu_tree.children[0]
        titles = [n.label for n in all_books.children]
        assert titles == sorted(titles, key=lambda s: s.lower())
        assert len(titles) == 4

    def test_authors_grouped_correctly(self, menu_tree):
        authors_node = menu_tree.children[2]
        author_names = [n.label for n in authors_node.children]
        assert "Andy Weir" in author_names
        assert "Pierce Brown" in author_names
        assert "Terry Pratchett" in author_names
        assert "Ursula K Le Guin" in author_names
        # Each author has exactly one book in our sample
        for author_node in authors_node.children:
            assert len(author_node.children) >= 1
            for book_node in author_node.children:
                assert book_node.book_id is not None

    def test_series_sorted_by_filename(self, menu_tree):
        series_node = menu_tree.children[3]
        series_names = [n.label for n in series_node.children]
        assert "Earthsea 1" in series_names
        assert "Red Rising 1" in series_names
        # Terry Pratchett and Andy Weir have no series, should not appear
        assert len(series_names) == 2

    def test_genres_from_metadata(self, menu_tree):
        genres_node = menu_tree.children[4]
        genre_names = [n.label for n in genres_node.children]
        assert "Fantasy" in genre_names
        assert "Science Fiction" in genre_names
        assert "Uncategorized" in genre_names

    def test_uncategorized_genre_for_missing(self, menu_tree):
        genres_node = menu_tree.children[4]
        uncat = None
        for g in genres_node.children:
            if g.label == "Uncategorized":
                uncat = g
                break
        assert uncat is not None
        # Terry Pratchett has no genre tag
        titles = [n.label for n in uncat.children]
        assert "Guards Guards" in titles

    def test_recently_read_preserves_order(self, sample_metadata):
        recent_files = [SAMPLE_BOOKS[2], SAMPLE_BOOKS[0]]  # Guards Guards, then Wizard
        root = build_menu_tree(SAMPLE_BOOKS, sample_metadata, recent_files)
        recent_node = root.children[1]
        assert len(recent_node.children) == 2
        assert recent_node.children[0].label == "Guards Guards"
        assert recent_node.children[1].label == "A Wizard Of Earthsea"

    def test_recently_read_skips_missing_files(self, sample_metadata):
        recent_files = ["nonexistent.txt", SAMPLE_BOOKS[0]]
        root = build_menu_tree(SAMPLE_BOOKS, sample_metadata, recent_files)
        recent_node = root.children[1]
        assert len(recent_node.children) == 1
        assert recent_node.children[0].label == "A Wizard Of Earthsea"

    def test_empty_series_when_no_books_have_series(self):
        books = ["Author - Title (100).txt"]
        meta = [parse_book_filename(b) for b in books]
        root = build_menu_tree(books, meta, [])
        series_node = root.children[3]
        assert len(series_node.children) == 0

    def test_settings_is_empty_stub(self, menu_tree):
        settings_node = menu_tree.children[5]
        assert settings_node.children == []


# --- Navigation tests ---

class TestMenuState:
    def test_scroll_wraps_forward(self, menu_state):
        # Root has 6 children
        assert menu_state.cursor == 0
        for i in range(6):
            menu_state.scroll(1)
        assert menu_state.cursor == 0  # Wrapped around

    def test_scroll_wraps_backward(self, menu_state):
        assert menu_state.cursor == 0
        menu_state.scroll(-1)
        assert menu_state.cursor == 5  # Wrapped to last item

    def test_select_category_drills_in(self, menu_state):
        # Select "All Books" (first child)
        menu_state.cursor = 0
        result = menu_state.select()
        assert result is None  # Drilled into category, not a book
        assert menu_state.depth == 1
        assert menu_state.current_node.label == "All Books"

    def test_select_book_returns_id(self, menu_state):
        # Drill into All Books, then select a book
        menu_state.select()  # Enter "All Books"
        result = menu_state.select()  # Select first book
        assert result is not None  # Should be a book_id

    def test_back_pops_level(self, menu_state):
        menu_state.select()  # Drill into "All Books"
        assert menu_state.depth == 1
        result = menu_state.back()
        assert result is True
        assert menu_state.depth == 0

    def test_back_at_root_returns_false(self, menu_state):
        result = menu_state.back()
        assert result is False
        assert menu_state.depth == 0

    def test_breadcrumb_at_root(self, menu_state):
        assert menu_state.breadcrumb() == "picoReader"

    def test_breadcrumb_two_levels_deep(self, menu_state):
        # Drill into Authors
        menu_state.cursor = 2  # Authors
        menu_state.select()
        bc = menu_state.breadcrumb()
        assert bc == "Authors"
        # Drill into first author
        menu_state.select()
        bc = menu_state.breadcrumb()
        assert " > " in bc

    def test_breadcrumb_truncation(self):
        # Build deep tree with long names
        child2 = MenuNode("VeryLongCategoryName", children=[
            MenuNode("Leaf", book_id=0)
        ])
        child1 = MenuNode("AnotherLongCategory", children=[child2])
        root = MenuNode("picoReader", children=[child1])
        ms = MenuState(root)
        ms.select()  # into AnotherLongCategory
        ms.select()  # into VeryLongCategoryName
        bc = ms.breadcrumb()
        assert len(bc) <= 22

    def test_refresh_recent_updates_children(self, menu_state, sample_metadata):
        recent_files = [SAMPLE_BOOKS[1]]  # The Martian
        menu_state.refresh_recent(SAMPLE_BOOKS, sample_metadata, recent_files)
        recent_node = menu_state.root.children[1]
        assert len(recent_node.children) == 1
        assert recent_node.children[0].label == "The Martian"

    def test_select_on_empty_category(self, menu_state):
        # Navigate to Settings (empty stub)
        menu_state.cursor = 5  # Settings
        result = menu_state.select()
        # Drills into Settings
        assert result is None
        assert menu_state.current_node.label == "Settings"
        # Selecting inside empty category
        result = menu_state.select()
        assert result is None

    def test_scroll_on_empty_category(self, menu_state):
        menu_state.cursor = 5  # Settings
        menu_state.select()  # Drill into empty Settings
        # Scroll should be a no-op
        menu_state.scroll(1)
        assert menu_state.cursor == 0
        menu_state.scroll(-1)
        assert menu_state.cursor == 0

    def test_visible_items(self, menu_state):
        items, cursor = menu_state.visible_items()
        assert items == menu_state.root.children
        assert cursor == 0

    def test_back_resets_cursor(self, menu_state):
        menu_state.cursor = 2
        menu_state.select()  # Drill into Authors
        menu_state.cursor = 1  # Move cursor
        menu_state.back()
        assert menu_state.cursor == 0  # Reset on back

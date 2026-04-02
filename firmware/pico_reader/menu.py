class MenuNode:
    """A single node in the menu tree."""
    def __init__(self, label, children=None, book_id=None, setting_key=None):
        self.label = label          # Display text
        self.children = children    # List[MenuNode] or None for leaves
        self.book_id = book_id      # int index into books[] or None for categories
        self.setting_key = setting_key  # str setting key for actionable settings leaves


class MenuState:
    """Tracks current position in the menu tree."""
    def __init__(self, root):
        self.root = root
        self.path = [root]
        self.cursor = 0

    @property
    def current_node(self):
        return self.path[-1]

    @property
    def current_items(self):
        return self.current_node.children

    @property
    def depth(self):
        return len(self.path) - 1

    def scroll(self, direction):
        """Scroll cursor by +1 or -1, wrapping around."""
        items = self.current_node.children
        if not items:
            return
        self.cursor = (self.cursor + direction) % len(items)

    def select(self):
        """Select current item.

        Returns:
            int book_id if a book leaf was selected
            str setting_key if a setting leaf was selected (prefixed with 'setting:')
            None if drilled into a category
        """
        items = self.current_node.children
        if not items:
            return None
        selected = items[self.cursor]
        if selected.book_id is not None:
            return selected.book_id
        if selected.setting_key is not None:
            return "setting:{}".format(selected.setting_key)
        if selected.children is not None:
            self.path.append(selected)
            self.cursor = 0
            return None
        return None

    def back(self):
        """Go back one level. Returns False if already at root."""
        if len(self.path) <= 1:
            return False
        self.path.pop()
        self.cursor = 0
        return True

    def breadcrumb(self):
        """Return breadcrumb string for title bar."""
        if len(self.path) <= 1:
            return self.root.label
        parts = [n.label for n in self.path[1:]]
        text = " > ".join(parts)
        if len(text) > 22:
            text = "..> " + parts[-1]
            if len(text) > 22:
                text = parts[-1][:20]
        return text

    def visible_items(self):
        """Return (items_list, cursor_index) for the display to render."""
        return (self.current_node.children, self.cursor)

    def refresh_recent(self, books, book_metadata, recent_filenames):
        """Rebuild the Recently Read node's children in-place."""
        recent_node = self.root.children[1]  # Index 1 = Recently Read
        filename_to_id = {}
        for i, fn in enumerate(books):
            filename_to_id[fn] = i
        recent_node.children = []
        for fn in recent_filenames:
            if fn in filename_to_id:
                bid = filename_to_id[fn]
                recent_node.children.append(MenuNode(book_metadata[bid][0], book_id=bid))


def build_menu_tree(books, book_metadata, recent_filenames):
    """Build the menu tree from book data. Returns root MenuNode.

    Args:
        books: list of filenames
        book_metadata: list of (title, author, series, wordcount, genre) tuples
        recent_filenames: list of filenames from recent_order.txt
    """
    # All Books -- sorted by title
    all_books_sorted = sorted(range(len(books)), key=lambda i: book_metadata[i][0].lower())
    all_books_node = MenuNode("All Books", children=[
        MenuNode(book_metadata[i][0], book_id=i) for i in all_books_sorted
    ])

    # Recently Read -- preserve order from recent_filenames
    filename_to_id = {}
    for i, fn in enumerate(books):
        filename_to_id[fn] = i
    recent_nodes = []
    for fn in recent_filenames:
        if fn in filename_to_id:
            bid = filename_to_id[fn]
            recent_nodes.append(MenuNode(book_metadata[bid][0], book_id=bid))
    recent_node = MenuNode("Recently Read", children=recent_nodes)

    # Authors -- group by author
    authors = {}
    for i, meta in enumerate(book_metadata):
        author = meta[1] if meta[1] else "Unknown"
        if author not in authors:
            authors[author] = []
        authors[author].append((i, meta[0]))
    author_nodes = []
    for author in sorted(authors.keys(), key=lambda s: s.lower()):
        book_nodes = [MenuNode(title, book_id=bid)
                      for bid, title in sorted(authors[author], key=lambda x: x[1].lower())]
        author_nodes.append(MenuNode(author, children=book_nodes))
    authors_node = MenuNode("Authors", children=author_nodes)

    # Series -- group by series name
    series_map = {}
    for i, meta in enumerate(book_metadata):
        if meta[2]:
            if meta[2] not in series_map:
                series_map[meta[2]] = []
            series_map[meta[2]].append((i, books[i]))
    series_nodes = []
    for series_name in sorted(series_map.keys(), key=lambda s: s.lower()):
        book_nodes = [MenuNode(book_metadata[bid][0], book_id=bid)
                      for bid, fn in sorted(series_map[series_name], key=lambda x: x[1])]
        series_nodes.append(MenuNode(series_name, children=book_nodes))
    series_node = MenuNode("Series", children=series_nodes)

    # Genres -- group by genre
    genres = {}
    for i, meta in enumerate(book_metadata):
        genre = meta[4] if len(meta) > 4 and meta[4] else "Uncategorized"
        if genre not in genres:
            genres[genre] = []
        genres[genre].append((i, meta[0]))
    genre_nodes = []
    for genre_name in sorted(genres.keys(), key=lambda s: s.lower()):
        book_nodes = [MenuNode(title, book_id=bid)
                      for bid, title in sorted(genres[genre_name], key=lambda x: x[1].lower())]
        genre_nodes.append(MenuNode(genre_name, children=book_nodes))
    genres_node = MenuNode("Genres", children=genre_nodes)

    # Settings
    settings_node = MenuNode("Settings", children=[
        MenuNode("Skin", setting_key="skin"),
        MenuNode("Color", setting_key="palette"),
        MenuNode("ORP Mode", setting_key="orp"),
        MenuNode("Animation", children=[
            MenuNode("Walker: off", setting_key="anim_walker"),
            MenuNode("Particles: off", setting_key="anim_particles"),
            MenuNode("Page %: off", setting_key="anim_page_turn"),
        ]),
        MenuNode("Font", setting_key="font"),
        MenuNode("Smart Pacing", setting_key="smart_pacing"),
        MenuNode("Brightness", setting_key="brightness"),
        MenuNode("Stats", setting_key="stats"),
        MenuNode("System Info", setting_key="games"),
    ])

    root = MenuNode("picoReader", children=[
        all_books_node,
        recent_node,
        authors_node,
        series_node,
        genres_node,
        settings_node,
    ])
    return root

from __future__ import annotations

from sqlit.domains.explorer.domain.tree_nodes import DatabaseNode, FolderNode, TableNode, ViewNode
from sqlit.domains.explorer.ui.mixins.tree_filter import TreeFilterMixin


class FakeFilterInput:
    def __init__(self) -> None:
        self.visible = False
        self.last_filter: tuple[str, int, int] | None = None

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False

    def set_filter(self, text: str, match_count: int = 0, total_count: int = 0, truncated: bool = False) -> None:
        self.last_filter = (text, match_count, total_count)


class FakeNode:
    def __init__(self, label: str, data: object | None = None, parent: FakeNode | None = None) -> None:
        self.label = label
        self.data = data
        self.parent = parent
        self.children: list[FakeNode] = []
        self.expanded = False

    def add(self, label: str) -> FakeNode:
        node = FakeNode(label, parent=self)
        self.children.append(node)
        return node

    def add_leaf(self, label: str) -> FakeNode:
        return self.add(label)

    def set_label(self, label: str) -> None:
        self.label = label

    def remove(self) -> None:
        if self.parent is not None:
            self.parent.children.remove(self)
            self.parent = None

    def expand(self) -> None:
        self.expanded = True


class FakeTree:
    def __init__(self) -> None:
        self.root = FakeNode("root")
        self.cursor_node: FakeNode | None = None
        self.has_focus = True
        self.selected_node: FakeNode | None = None

    def focus(self) -> None:
        self.has_focus = True

    def select_node(self, node: FakeNode) -> None:
        self.selected_node = node

    def move_cursor(self, node: FakeNode) -> None:
        self.cursor_node = node


class Host(TreeFilterMixin):
    def __init__(self) -> None:
        self.object_tree = FakeTree()
        self.tree_filter_input = FakeFilterInput()
        self.current_connection = None
        self.current_provider = None
        self.refreshed = False
        self.activated_node: FakeNode | None = None
        self._expanded_paths: set[str] = set()
        self._pending_tree_cursor_path = ""
        self._pending_tree_cursor_connection = ""
        self.timers: list[object] = []
        self.load_calls: list[FakeNode] = []

    def _get_node_kind(self, node: FakeNode) -> str:
        data = node.data
        getter = getattr(data, "get_node_kind", None)
        return getter() if callable(getter) else ""

    def _get_node_path_part(self, data: object) -> str:
        getter = getattr(data, "get_node_path_part", None)
        return getter() if callable(getter) else ""

    def _update_footer_bindings(self) -> None:
        pass

    def refresh_tree(self) -> None:
        self.refreshed = True

    def _activate_tree_node(self, node: FakeNode) -> None:
        self.activated_node = node

    def _load_folder_async(self, node: FakeNode, _data: object) -> None:
        self.load_calls.append(node)

    def set_timer(self, _delay: float, callback: object) -> None:
        self.timers.append(callback)

    def run_timers(self) -> None:
        callbacks = list(self.timers)
        self.timers = []
        for callback in callbacks:
            if callable(callback):
                callback()


def build_host() -> tuple[Host, FakeNode, FakeNode, FakeNode, FakeNode]:
    host = Host()
    database = host.object_tree.root.add("main")
    database.data = DatabaseNode(name="main")

    tables = database.add("Tables")
    tables.data = FolderNode(folder_type="tables", database="main")
    users = tables.add("users")
    users.data = TableNode(database="main", schema="public", name="users")
    orders = tables.add("orders")
    orders.data = TableNode(database="main", schema="public", name="orders")

    views = database.add("Views")
    views.data = FolderNode(folder_type="views", database="main")
    user_view = views.add("user_view")
    user_view.data = ViewNode(database="main", schema="public", name="user_view")
    return host, database, tables, users, views


def test_tree_filter_only_searches_through_database_nodes() -> None:
    host, database, tables, _users, views = build_host()
    host.object_tree.cursor_node = database

    host.action_tree_filter()
    host._tree_filter_text = "main"
    host._update_tree_filter()

    assert host._tree_filter_scope_path is None
    assert host._tree_filter_matches == [database]
    assert database.parent is host.object_tree.root
    assert tables.parent is None
    assert views.parent is None
    assert host.tree_filter_input.last_filter == ("main", 1, 1)


def test_tree_filter_accept_keeps_main_accept_behavior() -> None:
    host, database, _tables, _users, _views = build_host()
    host.object_tree.cursor_node = database
    host.action_tree_filter()
    host._tree_filter_text = "main"
    host._update_tree_filter()

    host.action_tree_filter_accept()

    assert host.object_tree.selected_node is database
    assert host.object_tree.cursor_node is database
    assert host.activated_node is database
    assert host._pending_tree_cursor_path == ""
    assert host.refreshed is True
    assert host._tree_filter_visible is False


def test_tree_filter_does_not_load_table_folders_while_searching() -> None:
    host, database, tables, _users, _views = build_host()
    host.object_tree.cursor_node = database
    host.current_connection = object()
    host.current_provider = object()

    host.action_tree_filter()
    host._tree_filter_text = "main"
    host._update_tree_filter()

    assert host._tree_filter_scope_path is None
    assert host.load_calls == []
    assert tables.children


def test_table_filter_still_loads_tables_scope_while_searching() -> None:
    host, database, tables, users, _views = build_host()
    host.object_tree.cursor_node = database
    host.current_connection = object()
    host.current_provider = object()
    users.remove()
    tables.children.clear()

    host.action_table_filter()
    host._tree_filter_text = "us"
    host._update_tree_filter()

    assert host._tree_filter_scope_path == "db:main/folder:tables"
    assert host.load_calls == [tables]


def test_table_filter_from_database_only_searches_tables_subtree() -> None:
    host, database, tables, users, views = build_host()
    host.object_tree.cursor_node = database

    host.action_table_filter()
    host._tree_filter_text = "us"
    host._update_tree_filter()

    assert host._tree_filter_scope_path == "db:main/folder:tables"
    assert host._tree_filter_matches == [users]
    assert [child.data.get_label_text() for child in tables.children] == ["users"]
    assert views.parent is None
    assert host.tree_filter_input.last_filter == ("us", 1, 2)


def test_table_filter_from_tables_folder_uses_that_tables_subtree() -> None:
    host, _database, tables, users, views = build_host()
    host.object_tree.cursor_node = tables

    host.action_table_filter()
    host._tree_filter_text = "us"
    host._update_tree_filter()

    assert host._tree_filter_scope_path == "db:main/folder:tables"
    assert host._tree_filter_matches == [users]
    assert views.parent is None


def test_table_filter_from_table_uses_ancestor_tables_subtree() -> None:
    host, _database, _tables, users, views = build_host()
    host.object_tree.cursor_node = users

    host.action_table_filter()
    host._tree_filter_text = "us"
    host._update_tree_filter()

    assert host._tree_filter_scope_path == "db:main/folder:tables"
    assert host._tree_filter_matches == [users]
    assert views.parent is None


def test_table_filter_does_not_fall_back_to_root_when_scope_is_missing() -> None:
    host, _database, tables, _users, _views = build_host()
    info_schema = host.object_tree.root.add("information_schema")
    info_schema.data = DatabaseNode(name="information_schema")
    info_tables = info_schema.add("Tables")
    info_tables.data = FolderNode(folder_type="tables", database="information_schema")
    routines = info_tables.add("ROUTINES")
    routines.data = TableNode(database="information_schema", schema="", name="ROUTINES")

    host._tree_filter_visible = True
    host._tree_filter_scope_path = "db:main/folder:tables"
    host._tree_filter_scope_node = None
    tables.remove()
    host._tree_filter_text = "routine"

    host._update_tree_filter()

    assert host._tree_filter_matches == []
    assert host.object_tree.cursor_node is None
    assert routines.parent is info_tables
    assert host.tree_filter_input.last_filter == ("routine", 0, 0)


def test_table_filter_accept_moves_cursor_to_matched_table() -> None:
    host, database, _tables, users, _views = build_host()
    host.object_tree.cursor_node = database
    host.action_table_filter()
    host._tree_filter_text = "us"
    host._update_tree_filter()

    host.action_tree_filter_accept()

    assert host.object_tree.cursor_node is users
    assert host.activated_node is users
    assert host._pending_tree_cursor_path == "db:main/folder:tables/table:public.users"
    assert "db:main" in host._expanded_paths
    assert "db:main/folder:tables" in host._expanded_paths
    assert host.refreshed is False
    assert host._tree_filter_visible is False


def test_table_filter_cursor_restore_retries_until_table_is_reloaded() -> None:
    host, _database, tables, users, _views = build_host()
    path = "db:main/folder:tables/table:public.users"
    users.remove()

    restored = host._restore_tree_filter_cursor_path(path)

    assert restored is None
    assert host._pending_tree_cursor_path == path
    assert host.timers

    reloaded_users = tables.add("users")
    reloaded_users.data = TableNode(database="main", schema="public", name="users")
    host.run_timers()

    assert host.object_tree.cursor_node is reloaded_users

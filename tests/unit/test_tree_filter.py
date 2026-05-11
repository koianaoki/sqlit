"""Unit tests for explorer tree filtering."""

from __future__ import annotations

from typing import Any

from sqlit.domains.explorer.domain.tree_nodes import FolderNode, LoadingNode, TableNode
from sqlit.domains.explorer.ui.mixins.tree_filter import TreeFilterMixin


class FakeNode:
    def __init__(self, label: str, data: Any | None = None) -> None:
        self.label = label
        self.data = data
        self.children: list[FakeNode] = []
        self.parent: FakeNode | None = None
        self.is_expanded = False
        self.allow_expand = False

    def add(self, label: str, data: Any | None = None) -> FakeNode:
        child = FakeNode(label, data)
        child.parent = self
        self.children.append(child)
        return child

    def add_leaf(self, label: str, data: Any | None = None) -> FakeNode:
        return self.add(label, data)

    def remove(self) -> None:
        if self.parent is not None:
            self.parent.children.remove(self)
            self.parent = None

    def expand(self) -> None:
        self.is_expanded = True

    def set_label(self, label: str) -> None:
        self.label = label


class FakeTree:
    def __init__(self, root: FakeNode) -> None:
        self.root = root
        self.cursor_node: FakeNode | None = None
        self.has_focus = True
        self.selected_node: FakeNode | None = None

    def focus(self) -> None:
        self.has_focus = True

    def select_node(self, node: FakeNode) -> None:
        self.selected_node = node

    def move_cursor(self, node: FakeNode) -> None:
        self.cursor_node = node
        self.selected_node = node


class FakeFilterInput:
    def __init__(self) -> None:
        self.last_filter: tuple[str, int, int] | None = None

    def show(self) -> None:
        pass

    def hide(self) -> None:
        pass

    def set_filter(self, text: str, matches: int, total: int) -> None:
        self.last_filter = (text, matches, total)


class FakeTreeFilterHost(TreeFilterMixin):
    def __init__(self, root: FakeNode) -> None:
        self.object_tree = FakeTree(root)
        self.tree_filter_input = FakeFilterInput()
        self.current_connection = object()
        self.current_provider = object()
        self._loading_nodes: set[str] = set()
        self.loaded_folders: list[FakeNode] = []
        self.refreshed = False
        self._tree_filter_visible = True
        self._tree_filter_text = ""
        self._tree_filter_query = ""
        self._tree_filter_fuzzy = False
        self._tree_filter_regex_mode = False
        self._tree_filter_regex = None
        self._tree_filter_regex_error = None
        self._tree_filter_typing = True
        self._tree_filter_matches = []
        self._tree_filter_match_index = 0
        self._tree_original_labels = {}
        self._tree_filter_applied = False
        self._tree_filter_scope_path: str | None = None
        self._expanded_paths: set[str] = set()

    def _get_node_kind(self, node: FakeNode) -> str:
        if node.data is None:
            return ""
        return node.data.get_node_kind()

    def _get_node_path_part(self, data: Any) -> str:
        return data.get_node_path_part()

    def _load_folder_async(self, node: FakeNode, data: Any) -> None:
        self.loaded_folders.append(node)

    def refresh_tree(self) -> None:
        self.refreshed = True

    def _update_footer_bindings(self) -> None:
        pass

    def _activate_tree_node(self, node: FakeNode) -> None:
        pass


def test_table_filter_loads_unloaded_table_folder_and_keeps_it_visible() -> None:
    root = FakeNode("root")
    tables = root.add("Tables", FolderNode(folder_type="tables"))
    host = FakeTreeFilterHost(root)
    host.object_tree.cursor_node = tables
    host.action_table_filter()
    host._tree_filter_text = "orders"

    host._update_tree_filter()

    assert host.loaded_folders == [tables]
    assert tables in root.children
    assert tables.is_expanded is True
    assert len(tables.children) == 1
    assert isinstance(tables.children[0].data, LoadingNode)
    assert host._tree_filter_matches == []


def test_table_filter_matches_tables_under_non_matching_folder_label() -> None:
    root = FakeNode("root")
    tables = root.add("Tables", FolderNode(folder_type="tables"))
    orders = tables.add("orders", TableNode(database=None, schema="main", name="orders"))
    tables.add("customers", TableNode(database=None, schema="main", name="customers"))
    host = FakeTreeFilterHost(root)
    host.object_tree.cursor_node = tables
    host.action_table_filter()
    host._tree_filter_text = "orders"

    host._update_tree_filter()

    assert host.loaded_folders == []
    assert host._tree_filter_matches == [orders]
    assert tables in root.children
    assert tables.children == [orders]
    assert host.object_tree.selected_node is orders


def test_table_filter_regex_matches_table_labels() -> None:
    root = FakeNode("root")
    tables = root.add("Tables", FolderNode(folder_type="tables"))
    users = tables.add("user_accounts", TableNode(database=None, schema="main", name="user_accounts"))
    orders = tables.add("orders_2026", TableNode(database=None, schema="main", name="orders_2026"))
    tables.add("audit_log", TableNode(database=None, schema="main", name="audit_log"))
    host = FakeTreeFilterHost(root)
    host.object_tree.cursor_node = tables
    host.action_table_filter()
    host._tree_filter_text = r"/^(user|orders)_"

    host._update_tree_filter()

    assert host._tree_filter_regex_mode is True
    assert host._tree_filter_matches == [users, orders]
    assert tables.children == [users, orders]
    assert host.object_tree.selected_node is users


def test_table_filter_regex_supports_re_prefix() -> None:
    root = FakeNode("root")
    tables = root.add("Tables", FolderNode(folder_type="tables"))
    customer = tables.add("customer_profile", TableNode(database=None, schema="main", name="customer_profile"))
    tables.add("orders", TableNode(database=None, schema="main", name="orders"))
    host = FakeTreeFilterHost(root)
    host.object_tree.cursor_node = tables
    host.action_table_filter()
    host._tree_filter_text = r"re:_profile$"

    host._update_tree_filter()

    assert host._tree_filter_regex_mode is True
    assert host._tree_filter_matches == [customer]
    assert tables.children == [customer]


def test_table_filter_invalid_regex_does_not_raise() -> None:
    root = FakeNode("root")
    tables = root.add("Tables", FolderNode(folder_type="tables"))
    tables.add("orders", TableNode(database=None, schema="main", name="orders"))
    host = FakeTreeFilterHost(root)
    host.object_tree.cursor_node = tables
    host.action_table_filter()
    host._tree_filter_text = r"/(orders"

    host._update_tree_filter()

    assert host._tree_filter_regex_mode is True
    assert host._tree_filter_regex is None
    assert host._tree_filter_regex_error
    assert host._tree_filter_matches == []
    assert host.tree_filter_input.last_filter == (r"/(orders", 0, 1)

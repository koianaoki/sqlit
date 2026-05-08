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
        self.has_focus = True
        self.selected_node: FakeNode | None = None

    def focus(self) -> None:
        self.has_focus = True

    def select_node(self, node: FakeNode) -> None:
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
        self._tree_filter_typing = True
        self._tree_filter_matches = []
        self._tree_filter_match_index = 0
        self._tree_original_labels = {}
        self._tree_filter_applied = False

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


def test_tree_filter_loads_unloaded_table_folder_and_keeps_it_visible() -> None:
    root = FakeNode("root")
    tables = root.add("Tables", FolderNode(folder_type="tables"))
    host = FakeTreeFilterHost(root)
    host._tree_filter_text = "orders"

    host._update_tree_filter()

    assert host.loaded_folders == [tables]
    assert tables in root.children
    assert tables.is_expanded is True
    assert len(tables.children) == 1
    assert isinstance(tables.children[0].data, LoadingNode)
    assert host._tree_filter_matches == []


def test_tree_filter_matches_tables_under_non_matching_folder_label() -> None:
    root = FakeNode("root")
    tables = root.add("Tables", FolderNode(folder_type="tables"))
    orders = tables.add("orders", TableNode(database=None, schema="main", name="orders"))
    tables.add("customers", TableNode(database=None, schema="main", name="customers"))
    host = FakeTreeFilterHost(root)
    host._tree_filter_text = "orders"

    host._update_tree_filter()

    assert host.loaded_folders == []
    assert host._tree_filter_matches == [orders]
    assert tables in root.children
    assert tables.children == [orders]
    assert host.object_tree.selected_node is orders

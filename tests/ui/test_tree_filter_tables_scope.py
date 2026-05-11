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


class Host(TreeFilterMixin):
    def __init__(self) -> None:
        self.object_tree = FakeTree()
        self.tree_filter_input = FakeFilterInput()
        self.current_connection = None
        self.current_provider = None
        self.refreshed = False

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
        pass


def build_host() -> tuple[Host, FakeNode, FakeNode, FakeNode]:
    host = Host()
    database = host.object_tree.root.add("main")
    database.data = DatabaseNode(name="main")

    tables = database.add("tables")
    tables.data = FolderNode(folder_type="tables", database="main")
    users = tables.add("users")
    users.data = TableNode(database="main", schema="public", name="users")
    orders = tables.add("orders")
    orders.data = TableNode(database="main", schema="public", name="orders")

    views = database.add("views")
    views.data = FolderNode(folder_type="views", database="main")
    user_view = views.add("user_view")
    user_view.data = ViewNode(database="main", schema="public", name="user_view")
    return host, tables, users, views


def test_filter_started_on_tables_folder_only_searches_tables_subtree() -> None:
    host, tables, users, views = build_host()
    host.object_tree.cursor_node = tables

    host.action_tree_filter()
    host._tree_filter_text = "us"
    host._update_tree_filter()

    assert host._tree_filter_scope_path == "db:main/folder:tables"
    assert host._tree_filter_matches == [users]
    assert [child.data.get_label_text() for child in tables.children] == ["users"]
    assert views.parent is None
    assert host.tree_filter_input.last_filter == ("us", 1, 2)


def test_filter_started_on_table_uses_ancestor_tables_folder_as_scope() -> None:
    host, tables, users, _views = build_host()
    host.object_tree.cursor_node = users

    host.action_tree_filter()

    assert host._get_tree_filter_search_root() is tables
    assert host._tree_filter_scope_path == "db:main/folder:tables"

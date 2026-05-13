"""Tests for results yank INSERT statement copying."""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

from sqlit.core.input_context import InputContext
from sqlit.core.key_router import resolve_action
from sqlit.core.keymap import get_keymap
from sqlit.core.vim import VimMode

try:
    from sqlit.domains.results.ui.mixins.results import ResultsMixin
except ModuleNotFoundError as exc:
    if exc.name != "textual":
        raise
    widgets_module = ModuleType("sqlit.shared.ui.widgets")

    class _StubSqlitDataTable:
        pass

    widgets_module.SqlitDataTable = _StubSqlitDataTable
    sys.modules["sqlit.shared.ui.widgets"] = widgets_module
    from sqlit.domains.results.ui.mixins.results import ResultsMixin


class _ResultsArea:
    def has_class(self, _class_name: str) -> bool:
        return False


class _Table:
    def __init__(self, rows: list[tuple[Any, ...]], *, cursor_row: int = 0) -> None:
        self._rows = rows
        self.cursor_row = cursor_row
        self.cursor_coordinate = (cursor_row, 0)
        self.row_count = len(rows)
        self.result_table_info = {"name": "users"}

    def get_row_at(self, row: int) -> tuple[Any, ...]:
        return self._rows[row]


class _Host(ResultsMixin):
    def __init__(self, columns: list[str], rows: list[tuple[Any, ...]], *, cursor_row: int = 0) -> None:
        self.results_area = _ResultsArea()
        self.results_table = _Table(rows, cursor_row=cursor_row)
        self._last_result_columns = columns
        self._last_result_rows = rows
        self._last_query_table = None
        self.copied_text: str | None = None
        self.notifications: list[tuple[str, str | None]] = []
        self.flashes: list[tuple[Any, str]] = []
        self.leader_cleared = False

    def _clear_leader_pending(self) -> None:
        self.leader_cleared = True

    def _copy_text(self, text: str) -> bool:
        self.copied_text = text
        return True

    def _flash_table_yank(self, table: Any, scope: str) -> None:
        self.flashes.append((table, scope))

    def notify(self, message: str, *, severity: str | None = None) -> None:
        self.notifications.append((message, severity))


def test_ry_leader_menu_resolves_i_to_ry_insert() -> None:
    keymap = get_keymap()
    assert keymap.leader("insert", menu="ry") == "i"

    ctx = InputContext(
        focus="results",
        vim_mode=VimMode.NORMAL,
        leader_pending=True,
        leader_menu="ry",
        tree_filter_active=False,
        tree_multi_select_active=False,
        tree_visual_mode_active=False,
        autocomplete_visible=False,
        results_filter_active=False,
        value_view_active=False,
        value_view_tree_mode=False,
        value_view_is_json=False,
        query_executing=False,
        modal_open=False,
        has_connection=True,
        current_connection_name=None,
        tree_node_kind=None,
        tree_node_folder_type=None,
        tree_node_connection_name=None,
        tree_node_connection_selected=False,
        last_result_is_error=False,
        has_results=True,
    )

    assert resolve_action("i", ctx, is_allowed=lambda _action: True) == "ry_insert"


def test_action_ry_insert_copies_selected_row_as_insert_statement() -> None:
    host = _Host(
        ["id", "name", "active", "score", "note"],
        [
            (1, "Alice", True, 12.5, None),
            (2, "O'Brien", False, 7, "hello"),
        ],
        cursor_row=1,
    )

    host.action_ry_insert()

    assert host.leader_cleared
    assert host.copied_text == (
        "INSERT INTO users (id, name, active, score, note) "
        "VALUES (2, 'O''Brien', FALSE, 7, 'hello');"
    )
    assert host.flashes == [(host.results_table, "row")]
    assert host.notifications == []


def test_action_ry_insert_formats_null_bool_number_and_escaped_string() -> None:
    host = _Host(
        ["id", "name", "active", "score", "note"],
        [(1, "Alice's", True, 12.5, None)],
    )

    host.action_ry_insert()

    assert host.copied_text == (
        "INSERT INTO users (id, name, active, score, note) "
        "VALUES (1, 'Alice''s', TRUE, 12.5, NULL);"
    )

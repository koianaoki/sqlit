"""Protocols for explorer/tree mixins."""

from __future__ import annotations

from typing import Any, Protocol


class ExplorerStateProtocol(Protocol):
    _expanded_paths: set[str]
    _loading_nodes: set[str]
    _schema_service: Any | None
    _schema_service_session: Any | None
    _tree_filter_visible: bool
    _tree_filter_text: str
    _tree_filter_query: str
    _tree_filter_fuzzy: bool
    _tree_filter_regex_mode: bool
    _tree_filter_regex: Any | None
    _tree_filter_regex_error: str | None
    _tree_filter_typing: bool
    _tree_filter_matches: list[Any]
    _tree_filter_match_index: int
    _tree_original_labels: dict[int, str]
    _tree_filter_applied: bool
    _tree_filter_scope_path: str | None
    _TREE_FILTER_LOADABLE_FOLDERS: set[str]


class ExplorerActionsProtocol(Protocol):
    def _get_schema_service(self) -> Any:
        ...

    def _get_object_cache(self) -> dict[str, dict[str, Any]]:
        ...

    def _db_type_badge(self, db_type: str) -> str:
        ...

    def _format_connection_label(self, conn: Any, status: str, spinner: str | None = None) -> str:
        ...

    def _connect_spinner_frame(self) -> str:
        ...

    def _get_node_kind(self, node: Any) -> str:
        ...

    def _activate_tree_node(self, node: Any) -> None:
        ...

    def _show_table_metadata_result(
        self,
        result_columns: list[str],
        rows: list[Any],
        *,
        query_text: str,
        message_prefix: str,
        table_name: str,
    ) -> None:
        ...

    def _fetch_cursor_result(self, query: str) -> tuple[list[str], list[tuple[Any, ...]]]:
        ...

    def action_tree_filter(self) -> None:
        ...

    def action_tree_filter_close(self) -> None:
        ...

    def action_table_filter(self) -> None:
        ...

    def _begin_tree_filter_session(self, *, scope_path: str | None) -> None:
        ...

    def _close_tree_filter_state(self, *, restore_tree: bool) -> None:
        ...

    def action_tree_filter_accept(self) -> None:
        ...

    def action_tree_filter_next(self) -> None:
        ...

    def action_tree_filter_prev(self) -> None:
        ...

    def _update_tree_filter(self) -> None:
        ...

    def _jump_to_current_match(self) -> None:
        ...

    def _expand_ancestors(self, node: Any) -> None:
        ...

    def _restore_tree_labels(self) -> None:
        ...

    def _show_all_tree_nodes(self) -> None:
        ...

    def _count_all_nodes(self, root: Any | None = None) -> int:
        ...

    def _get_table_filter_tables_folder(self) -> Any | None:
        ...

    def _remember_tree_filter_path(self, path: str | None, *, include_self: bool = False) -> None:
        ...

    def _move_tree_cursor_to_node(self, node: Any) -> None:
        ...

    def _restore_tree_filter_cursor_path(self, path: str, attempt: int = 0) -> Any | None:
        ...

    def _get_tree_filter_search_root(self) -> Any:
        ...

    def _extract_tree_filter_regex_query(self, raw_text: str) -> str | None:
        ...

    def _match_tree_filter_regex(self, label_text: str) -> tuple[bool, list[int]]:
        ...

    def _ensure_tree_filter_search_nodes_loaded(self) -> bool:
        ...

    def _tree_filter_should_load_node(self, node: Any) -> bool:
        ...

    def _start_tree_filter_node_load(self, node: Any) -> bool:
        ...

    def _tree_filter_node_has_pending_load(self, node: Any) -> bool:
        ...

    def _tree_filter_can_match_node(self, node: Any) -> bool:
        ...

    def _tree_filter_should_descend_node(self, node: Any) -> bool:
        ...

    def _find_matching_nodes(self, node: Any, matches: list[Any], include_self: bool = True) -> bool:
        ...

    def _get_node_label_text(self, node: Any) -> str:
        ...

    def _apply_filter_to_tree(self) -> None:
        ...

    def _set_node_visibility(
        self,
        node: Any,
        match_ids: set[Any],
        ancestor_ids: set[Any],
        pending_ids: set[Any],
        visible: bool,
    ) -> None:
        ...

    def _rebuild_label_with_highlight(self, node: Any, highlighted_text: str) -> str:
        ...

    def _load_columns_async(self, node: Any, data: Any) -> None:
        ...

    def _load_folder_async(self, node: Any, data: Any) -> None:
        ...

    def refresh_tree(self) -> None:
        ...

    def _get_node_path_part(self, node: Any) -> str:
        ...


class ExplorerProtocol(ExplorerStateProtocol, ExplorerActionsProtocol, Protocol):
    """Composite protocol for explorer-related mixins."""

    pass

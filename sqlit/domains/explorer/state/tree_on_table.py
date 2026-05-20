"""Explorer tree state for table/view nodes."""

from __future__ import annotations

from sqlit.core.input_context import InputContext
from sqlit.core.state_base import DisplayBinding, State, resolve_display_key


class TreeOnTableState(State):
    """Tree focused on table or view node."""

    help_category = "Explorer"

    def _setup_actions(self) -> None:
        def is_table(app: InputContext) -> bool:
            return app.tree_node_kind == "table"

        self.allows("select_table", label="Select TOP 100", help="Select TOP 100 (table/view)")
        self.allows("show_table_columns", label="Show Columns", help="Show table columns")
        self.allows("show_table_indexes", label="Show Indexes", help="Show table indexes")
        self.allows(
            "table_filter",
            is_table,
            label="Table Filter",
            help="Filter tables in this database",
        )

    def get_display_bindings(self, app: InputContext) -> tuple[list[DisplayBinding], list[DisplayBinding]]:
        left: list[DisplayBinding] = []
        seen: set[str] = set()

        left.append(
            DisplayBinding(
                key=resolve_display_key("select_table") or "s",
                label="Select TOP 100",
                action="select_table",
            )
        )
        seen.add("select_table")
        left.append(
            DisplayBinding(
                key=resolve_display_key("show_table_columns") or "c",
                label="Show Columns",
                action="show_table_columns",
            )
        )
        seen.add("show_table_columns")
        left.append(
            DisplayBinding(
                key=resolve_display_key("show_table_indexes") or "i",
                label="Show Indexes",
                action="show_table_indexes",
            )
        )
        seen.add("show_table_indexes")
        if app.tree_node_kind == "table":
            left.append(
                DisplayBinding(
                    key=resolve_display_key("table_filter") or "t",
                    label="Table Filter",
                    action="table_filter",
                )
            )
            seen.add("table_filter")
        left.append(
            DisplayBinding(
                key=resolve_display_key("refresh_tree") or "f",
                label="Refresh",
                action="refresh_tree",
            )
        )
        seen.add("refresh_tree")

        if self.parent:
            parent_left, _ = self.parent.get_display_bindings(app)
            for binding in parent_left:
                if binding.action not in seen:
                    left.append(binding)
                    seen.add(binding.action)

        return left, []

    def is_active(self, app: InputContext) -> bool:
        return app.focus == "explorer" and app.tree_node_kind in ("table", "view")

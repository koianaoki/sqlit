"""Tests for table metadata shortcuts in the explorer."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

from sqlit.domains.connections.providers.adapters.base import ColumnInfo
from sqlit.domains.connections.providers.model import SchemaCapabilities
from sqlit.domains.explorer.domain.tree_nodes import TableNode
from sqlit.domains.explorer.state.tree_on_table import TreeOnTableState
from sqlit.domains.explorer.ui.mixins.tree import TreeMixin


@dataclass
class MockTreeNode:
    data: object | None = None


class MockTree:
    def __init__(self, node: MockTreeNode) -> None:
        self.cursor_node = node


class MockQueryInput:
    def __init__(self) -> None:
        self.text = ""


class TestTableMetadataShortcuts:
    def _create_mixin(self, *, supports_indexes: bool = True):
        mixin = object.__new__(TreeMixin)
        table_data = TableNode(database="app_db", schema="public", name="users")
        mixin.object_tree = MockTree(MockTreeNode(table_data))
        mixin.query_input = MockQueryInput()
        mixin.current_provider = MagicMock()
        mixin.current_provider.capabilities = SchemaCapabilities(
            supports_multiple_databases=True,
            supports_cross_database_queries=True,
            supports_stored_procedures=False,
            supports_indexes=supports_indexes,
            supports_triggers=False,
            supports_sequences=False,
            default_schema="public",
            system_databases=frozenset(),
        )
        mixin._get_node_kind = lambda node: "table" if isinstance(node.data, TableNode) else ""
        mixin._replace_results_table = MagicMock()
        mixin.notify = MagicMock()
        mixin._last_result_columns = []
        mixin._last_result_rows = []
        mixin._last_result_row_count = 0
        return mixin

    def test_show_table_columns_displays_columns_in_results(self):
        mixin = self._create_mixin()
        schema_service = MagicMock()
        schema_service.list_columns.return_value = [
            ColumnInfo("id", "integer", True),
            ColumnInfo("email", "varchar", False),
        ]
        mixin._get_schema_service = MagicMock(return_value=schema_service)

        mixin.action_show_table_columns()

        schema_service.list_columns.assert_called_once_with("app_db", "public", "users")
        mixin._replace_results_table.assert_called_once_with(
            ["#", "Column", "Type", "Primary Key"],
            [(1, "id", "integer", "Yes"), (2, "email", "varchar", "")],
        )
        assert mixin._last_result_row_count == 2
        assert mixin.query_input.text == "-- Columns for users"

    def test_show_table_indexes_displays_matching_indexes_in_results(self):
        mixin = self._create_mixin()
        schema_service = MagicMock()
        schema_service.list_folder_items.return_value = [
            ("index", "idx_users_email", "users"),
            ("index", "idx_orders_user_id", "orders"),
        ]
        schema_service.get_index_definition.return_value = {
            "columns": ["email"],
            "is_unique": True,
            "definition": "CREATE UNIQUE INDEX idx_users_email ON users (email)",
        }
        mixin._get_schema_service = MagicMock(return_value=schema_service)

        mixin.action_show_table_indexes()

        schema_service.list_folder_items.assert_called_once_with("indexes", "app_db")
        schema_service.get_index_definition.assert_called_once_with("app_db", "idx_users_email", "users")
        mixin._replace_results_table.assert_called_once_with(
            ["Index", "Columns", "Unique", "Definition"],
            [("idx_users_email", "email", "Yes", "CREATE UNIQUE INDEX idx_users_email ON users (email)")],
        )
        assert mixin._last_result_row_count == 1
        assert mixin.query_input.text == "-- Indexes for users"

    def test_show_table_columns_uses_serialized_mysql_full_columns(self):
        mixin = self._create_mixin()
        mixin.current_provider.metadata.db_type = "mysql"
        mixin.current_provider.dialect.quote_identifier.side_effect = lambda name: f"`{name}`"
        mixin.current_connection = MagicMock()
        schema_service = MagicMock()
        schema_service.execute_cursor_query.return_value = (
            ["Field", "Type", "Collation", "Null", "Key", "Default", "Extra", "Privileges", "Comment"],
            [
                ("id", "int", None, "NO", "PRI", None, "auto_increment", "select,insert", ""),
                ("email", "varchar(255)", "utf8mb4_0900_ai_ci", "YES", "UNI", None, "", "select,insert", "login email"),
            ],
        )
        mixin._get_schema_service = MagicMock(return_value=schema_service)

        mixin.action_show_table_columns()

        schema_service.execute_cursor_query.assert_called_once_with("SHOW FULL COLUMNS FROM `app_db`.`users`", "app_db")
        mixin.current_connection.cursor.assert_not_called()
        mixin._replace_results_table.assert_called_once_with(
            ["Field", "Type", "Collation", "Null", "Key", "Default", "Extra", "Privileges", "Comment"],
            [
                ("id", "int", None, "NO", "PRI", None, "auto_increment", "select,insert", ""),
                ("email", "varchar(255)", "utf8mb4_0900_ai_ci", "YES", "UNI", None, "", "select,insert", "login email"),
            ],
        )
        assert mixin.query_input.text == "SHOW FULL COLUMNS FROM `app_db`.`users`"

    def test_show_table_columns_reports_mysql_show_error_after_serialized_retry(self):
        mixin = self._create_mixin()
        mixin.current_provider.metadata.db_type = "mysql"
        mixin.current_provider.dialect.quote_identifier.side_effect = lambda name: f"`{name}`"
        mixin.current_connection = MagicMock()
        schema_service = MagicMock()
        schema_service.execute_cursor_query.side_effect = RuntimeError((0, ""))
        mixin._get_schema_service = MagicMock(return_value=schema_service)

        mixin.action_show_table_columns()

        schema_service.execute_cursor_query.assert_called_once_with("SHOW FULL COLUMNS FROM `app_db`.`users`", "app_db")
        mixin.current_connection.cursor.assert_not_called()
        mixin.notify.assert_called_once_with("Error getting table columns: (0, '')", severity="error")
        mixin._replace_results_table.assert_not_called()

    def test_show_table_indexes_uses_serialized_mysql_show_index(self):
        mixin = self._create_mixin()
        mixin.current_provider.metadata.db_type = "mysql"
        mixin.current_provider.dialect.quote_identifier.side_effect = lambda name: f"`{name}`"
        mixin.current_connection = MagicMock()
        schema_service = MagicMock()
        schema_service.execute_cursor_query.return_value = (
            ["Table", "Non_unique", "Key_name", "Seq_in_index", "Column_name", "Index_type"],
            [
                ("users", 0, "PRIMARY", 1, "id", "BTREE"),
                ("users", 1, "idx_users_email", 1, "email", "BTREE"),
            ],
        )
        mixin._get_schema_service = MagicMock(return_value=schema_service)

        mixin.action_show_table_indexes()

        schema_service.execute_cursor_query.assert_called_once_with("SHOW INDEX FROM `app_db`.`users`", "app_db")
        mixin.current_connection.cursor.assert_not_called()
        mixin._replace_results_table.assert_called_once_with(
            ["Table", "Non_unique", "Key_name", "Seq_in_index", "Column_name", "Index_type"],
            [
                ("users", 0, "PRIMARY", 1, "id", "BTREE"),
                ("users", 1, "idx_users_email", 1, "email", "BTREE"),
            ],
        )
        assert mixin.query_input.text == "SHOW INDEX FROM `app_db`.`users`"

    def test_show_table_indexes_reports_mysql_show_error_after_serialized_retry(self):
        mixin = self._create_mixin()
        mixin.current_provider.metadata.db_type = "mysql"
        mixin.current_provider.dialect.quote_identifier.side_effect = lambda name: f"`{name}`"
        mixin.current_connection = MagicMock()
        schema_service = MagicMock()
        schema_service.execute_cursor_query.side_effect = RuntimeError((0, ""))
        mixin._get_schema_service = MagicMock(return_value=schema_service)

        mixin.action_show_table_indexes()

        schema_service.execute_cursor_query.assert_called_once_with("SHOW INDEX FROM `app_db`.`users`", "app_db")
        mixin.current_connection.cursor.assert_not_called()
        mixin.notify.assert_called_once_with("Error getting table indexes: (0, '')", severity="error")
        mixin._replace_results_table.assert_not_called()

    def test_show_table_indexes_matches_table_case_insensitively(self):
        mixin = self._create_mixin()
        mixin.object_tree.cursor_node.data = TableNode(database="app_db", schema="public", name="User")
        schema_service = MagicMock()
        schema_service.list_folder_items.return_value = [
            ("index", "PRIMARY", "user"),
            ("index", "idx_order_user", "orders"),
        ]
        schema_service.get_index_definition.return_value = {
            "columns": ["id"],
            "is_unique": True,
            "definition": "CREATE UNIQUE INDEX PRIMARY ON User (id)",
        }
        mixin._get_schema_service = MagicMock(return_value=schema_service)

        mixin.action_show_table_indexes()

        schema_service.get_index_definition.assert_called_once_with("app_db", "PRIMARY", "user")
        mixin._replace_results_table.assert_called_once_with(
            ["Index", "Columns", "Unique", "Definition"],
            [("PRIMARY", "id", "Yes", "CREATE UNIQUE INDEX PRIMARY ON User (id)")],
        )

    def test_show_table_indexes_warns_when_indexes_not_supported(self):
        mixin = self._create_mixin(supports_indexes=False)
        mixin._get_schema_service = MagicMock()

        mixin.action_show_table_indexes()

        mixin.notify.assert_called_once_with("Indexes not supported for this database.", severity="warning")
        mixin._get_schema_service.assert_not_called()

    def test_tree_on_table_footer_includes_metadata_shortcuts(self):
        state = TreeOnTableState()
        app = MagicMock(focus="explorer", tree_node_kind="table")

        left, right = state.get_display_bindings(app)

        assert right == []
        actions = [binding.action for binding in left]
        assert "select_table" in actions
        assert "show_table_columns" in actions
        assert "show_table_indexes" in actions

"""Tests for MySQL index metadata."""

from __future__ import annotations

from sqlit.domains.connections.providers.mysql.adapter import MySQLAdapter


class FakeCursor:
    def __init__(self) -> None:
        self.query = ""
        self.params = None

    def execute(self, query: str, params=None) -> None:
        self.query = query
        self.params = params

    def fetchall(self):
        return [
            ("PRIMARY", "User", 0),
            ("idx_user_email", "User", 1),
        ]


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()

    def cursor(self) -> FakeCursor:
        return self.cursor_instance


def test_mysql_get_indexes_includes_primary_index() -> None:
    conn = FakeConnection()
    adapter = MySQLAdapter()

    indexes = adapter.get_indexes(conn, "app_db")

    assert "index_name != 'PRIMARY'" not in conn.cursor_instance.query
    assert conn.cursor_instance.params == ("app_db",)
    assert [index.name for index in indexes] == ["PRIMARY", "idx_user_email"]
    assert indexes[0].is_unique is True
    assert indexes[1].is_unique is False

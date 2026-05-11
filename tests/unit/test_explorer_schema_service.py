"""Tests for explorer schema service helpers."""

from __future__ import annotations

from concurrent.futures import Future
from typing import Any

from sqlit.domains.explorer.app.schema_service import ExplorerSchemaService


class FakeCursor:
    description = [("Field",), ("Type",)]

    def __init__(self) -> None:
        self.executed: str | None = None
        self.closed = False

    def execute(self, query: str) -> None:
        self.executed = query

    def fetchall(self) -> list[tuple[str, str]]:
        return [("id", "int")]

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()

    def cursor(self) -> FakeCursor:
        return self.cursor_instance


class FakeExecutor:
    def __init__(self) -> None:
        self.submitted = False

    def submit(self, fn: Any) -> Future[Any]:
        self.submitted = True
        future: Future[Any] = Future()
        try:
            future.set_result(fn())
        except Exception as error:
            future.set_exception(error)
        return future


class FakeSession:
    def __init__(self) -> None:
        self.connection = FakeConnection()
        self.executor = FakeExecutor()


def test_execute_cursor_query_uses_session_executor_and_closes_cursor() -> None:
    session = FakeSession()
    service = ExplorerSchemaService(session=session, object_cache={})  # type: ignore[arg-type]

    columns, rows = service.execute_cursor_query("SHOW FULL COLUMNS FROM `users`", "app_db")

    assert columns == ["Field", "Type"]
    assert rows == [("id", "int")]
    assert session.executor.submitted is True
    assert session.connection.cursor_instance.executed == "SHOW FULL COLUMNS FROM `users`"
    assert session.connection.cursor_instance.closed is True

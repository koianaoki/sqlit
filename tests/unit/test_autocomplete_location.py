"""Tests for autocomplete cursor location conversion."""

from sqlit.domains.query.ui.mixins.autocomplete import AutocompleteMixin


def test_location_to_offset_clamps_stale_row_to_end() -> None:
    """A stale debounced cursor row should not crash on single-line text."""
    mixin = AutocompleteMixin()

    assert mixin._location_to_offset("SELECT * FROM users", (4, 0)) == len("SELECT * FROM users")


def test_location_to_offset_clamps_column_to_current_line() -> None:
    """Columns past the line end should clamp to the line length."""
    mixin = AutocompleteMixin()

    assert mixin._location_to_offset("SELECT\nFROM", (1, 99)) == len("SELECT\nFROM")


def test_offset_to_location_clamps_offset_to_text_bounds() -> None:
    """Offset conversion should keep cursor positions inside the document."""
    mixin = AutocompleteMixin()

    assert mixin._offset_to_location("SELECT", -10) == (0, 0)
    assert mixin._offset_to_location("SELECT", 999) == (0, len("SELECT"))

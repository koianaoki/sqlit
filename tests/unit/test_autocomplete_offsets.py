"""Regression tests for autocomplete cursor offset conversion."""

from sqlit.domains.query.ui.mixins.autocomplete import AutocompleteMixin


def _location_to_offset(text: str, location: tuple[int, int]) -> int:
    """Call the mixin helper without requiring a Textual app instance."""
    return AutocompleteMixin._location_to_offset(object(), text, location)


def test_location_to_offset_converts_valid_multiline_location() -> None:
    assert _location_to_offset("SELECT\nFROM users", (1, 4)) == len("SELECT\nFROM")


def test_location_to_offset_clamps_stale_row_after_text_change() -> None:
    """A stale TextArea cursor row must not crash debounced autocomplete."""
    text = "INSERT INTO users (id, name) VALUES (1, 'alice')"

    assert _location_to_offset(text, (3, 0)) == len(text)


def test_location_to_offset_clamps_column_to_current_line() -> None:
    assert _location_to_offset("SELECT", (0, 99)) == len("SELECT")

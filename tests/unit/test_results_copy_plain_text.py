from sqlit.domains.results.ui.mixins.results import ResultsMixin


class _Dummy(ResultsMixin):
    pass


class _PlainValue:
    def __init__(self, plain: str) -> None:
        self.plain = plain


def test_to_plain_text_strips_ansi_and_prefers_plain_attr() -> None:
    d = _Dummy()
    assert d._to_plain_text(_PlainValue("ok")) == "ok"
    assert d._to_plain_text("\x1b[31mraw\x1b[0m") == "\x1b[31mraw\x1b[0m"


def test_to_sql_literal_uses_plain_text_and_escapes_quotes() -> None:
    d = _Dummy()
    assert d._to_sql_literal(None) == "NULL"
    assert d._to_sql_literal(True) == "TRUE"
    assert d._to_sql_literal(12) == "12"
    assert d._to_sql_literal("O'Reilly") == "'O''Reilly'"

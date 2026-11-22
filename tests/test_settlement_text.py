from app.components import is_settled, settlement_text


def detail(status=None, balance=100.0, owed=100.0, remaining=0.0):
    d = {"balance": balance}
    if status:
        d["settlement"] = {"status": status, "owed": owed, "covered": 0.0, "remaining": remaining}
    return d


def test_open():
    assert settlement_text(detail("open")) == "Fefe deve R$ 100,00 para Fafa"


def test_partial():
    assert settlement_text(detail("partial", remaining=40.0)) == "Fefe ainda deve R$ 40,00 para Fafa"


def test_paid():
    assert settlement_text(detail("paid")) == "Quite · Fefe pagou R$ 100,00"


def test_settled():
    assert settlement_text(detail("settled", owed=0.0)) == "Contas iguais"


def test_credit():
    assert settlement_text(detail("credit", owed=-30.0)) == "Fafa deve R$ 30,00 para Fefe"


def test_prebilling():
    assert settlement_text(detail("prebilling")) == "Quite"


def test_in_progress_variants():
    assert settlement_text(detail("in_progress", balance=100.0)) == "Fefe deve R$ 100,00 para Fafa · mês em andamento"
    assert settlement_text(detail("in_progress", balance=-5.0)) == "Fafa deve R$ 5,00 para Fefe · mês em andamento"
    assert settlement_text(detail("in_progress", balance=0.0)) == "Contas iguais · mês em andamento"


def test_fallback_without_settlement():
    assert settlement_text(detail(None, balance=100.0)) == "Fefe deve R$ 100,00 para Fafa"
    assert settlement_text(detail(None, balance=-5.0)) == "Fafa deve R$ 5,00 para Fefe"
    assert settlement_text(detail(None, balance=0.0)) == "Contas iguais"


def test_is_settled():
    assert all(is_settled(detail(s)) for s in ("paid", "settled", "prebilling"))
    assert not any(is_settled(detail(s)) for s in ("open", "partial", "credit", "in_progress"))

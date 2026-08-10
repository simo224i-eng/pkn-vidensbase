"""_apply_filters: NA-sikkerhed (pandas 2.x rejser ved NA i boolske masker)
og alle filtertyper."""
from __future__ import annotations

from app.main import _apply_filters, find_kendelse


def _alle(df, **kw):
    args = dict(mangeltype=None, selskab=None, udfald=None, år_min=None, år_max=None,
                opførelsesår_min=None, opførelsesår_max=None)
    args.update(kw)
    return _apply_filters(df, **args)


def test_år_filter_er_na_sikkert(store):
    # Regression: rækken uden dato (År=NA) må hverken crashe eller matche.
    d = _alle(store.df, år_min=2000, år_max=2030)
    assert len(d) == len(store.df) - 1
    assert "100007" not in set(d["Sagsnummer"])


def test_år_interval(store):
    d = _alle(store.df, år_min=2020, år_max=2022)
    assert set(d["Sagsnummer"]) == {"100001", "100002", "100005"}


def test_opførelsesår_er_na_sikkert(store):
    # Kun 3 rækker har Opførelsesår — resten (NA) skal ekskluderes, ikke crashe.
    d = _alle(store.df, opførelsesår_min=1900, opførelsesår_max=1980)
    assert set(d["Sagsnummer"]) == {"100001", "100003", "100008"}


def test_mangeltype_matcher_enhver_i_listen(store):
    d = _alle(store.df, mangeltype=["Skimmel/fugt", "Fundament"])
    assert set(d["Sagsnummer"]) == {"100001", "100002", "100007", "100008", "100010"}


def test_selskab_og_udfald(store):
    d = _alle(store.df, selskab=["Tryg"], udfald=["Medhold"])
    assert set(d["Sagsnummer"]) == {"100001", "100008"}


def test_kombineret_filter(store):
    d = _alle(store.df, mangeltype=["Skimmel/fugt"], år_min=2021, år_max=2024)
    assert set(d["Sagsnummer"]) == {"100001", "100010"}


def test_find_kendelse_på_sagsnummer(store):
    row = find_kendelse(store.df, "100003")
    assert row is not None and row["Titel"] == "Utæt tag efter storm"


def test_find_kendelse_på_link_suffix(store):
    row = find_kendelse(store.df, "kendelser/100005")
    assert row is not None and row["Sagsnummer"] == "100005"


def test_find_kendelse_tom_id_matcher_aldrig(store):
    # Regression: "" matchede tidligere ALLE rækker via Link.endswith("").
    assert find_kendelse(store.df, "") is None
    assert find_kendelse(store.df, "   ") is None


def test_find_kendelse_ukendt_id(store):
    assert find_kendelse(store.df, "999999") is None

"""v0.44.0 "the phrasebook": the zero-build UI dictionary (English + Bahasa
Indonesia) and the window-top seam fix — the header's wet edge read as a 1px
line against the native chrome, so the bar keeps glass + hairline only."""
import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

SRC = Path(__file__).resolve().parents[1] / "src" / "suravidl_engine"
WEB = SRC / "web"

APP = (WEB / "app.js").read_text(encoding="utf-8")
HTML = (WEB / "index.html").read_text(encoding="utf-8")
CSS = (WEB / "style.css").read_text(encoding="utf-8")

AUTH = {"Authorization": "Bearer t"}


def _app(tmp_path):
    import suravidl_engine.api as api

    return api.create_app(download_dir=tmp_path / "dl", auth_token="t",
                          db_path=tmp_path / "jobs.db")


def _dict():
    m = re.search(r"const STRINGS = \{ en: \{\}, id: \{(.*?)\n\} \};", APP, re.S)
    assert m, "STRINGS block shape changed"
    return json.loads("{" + m.group(1) + "}")


def test_dictionary_ships_and_is_well_formed():
    d = _dict()
    assert len(d) >= 650
    for probe in ("Download", "Queue", "Settings", "Probe", "Cancel", "Save",
                  "Language"):
        assert probe in d, probe
    for k, v in d.items():
        assert set(re.findall(r"\{[^}]*\}", k)) == set(re.findall(r"\{[^}]*\}", v)), k
        assert (k != k.lstrip()) == (v != v.lstrip()), k
        assert (k != k.rstrip()) == (v != v.rstrip()), k


def test_the_dictionary_speaks_indonesian():
    d = _dict()
    assert d["Download"] == "Unduh"
    assert d["Quit"] == "Keluar"
    assert d["Probe"] == "Cek"
    assert d["Settings"] == "Pengaturan"
    assert d["Language"] == "Bahasa"


def test_the_static_page_declares_its_strings():
    n = len(re.findall(r"data-i18n(?:-title|-aria|-ph)?=", HTML))
    assert n >= 300
    assert 'data-i18n="Download"' in HTML
    assert 'id="setLang"' in HTML
    assert 'data-i18n="Language"' in HTML
    assert '<option value="id"' in HTML


def test_the_wiring_applies_at_boot_and_on_switch():
    assert APP.count("applyStaticI18n()") >= 2          # boot + relabel-on-switch
    assert "async function setLanguage(" in APP
    assert "n.textContent = t(n.dataset.i18n)" in APP
    assert '$("setLang").value = s.language === "id" ? "id" : "en"' in APP
    assert "langSel.onchange = () => setLanguage(langSel.value)" in APP
    assert 'document.title = t("🐴 suravidl")' in APP   # the brand mark rides the key


def test_settings_carry_the_language(tmp_path):
    c = TestClient(_app(tmp_path))
    s = c.get("/settings", headers=AUTH).json()
    assert s["language"] == "en"
    r = c.post("/settings", headers=AUTH, json={"language": "id"})
    assert r.status_code == 200 and r.json()["language"] == "id"
    c2 = TestClient(_app(tmp_path))
    assert c2.get("/settings", headers=AUTH).json()["language"] == "id"
    assert c.post("/settings", headers=AUTH,
                  json={"language": "fr"}).status_code == 400


def test_the_page_ships_the_language(tmp_path):
    with TestClient(_app(tmp_path)) as c:
        html = c.get("/").text
    assert '"language": "en"' in html
    assert '"theme": "dark"' in html    # the cfg block stays whole


def test_the_header_lost_its_seam_and_plates_kept_their_edge():
    m = re.search(r"\nheader \{[^}]*?position: sticky[^}]*?\n\}", CSS, re.S)
    assert m, "the main header rule moved"
    assert "inset 0 1px 0" not in m.group(0)
    assert CSS.count("inset 0 1px 0 var(--glass-hi)") >= 7
    assert "body.scrolled header { box-shadow: 0 8px 26px rgba(0,0,0,.28); }" in CSS


def test_api_inlines_the_language():
    api_src = (SRC / "api.py").read_text(encoding="utf-8")
    assert '"language": settings.get()["language"]' in api_src

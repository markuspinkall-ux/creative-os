"""Entwickler-Widget: Zahlen und Fehlermeldungen richtig auslesen; nur für den Repo-Besitzer."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shell"))
from creative_shell import entwickler as e  # noqa: E402


def test_paketseite():
    html = '<span>Total downloads</span>\n  <h3 title="1854">1.85K</h3>'
    assert e.package_downloads(html) == 1854
    assert e.package_downloads('Total downloads</span><h3>2.3K</h3>') == 2300
    assert e.package_downloads("nichts") is None


def test_releases():
    rels = [{"assets": [{"name": "a.iso", "download_count": 3}, {"name": "Gibeon-Studio-x86_64.AppImage", "download_count": 5},
                        {"name": "Gibeon-3D-Studio-x86_64.AppImage", "download_count": 2}, {"name": "studio.json", "download_count": 9}]},
            {"assets": [{"name": "b.iso", "download_count": 4}]}]
    iso, apps = e.release_downloads(rels)
    assert iso == 7 and apps == {"Studio": 5, "3D Studio": 2}
    rows = e.rows_from({"views": 1200, "uniques": 80, "image": 1854, "iso": iso, "apps": apps})
    assert rows[0]["value"] == "1.200 Besuche · 80 Personen"
    assert any(r["label"] == "AppImage Studio" and r["value"] == "5" for r in rows)


def test_meldungen():
    issues = [{"title": "Fehler: Studio stürzt ab", "number": 7, "html_url": "u", "created_at": "2026-11-22T10:00:00Z",
               "body": "### Quelle\n\nGibeon OS\n\n### Was ist passiert?\n\n…"},
              {"title": "Fehler: Link kaputt", "number": 8, "html_url": "v", "body": "### Quelle\n\nWebseite"},
              {"title": "PR", "number": 9, "pull_request": {}}]
    r = e.reports_from(issues)
    assert [x["quelle"] for x in r] == ["OS", "Webseite"] and r[0]["datum"] == "2026-11-22"


def test_nur_besitzer():
    assert e.owner_of(e.REPO) == "markuspinkall-ux"
    tpl = (ROOT / ".github/ISSUE_TEMPLATE/fehlermeldung.yml").read_text(encoding="utf-8")
    assert "fehlermeldung" in tpl and "id: quelle" in tpl and "id: version" in tpl
    wp = (ROOT / "shell/creative_shell/qml/surfaces/Wallpaper.qml").read_text(encoding="utf-8")
    assert 'visible: root.widgetOnScreen("entwickler") && devStats.enabled' in wp

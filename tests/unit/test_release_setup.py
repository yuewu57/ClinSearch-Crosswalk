from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.build_public_site import checked_url, read_versions
from scripts.check_app_availability import EXPECTED_TITLE, check_page, validate_app_url


@pytest.mark.parametrize("validator", [checked_url, validate_app_url])
def test_accepts_public_app_url(validator):
    assert validator(" https://evidentia-csc.streamlit.app ") == (
        "https://evidentia-csc.streamlit.app/"
    )


@pytest.mark.parametrize("validator", [checked_url, validate_app_url])
@pytest.mark.parametrize("url", [
    "http://example.streamlit.app",
    "https://streamlit.app/",
    "https://example.com/",
    "https://example.streamlit.app.evil.example/",
    "https://user:pass@example.streamlit.app/",
    "https://example.streamlit.app/?token=secret",
    "https://example.streamlit.app/#fragment",
    "https://example.streamlit.app/private",
    "https://example.streamlit.app:8000/",
    "https://example.streamlit.app:invalid/",
    "javascript:alert(1)",
])
def test_rejects_unsafe_or_non_app_urls(validator, url):
    with pytest.raises(ValueError):
        validator(url)


def test_site_can_be_built_before_url_exists_but_monitor_requires_url():
    assert checked_url("") == ""
    with pytest.raises(ValueError):
        validate_app_url("")


def test_version_reader_does_not_execute_package_code(tmp_path):
    source = tmp_path / "versions.py"
    source.write_text(
        'raise RuntimeError("must not execute")\n'
        '__version__ = "0.1.2"\nRULESET_VERSION = "v21"\n', encoding="utf-8"
    )
    assert read_versions(source) == {"__version__": "0.1.2", "RULESET_VERSION": "v21"}


class FakeControl:
    def __init__(self, visible=True, usable=True):
        self.visible = visible
        self.usable = usable

    def wait_for(self, **kwargs):
        if not self.visible:
            raise TimeoutError("UI absent")

    def is_editable(self):
        return self.usable

    def is_enabled(self):
        return self.usable


class FakePage:
    def __init__(self, ok=True, visible=True, usable=True, exception=False):
        self.ok = ok
        self.control = FakeControl(visible, usable)
        self.exception = exception
        self.lookups = []

    def set_default_timeout(self, timeout):
        assert timeout > 0

    def goto(self, url, **kwargs):
        return SimpleNamespace(ok=self.ok)

    def get_by_role(self, role, *, name, exact):
        self.lookups.append((role, name, exact))
        return self.control

    def locator(self, selector):
        return SimpleNamespace(count=lambda: int(self.exception))


def test_monitor_requires_actual_controls_without_clicking_or_submitting():
    page = FakePage()
    check_page(page, "https://example.streamlit.app/", 5000)
    assert page.lookups == [
        ("heading", EXPECTED_TITLE, True),
        ("textbox", "Ovid MEDLINE strategy", True),
        ("button", "Convert", True),
    ]


@pytest.mark.parametrize("kwargs", [
    {"ok": False}, {"visible": False}, {"usable": False}, {"exception": True},
])
def test_monitor_fails_for_missing_or_broken_ui(kwargs):
    with pytest.raises((RuntimeError, TimeoutError)):
        check_page(FakePage(**kwargs), "https://example.streamlit.app/", 5000)


def test_automation_requires_explicit_owner_opt_in():
    root = Path(__file__).parents[2]
    monitor = (root / ".github/workflows/app-availability.yml").read_text(encoding="utf-8")
    assert "vars.MONITORING_ENABLED == 'true'" in monitor
    assert "vars.MONITORING_POLICY_CONFIRMED == 'true'" in monitor
    assert 'cron: "17 */8 * * *"' in monitor
    assert "github.event.repository.visibility == 'public'" in monitor
    pages = (root / ".github/workflows/pages.yml").read_text(encoding="utf-8")
    assert "vars.PUBLIC_RELEASE_APPROVED == 'true'" in pages
    assert "path: _public_site" in pages

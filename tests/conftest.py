"""UI tests use explicit fixtures rather than contacting live score providers."""
import pytest


@pytest.fixture(autouse=True)
def offline_default_live_scores(monkeypatch):
    monkeypatch.setattr('live_scores.read_json',lambda url: {'events':[]})

import json
import pytest
import requests
import source_retry as m

def test_bad_json_and_http_failure_retry_then_accept_valid_scoreboard(monkeypatch):
    replies = iter([b'<html>unavailable</html>', requests.Timeout('temporary'), b'{"events": []}'])
    calls = []
    delays = []
    monkeypatch.setattr(m.time, 'sleep', delays.append)
    def fetch(url):
        calls.append(url)
        reply = next(replies)
        if isinstance(reply, Exception): raise reply
        return reply
    assert m.fetch_scoreboard(fetch, 'scoreboard') == {'events': []}
    assert len(calls) == 3 and delays == [1, 2]

@pytest.mark.parametrize('raw', [b'', b'[]', b'{}', b'{"events": null}', b'{"events": {}}'])
def test_persistent_malformed_response_fails_closed(monkeypatch, raw):
    calls = []
    monkeypatch.setattr(m.time, 'sleep', lambda delay: None)
    def fetch(url):
        calls.append(url)
        return raw
    with pytest.raises(ValueError, match='unavailable after 3 attempts'):
        m.fetch_scoreboard(fetch, 'scoreboard')
    assert len(calls) == 3

def test_valid_response_preserves_event_content_without_retry(monkeypatch):
    expected = {'events': [{'id':'42','season':{'year':2027,'type':2}}]}
    monkeypatch.setattr(m.time, 'sleep', lambda delay: pytest.fail('Unexpected retry'))
    assert m.fetch_scoreboard(lambda url: json.dumps(expected).encode(), 'scoreboard') == expected

"""Provider-boundary regressions; no user credentials or external model calls."""

from __future__ import annotations

import json
import importlib
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace

import pytest
import requests
from openai_codex.generated.v2_all import (
    GetAccountResponse,
    ErrorNotification,
    ItemCompletedNotification,
    TurnCompletedNotification,
)
from openai_codex.models import Notification
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

codex_provider = importlib.import_module("codex_provider")
Config = importlib.import_module("config").Config
LLMService = importlib.import_module("utils").LLMService


def message(text: str, phase: str = "final_answer") -> Notification:
    return Notification(
        "item/completed",
        ItemCompletedNotification.model_validate({
            "threadId": "thread", "turnId": "turn", "completedAtMs": 1,
            "item": {"id": "answer", "type": "agentMessage", "text": text, "phase": phase},
        }),
    )


def completed(status: str = "completed") -> Notification:
    return Notification(
        "turn/completed",
        TurnCompletedNotification.model_validate({
            "threadId": "thread", "turn": {"id": "turn", "status": status, "items": []},
        }),
    )


class FakeClient:
    def __init__(self, events):
        self.events = iter(events)
        self.closed = Event()
        self.authenticated = True
        self.thread_params = None
        self.model_reads = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.closed.set()

    def initialize(self):
        return None

    def account_read(self, params):
        return GetAccountResponse.model_validate({
            "account": {"type": "chatgpt", "email": None, "planType": "plus"}
            if self.authenticated else None,
            "requiresOpenaiAuth": True,
        })

    def model_list(self):
        self.model_reads += 1
        return SimpleNamespace(data=[SimpleNamespace(model="account-default", is_default=True)])

    def thread_start(self, params):
        self.thread_params = params
        return SimpleNamespace(thread=SimpleNamespace(id="thread"))

    def turn_start(self, thread_id, user):
        return SimpleNamespace(turn=SimpleNamespace(id="turn"))

    def register_turn_notifications(self, turn_id):
        return None

    def unregister_turn_notifications(self, turn_id):
        return None

    def next_turn_notification(self, turn_id):
        return next(self.events)


@pytest.fixture
def client(monkeypatch):
    fake = FakeClient([message("commentary", "commentary"), message("answer"), completed()])
    monkeypatch.setattr(codex_provider, "CodexClient", lambda config: fake)
    return fake


def test_completion_returns_final_answer_without_stream_duplication(client):
    result = codex_provider.complete([{"role": "user", "content": "input"}], "auto")
    assert result == "answer"
    assert client.thread_params["model"] == "account-default"
    assert client.thread_params["environments"] == []
    assert client.closed.is_set()


def test_explicit_model_does_not_use_catalog_default(client):
    codex_provider.complete([{"role": "user", "content": "input"}], "explicit-model")
    assert client.thread_params["model"] == "explicit-model"
    assert client.model_reads == 0


@pytest.mark.parametrize("status", ["failed", "interrupted"])
def test_failed_turn_rejects_partial_output(client, status):
    client.events = iter([message("partial"), completed(status)])
    with pytest.raises(codex_provider.CodexCompletionError):
        codex_provider.complete([{"role": "user", "content": "input"}], "auto")
    assert client.closed.is_set()


def test_empty_completed_turn_is_not_success(client):
    client.events = iter([completed()])
    with pytest.raises(codex_provider.CodexCompletionError):
        codex_provider.complete([{"role": "user", "content": "input"}], "auto")


def test_terminal_error_event_rejects_partial_output(client):
    error = ErrorNotification.model_validate({
        "threadId": "thread", "turnId": "turn", "willRetry": False,
        "error": {"message": "upstream failure"},
    })
    client.events = iter([message("partial"), Notification("error", error)])
    with pytest.raises(codex_provider.CodexCompletionError):
        codex_provider.complete([{"role": "user", "content": "input"}], "auto")


def test_api_key_account_does_not_satisfy_subscription_authentication(client):
    client.account_read = lambda params: GetAccountResponse.model_validate({
        "account": {"type": "apiKey"}, "requiresOpenaiAuth": True,
    })
    with pytest.raises(codex_provider.CodexCompletionError):
        codex_provider.complete([{"role": "user", "content": "input"}], "auto")
    assert client.thread_params is None


def test_missing_authentication_does_not_start_a_thread(client):
    client.authenticated = False
    with pytest.raises(codex_provider.CodexCompletionError):
        codex_provider.complete([{"role": "user", "content": "input"}], "auto")
    assert client.thread_params is None
    assert client.closed.is_set()


def test_timeout_closes_runtime_and_rejects_partial_output(client, monkeypatch):
    def blocked(turn_id):
        assert client.closed.wait(timeout=2)
        raise RuntimeError("transport closed")

    client.next_turn_notification = blocked
    monkeypatch.setenv("FOAMAGENT_HTTP_TIMEOUT", "0.01")
    with pytest.raises(requests.exceptions.Timeout):
        codex_provider.complete([{"role": "user", "content": "input"}], "auto")
    assert client.closed.is_set()


def test_structured_output_validates_actual_completed_content(client):
    class Count(BaseModel):
        count: int

    client.events = iter([message('{"count":42}'), completed()])
    service = LLMService(Config(model_version="explicit-model"))
    result = service.invoke("input", pydantic_obj=Count)
    assert result.count == 42


def test_public_completion_preserves_existing_whitespace_normalisation(client):
    client.events = iter([message("\n  answer  \n"), completed()])
    service = LLMService(Config(model_version="explicit-model"))
    assert service.invoke("input") == "answer"


@pytest.mark.parametrize(
    ("provider", "expected"),
    [("openai-codex", "auto"), ("openai", "gpt-5-mini"), ("anthropic", "gpt-5.3-codex")],
)
def test_implicit_model_matches_selected_provider(monkeypatch, provider, expected):
    monkeypatch.delenv("FOAMAGENT_MODEL_PROVIDER", raising=False)
    monkeypatch.delenv("FOAMAGENT_MODEL_VERSION", raising=False)
    assert Config(model_provider=provider).model_version == expected


def test_explicit_model_override_is_preserved(monkeypatch):
    monkeypatch.delenv("FOAMAGENT_MODEL_PROVIDER", raising=False)
    monkeypatch.setenv("FOAMAGENT_MODEL_VERSION", "env-model")
    assert Config(model_version="programmatic-model").model_version == "env-model"


def test_api_key_provider_performs_real_sdk_http_call(monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            body = json.dumps({
                "id": "chatcmpl-qa", "object": "chat.completion", "created": 1,
                "model": payload["model"],
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "API_OK"},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args):
            return None

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            monkeypatch.setenv("OPENAI_API_KEY", "local-fixture-key")
            monkeypatch.setenv("OPENAI_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
            monkeypatch.setenv("FOAMAGENT_MODEL_PROVIDER", "openai")
            monkeypatch.setenv("FOAMAGENT_MODEL_VERSION", "gpt-4o")
            service = LLMService(Config())
            assert service.invoke("Return the test response") == "API_OK"
        finally:
            server.shutdown()
            thread.join(timeout=2)
            assert not thread.is_alive()

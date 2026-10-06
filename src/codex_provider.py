"""Completion-only access through the official Codex app-server SDK."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TypedDict
from typing_extensions import override

import requests
from openai_codex import CodexConfig
from openai_codex.client import CodexClient
from openai_codex.generated.v2_all import (
    AgentMessageThreadItem,
    ErrorNotification,
    GetAccountParams,
    ItemCompletedNotification,
    TurnCompletedNotification,
    TurnStatus,
)


class Message(TypedDict):
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class CodexCompletionError(RuntimeError):
    detail: str

    @override
    def __str__(self) -> str:
        return self.detail


def complete(messages: list[Message], model: str) -> str:
    """Run one isolated turn, consuming its stream through successful completion."""
    timeout = float(os.environ.get("FOAMAGENT_HTTP_TIMEOUT", "300"))
    if not 0 < timeout < float("inf"):
        raise CodexCompletionError("FOAMAGENT_HTTP_TIMEOUT must be finite and positive.")
    overrides = (
        "mcp_servers={}", 'web_search="disabled"', "project_doc_max_bytes=0",
        "include_environment_context=false", "include_permissions_instructions=false",
        "include_collaboration_mode_instructions=false", "include_apps_instructions=false",
        "tools.update_plan.enabled=false", "tools.experimental_request_user_input.enabled=false",
    ) + tuple(f"features.{feature}=false" for feature in (
        "shell_tool", "apps", "plugins", "hooks", "codex_hooks", "memories",
        "memory_tool", "collab", "multi_agent", "multi_agent_v2", "code_mode",
        "code_mode_host", "tool_search", "search_tool", "tool_suggest",
        "image_generation", "imagegenext", "request_permissions",
        "request_permissions_tool", "send_user_message_async", "deferred_executor",
    ))
    with TemporaryDirectory(prefix="foamagent-codex-") as cwd:
        sdk_config = CodexConfig(
            cwd=cwd, config_overrides=overrides,
            client_name="foamagent", client_title="Foam-Agent", client_version="2.0.0",
        )
        # Closing the SDK before joining the worker releases blocked stream readers.
        with ThreadPoolExecutor(max_workers=1) as executor, CodexClient(sdk_config) as client:
            pending = executor.submit(_complete, client, messages, model)
            try:
                return pending.result(timeout=timeout)
            except TimeoutError as exc:
                raise requests.exceptions.Timeout(
                    f"Codex completion exceeded FOAMAGENT_HTTP_TIMEOUT={timeout:g}s."
                ) from exc


def _complete(
    client: CodexClient, messages: list[Message], model: str,
) -> str:
    _ = client.initialize()
    account = client.account_read(GetAccountParams(refresh_token=True)).account
    if account is None or account.root.type != "chatgpt":
        raise CodexCompletionError(
            "Subscription access requires ChatGPT sign-in. Run `python -m src.codex_auth login` and complete browser authorization; use FOAMAGENT_MODEL_PROVIDER=openai for API-key access."
        )
    if model == "auto":
        models = client.model_list().data
        model = next((item.model for item in models if item.is_default), "")
        if not model:
            raise CodexCompletionError("No default model is available for this ChatGPT account.")
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    user = "\n\n".join(m["content"] for m in messages if m["role"] == "user")
    instructions = Path(__file__).with_name("codex_instructions_default.txt").read_text(
        encoding="utf-8"
    )
    started = client.thread_start({
        "model": model, "modelProvider": "openai",
        "baseInstructions": instructions, "developerInstructions": system,
        "ephemeral": True, "approvalPolicy": "never", "sandbox": "read-only",
        # No environment means no shell, file, patch, or environment tools.
        "environments": [], "dynamicTools": [],
    })
    turn = client.turn_start(started.thread.id, user).turn
    final = ""
    client.register_turn_notifications(turn.id)
    try:
        while True:
            payload = client.next_turn_notification(turn.id).payload
            match payload:
                case ItemCompletedNotification():
                    item = payload.item.root
                    match item:
                        case AgentMessageThreadItem():
                            if item.phase is None or item.phase.value == "final_answer":
                                final = item.text
                        case _:
                            if item.type not in {"userMessage", "reasoning"}:
                                raise CodexCompletionError(
                                    f"Unexpected Codex item in completion-only mode: {item.type}"
                                )
                case TurnCompletedNotification():
                    if payload.turn.status != TurnStatus.completed:
                        detail = payload.turn.error.message if payload.turn.error else payload.turn.status.value
                        raise CodexCompletionError(f"Codex turn did not complete: {detail}")
                    if not final:
                        raise CodexCompletionError("Codex completed without an assistant response.")
                    return final
                case ErrorNotification():
                    if not payload.will_retry:
                        raise CodexCompletionError(payload.error.message)
                case _:
                    continue
    finally:
        client.unregister_turn_notifications(turn.id)

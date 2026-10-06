"""Manage Codex authentication without exposing stored credentials."""

from __future__ import annotations

import argparse
import sys
import webbrowser
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Literal
from typing_extensions import assert_never

from openai_codex import Codex
from openai_codex.errors import CodexError
from openai_codex.types import GetAccountResponse


class AuthArguments(argparse.Namespace):
    command: Literal["status", "models", "login"] = "status"
    device_code: bool = False
    open_browser: bool = False
    timeout: float = 300


def auth_mode(account: GetAccountResponse) -> str:
    """Return only the authentication mode, never account details."""
    if account.account is None:
        return "unauthenticated"
    mode = account.account.root.type
    match mode:
        case "chatgpt":
            return "chatgpt"
        case "apiKey":
            return "api-key"
        case "amazonBedrock":
            return "amazon-bedrock"
    assert_never(mode)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Codex SDK authentication and model discovery (no token output)."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    _ = commands.add_parser("status", help="Print the current authentication mode")
    _ = commands.add_parser("models", help="Print model identifiers from the SDK catalog")
    login_parser = commands.add_parser("login", help="Reuse authentication or sign in with ChatGPT")
    _ = login_parser.add_argument("--device-code", action="store_true", help="Use device authorization")
    _ = login_parser.add_argument("--open-browser", action="store_true", help="Also open the login URL")
    _ = login_parser.add_argument(
        "--timeout", type=float, default=300,
        help="Maximum seconds to wait for authorization (default: 300)",
    )
    args = AuthArguments()
    _ = parser.parse_args(namespace=args)
    if args.command == "login" and not 0 < args.timeout < float("inf"):
        login_parser.error("--timeout must be a finite positive number")

    try:
        # Close the runtime before joining a waiter interrupted by timeout or Ctrl-C.
        with ThreadPoolExecutor(max_workers=1) as waiter, Codex() as codex:
            account = codex.account(refresh_token=True)
            mode = auth_mode(account)
            match args.command:
                case "status":
                    print(mode)
                case "models":
                    for model in codex.models().data:
                        print(model.model)
                case "login":
                    if mode == "chatgpt":
                        print(f"Already authenticated ({mode}); reusing the existing session.")
                        return 0
                    if args.device_code:
                        login = codex.login_chatgpt_device_code()
                        url = login.verification_url
                        print(
                            f"Open {url}\nEnter code: {login.user_code}\nSign in with your ChatGPT account and approve device access.",
                            flush=True,
                        )
                    else:
                        login = codex.login_chatgpt()
                        url = login.auth_url
                        print(
                            f"Open {url}\nSign in with your ChatGPT account and approve Codex access; finish the browser redirect.",
                            flush=True,
                        )
                    print(f"Waiting up to {args.timeout:g} seconds for authorization.", flush=True)
                    if args.open_browser:
                        _ = webbrowser.open(url)
                    if not waiter.submit(login.wait).result(timeout=args.timeout).success:
                        print("Authorization did not succeed. Run login again to retry.", file=sys.stderr)
                        return 1
                    print(f"Authenticated ({auth_mode(codex.account(refresh_token=True))}).")
        return 0
    except TimeoutError:
        print("Authorization timed out. Run login again when ready.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Authorization interrupted.", file=sys.stderr)
        return 130
    except (CodexError, OSError, RuntimeError):
        print(
            "Codex SDK request failed. Check the SDK/runtime installation and network; use status before attempting login.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

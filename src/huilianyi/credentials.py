"""Composable credential providers shared by the Skill and MCP server."""

from __future__ import annotations

import getpass
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

import keyring

from .exceptions import ErrorCode, HuilianyiError


SERVICE_NAME = "codex-huilianyi-reimbursement"


def default_config_path() -> Path:
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        base = Path(os.environ["LOCALAPPDATA"])
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "Codex" / "huilianyi-reimbursement" / "credentials.json"


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str


class CredentialProvider(Protocol):
    def load(self) -> Credentials | None: ...


class EnvironmentCredentialProvider:
    def load(self) -> Credentials | None:
        username = os.environ.get("HUILIANYI_USERNAME", "").strip()
        password = os.environ.get("HUILIANYI_PASSWORD", "")
        return Credentials(username, password) if username and password else None


class CredentialStore:
    def __init__(self, config_path: str | Path | None = None, keyring_backend=keyring):
        self.config_path = Path(config_path) if config_path else default_config_path()
        self.keyring = keyring_backend

    def saved_username(self) -> str | None:
        if not self.config_path.exists():
            return None
        value = json.loads(self.config_path.read_text(encoding="utf-8"))
        username = str(value.get("username") or "").strip()
        return username or None

    def load(self) -> Credentials | None:
        username = self.saved_username()
        password = self.keyring.get_password(SERVICE_NAME, username) if username else None
        return Credentials(username, password) if username and password else None

    def save(self, username: str, password: str) -> Credentials:
        username = username.strip()
        if not username or not password:
            raise ValueError("Huilianyi account and password cannot be blank")
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.keyring.set_password(SERVICE_NAME, username, password)
        self.config_path.write_text(
            json.dumps({"username": username}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return Credentials(username, password)

    def prompt_and_save(
        self,
        validate: Callable[[str, str], None] | None = None,
        input_fn: Callable[[str], str] = input,
        password_fn: Callable[[str], str] = getpass.getpass,
    ) -> Credentials:
        username = input_fn("Huilianyi account: ").strip()
        password = password_fn("Huilianyi password: ")
        if validate:
            validate(username, password)
        return self.save(username, password)

    def resolve(
        self,
        username: str | None = None,
        validate: Callable[[str, str], None] | None = None,
        password_fn: Callable[[str], str] = getpass.getpass,
    ) -> Credentials:
        saved = self.load()
        if saved and (not username or saved.username == username):
            return saved
        if username:
            password = password_fn("Huilianyi password: ")
            if validate:
                validate(username, password)
            return self.save(username, password)
        return self.prompt_and_save(validate=validate, password_fn=password_fn)


class ChainedCredentialProvider:
    def __init__(self, *providers: CredentialProvider):
        self.providers = providers

    def load(self) -> Credentials:
        for provider in self.providers:
            credentials = provider.load()
            if credentials:
                return credentials
        raise HuilianyiError(ErrorCode.AUTH_REQUIRED, "no Huilianyi credentials are configured")


def default_provider() -> ChainedCredentialProvider:
    return ChainedCredentialProvider(EnvironmentCredentialProvider(), CredentialStore())

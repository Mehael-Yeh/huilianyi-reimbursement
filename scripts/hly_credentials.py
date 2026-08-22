#!/usr/bin/env python3
"""Backward-compatible imports for the reusable credential providers."""

from pathlib import Path
import sys

src = Path(__file__).resolve().parents[1] / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

from huilianyi.credentials import (  # noqa: E402,F401
    ChainedCredentialProvider,
    CredentialStore,
    Credentials,
    EnvironmentCredentialProvider,
    SERVICE_NAME,
    default_config_path,
    default_provider,
)

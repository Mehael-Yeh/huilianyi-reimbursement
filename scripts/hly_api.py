#!/usr/bin/env python3
"""Backward-compatible imports for the reusable :mod:`huilianyi` SDK."""

from pathlib import Path
import sys

src = Path(__file__).resolve().parents[1] / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

from huilianyi.auth import PUBLIC_KEY_B64, _rsa_encrypt, login  # noqa: E402,F401
from huilianyi.client import Client, clients_from_auth, unwrap_row, unwrap_rows  # noqa: E402,F401
from huilianyi.exceptions import HuilianyiError  # noqa: E402

HLYError = HuilianyiError

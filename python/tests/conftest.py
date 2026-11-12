from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session", autouse=True)
def fac_binary() -> Path:
    """Tests drive the repo's debug build unless FACTOBOT_FAC says otherwise."""
    fac = Path(os.environ.setdefault("FACTOBOT_FAC", str(REPO / "target" / "debug" / "fac")))
    if not fac.exists():
        pytest.fail(f"{fac} missing; run `cargo build` (mise run test does)")
    return fac

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator

import httpx
import pytest


@pytest.fixture(scope="session")
def mock_http_stack() -> Iterator[str]:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(  # noqa: S603 - fixed interpreter/module arguments
        [sys.executable, "-m", "breakfuser.mock_servers", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 10
        while True:
            try:
                response = httpx.get(f"{base}/health", timeout=0.2)
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                if time.time() > deadline:
                    raise
                time.sleep(0.05)
        yield base
    finally:
        process.terminate()
        process.wait(timeout=5)


@pytest.fixture
def live_mock_environment(mock_http_stack: str, monkeypatch) -> str:
    monkeypatch.setenv("BREAKFUSER_MODE", "live")
    monkeypatch.setenv("BREAKFUSER_LOCAL_BASE_URL", f"{mock_http_stack}/local/v1")
    monkeypatch.setenv("BREAKFUSER_SMART_BASE_URL", f"{mock_http_stack}/smart/v1")
    monkeypatch.setenv("BREAKFUSER_DECIDER_ENDPOINT", f"{mock_http_stack}/decisions")
    return mock_http_stack


@pytest.fixture
def fusion_api_server(mock_http_stack: str) -> Iterator[tuple[str, str]]:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    api_key = "e2e-synthetic-server-key"
    environment = os.environ.copy()
    environment.update(
        {
            "BREAKFUSER_MODE": "live",
            "BREAKFUSER_USE_DECIDER": "false",
            "BREAKFUSER_LOCAL_BASE_URL": f"{mock_http_stack}/local/v1",
            "BREAKFUSER_SMART_BASE_URL": f"{mock_http_stack}/smart/v1",
            "BREAKFUSER_LOCAL_MODEL": "e2e-uncensored",
            "BREAKFUSER_SMART_MODEL": "e2e-smart",
            "BREAKFUSER_SERVER_API_KEY": api_key,
        }
    )
    process = subprocess.Popen(  # noqa: S603 - fixed interpreter/module arguments
        [
            sys.executable,
            "-m",
            "breakfuser.cli",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 10
        while True:
            try:
                response = httpx.get(f"{base}/health", timeout=0.2)
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                if time.time() > deadline:
                    raise
                time.sleep(0.05)
        yield base, api_key
    finally:
        process.terminate()
        process.wait(timeout=5)

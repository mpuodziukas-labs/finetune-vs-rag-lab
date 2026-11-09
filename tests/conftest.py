"""Network guard: no test may open a connection to a non-loopback address."""

import socket
from collections.abc import Iterator
from typing import Any

import pytest

_LOOPBACK = ("127.0.0.1", "::1", "localhost")


@pytest.fixture(autouse=True)
def _no_external_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    real_connect = socket.socket.connect

    def guarded(self: socket.socket, address: Any) -> None:
        if self.family in (socket.AF_INET, socket.AF_INET6) and address[0] not in _LOOPBACK:
            raise AssertionError(f"test tried to reach {address[0]}: tests must not use the network")
        real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)
    yield

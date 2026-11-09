"""Name -> factory registries. New datasets/models/adapters/retrievers register themselves
(in a plugin module listed under `plugins:` in the config) with no edit to core code."""

from collections.abc import Callable
from typing import Any


class Registry:
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self._items: dict[str, Any] = {}

    def register(self, name: str) -> Callable[[Any], Any]:
        def deco(obj: Any) -> Any:
            if name in self._items:
                raise KeyError(f"{self.kind} '{name}' already registered")
            self._items[name] = obj
            return obj

        return deco

    def get(self, name: str) -> Any:
        if name not in self._items:
            raise KeyError(f"unknown {self.kind} '{name}'; known: {sorted(self._items)}")
        return self._items[name]

    def names(self) -> list[str]:
        return sorted(self._items)


DATASETS = Registry("dataset")
MODELS = Registry("model")
ADAPTERS = Registry("adapter")
RETRIEVERS = Registry("retriever")

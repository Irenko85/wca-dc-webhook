from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from importlib.resources import files
from typing import Any


@dataclass(frozen=True)
class MessageCatalog:
    language: str
    _messages: dict[str, str]

    @classmethod
    def load(cls, language: str) -> MessageCatalog:
        if language not in {"en", "es"}:
            raise ValueError(f"Unsupported notification language: {language}")
        resource = files("wca_notifier").joinpath("locales", f"{language}.json")
        messages = json.loads(resource.read_text(encoding="utf-8"))
        return cls(language=language, _messages=messages)

    def keys(self) -> set[str]:
        return set(self._messages)

    def __iter__(self) -> Iterator[str]:
        return iter(self._messages)

    def template(self, key: str) -> str:
        return self._messages[key]

    def text(self, key: str, **values: Any) -> str:
        return self.template(key).format(**values)

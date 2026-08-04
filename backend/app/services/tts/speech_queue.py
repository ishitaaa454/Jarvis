"""Bounded speech utterance queue for ordered welcome sequences."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SpeechUtterance:
    index: int
    total: int
    text: str
    sequence: str = "welcome"


@dataclass
class SpeechSequence:
    name: str
    utterances: list[SpeechUtterance] = field(default_factory=list)


class SpeechQueueFull(Exception):
    pass


class SpeechQueue:
    """Thread-safe bounded queue preserving utterance order."""

    def __init__(self, maxsize: int = 5) -> None:
        self._maxsize = maxsize
        self._lock = threading.Lock()
        self._items: list[SpeechUtterance] = []
        self._active_sequence: str | None = None
        self._current: SpeechUtterance | None = None

    @property
    def active_sequence(self) -> str | None:
        with self._lock:
            return self._active_sequence

    @property
    def current(self) -> SpeechUtterance | None:
        with self._lock:
            return self._current

    def is_busy(self) -> bool:
        with self._lock:
            return self._active_sequence is not None or bool(self._items) or self._current is not None

    def begin_sequence(self, sequence: SpeechSequence) -> None:
        with self._lock:
            if self._active_sequence is not None or self._items or self._current is not None:
                raise RuntimeError("A speech sequence is already active")
            if len(sequence.utterances) > self._maxsize:
                raise SpeechQueueFull("Speech queue capacity exceeded")
            self._active_sequence = sequence.name
            self._items = list(sequence.utterances)
            self._current = None

    def pop_next(self) -> SpeechUtterance | None:
        with self._lock:
            if not self._items:
                self._current = None
                return None
            self._current = self._items.pop(0)
            return self._current

    def mark_idle(self) -> None:
        with self._lock:
            self._active_sequence = None
            self._current = None
            self._items.clear()

    def cancel(self) -> list[SpeechUtterance]:
        with self._lock:
            remaining = list(self._items)
            if self._current is not None:
                remaining.insert(0, self._current)
            self._items.clear()
            self._current = None
            self._active_sequence = None
            return remaining

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "active_sequence": self._active_sequence,
                "queued": len(self._items),
                "current_index": self._current.index if self._current else None,
            }

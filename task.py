import PyQt5.QtCore as C
from typing import Any, Callable, Dict, List, Optional, Tuple


class Interrupted(Exception):
    pass


class Task:
    def __init__(self, task: Callable[..., None]):
        self.task = task
        self._next: Optional[Tuple[Tuple[Any, ...], Dict[str, Any]]] = None
        self._running = False
        self._interrupted = False

    def is_running(self) -> bool:
        return self._running

    def _check(self) -> None:
        if self._interrupted:
            raise Interrupted()
        C.QCoreApplication.processEvents()

    def run(self, *args: Any, **kwargs: Any) -> None:
        self._next = (args, kwargs)
        if self._running:
            self.interrupt()
            return
        self._running = True
        try:
            while self._next is not None:
                current_args, current_kwargs = self._next
                self._next = None
                try:
                    self.task(self._check, *current_args, **current_kwargs)
                except Interrupted:
                    self._interrupted = False
        finally:
            self._running = False

    def interrupt(self) -> None:
        if self._running:
            self._interrupted = True

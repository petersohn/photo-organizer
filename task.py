import PyQt5.QtCore as C
from typing import Callable


class Interrupted(Exception):
    pass


class Task:
    def __init__(self, task: Callable[[Callable[[], None]], None]):
        self.task = task
        self._should_run = False
        self._running = False
        self._interrupted = False

    def is_running(self) -> bool:
        return self._running

    def _check(self) -> None:
        C.QCoreApplication.processEvents()
        if self._interrupted:
            raise Interrupted()

    def run(self) -> None:
        self._should_run = True
        if self._running:
            self.interrupt()
            return
        self._running = True
        try:
            while self._should_run:
                self._should_run = False
                try:
                    self.task(self._check)
                except Interrupted:
                    self._interrupted = False
        finally:
            self._running = False

    def interrupt(self) -> None:
        if self._running:
            self._interrupted = True

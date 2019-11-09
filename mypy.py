from typing import Callable


def click_callback(callback: Callable[[], None]) -> Callable[[bool], None]:
    def ret(_: bool) -> None:
        callback()
    return ret

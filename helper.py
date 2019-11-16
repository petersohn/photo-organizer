import PyQt5.QtWidgets as W
from typing import Union


def set_tooltip(button: Union[W.QAbstractButton, W.QAction]) -> None:
    button.setToolTip('{} ({})'.format(
        button.text(), button.shortcut().toString()))

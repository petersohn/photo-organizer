import PyQt6.QtWidgets as W
import PyQt6.QtGui as G


def set_tooltip(button: W.QAbstractButton | G.QAction) -> None:
    button.setToolTip(
        "{} ({})".format(button.text(), button.shortcut().toString())
    )

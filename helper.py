import PyQt5.QtWidgets as W


def set_tooltip(button: W.QAbstractButton | W.QAction) -> None:
    button.setToolTip(
        "{} ({})".format(button.text(), button.shortcut().toString())
    )

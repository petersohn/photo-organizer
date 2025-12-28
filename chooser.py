import PyQt6.QtWidgets as W
import config


def choose_directory(
    parent: W.QWidget,
    title: str,
    dir_config: str,
    starting_dir: str | None = None,
) -> str | None:
    dialog = W.QFileDialog(parent, title)
    if starting_dir is None:
        starting_dir = config.config.get(dir_config)
    if starting_dir is not None:
        dialog.setDirectory(starting_dir)
    dialog.setNameFilters(["Images (*.jpeg *.jpg *.jpe *.png", "All Files (*)"])
    dialog.setFileMode(W.QFileDialog.FileMode.Directory)
    res = dialog.exec()
    if res != W.QDialog.DialogCode.Accepted:
        return None

    path = dialog.selectedFiles()[0]
    config.config[dir_config] = path
    config.save_config()
    return path

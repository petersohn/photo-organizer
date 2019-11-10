import sys
import os
import PyQt5.QtWidgets as W
import PyQt5.QtGui as G
import PyQt5.QtCore as C
import exifread
import shutil
# import pprint
from typing import Any, Callable, cast, Dict, List, Optional, Set

import apply
import chooser
import config
import task


orientations: Dict[int, G.QTransform] = {
    2: G.QTransform(-1, 0, 0, 1, 0, 0),
    3: G.QTransform(-1, 0, 0, -1, 0, 0),
    4: G.QTransform(1, 0, 0, -1, 0, 0),
    5: G.QTransform(0, 1, 1, 0, 0, 0),
    6: G.QTransform(0, 1, -1, 0, 0, 0),
    7: G.QTransform(0, -1, -1, 0, 0, 0),
    8: G.QTransform(0, -1, 1, 0, 0, 0),
}

picture_size_step = 10
picture_load_step = picture_size_step * 2


class ModelItem(G.QStandardItem):
    def __init__(self, filename: str):
        self.filename = filename
        super(ModelItem, self).__init__(os.path.basename(filename))

    def resize(self, size: int) -> None:
        actual_size: Optional[C.QSize] = None
        if self.icon() is not None:
            actual_size = self.icon().actualSize(C.QSize(size, size))
        if actual_size is None or (
                actual_size.width() < size and actual_size.height() < size):
            self.setIcon(self._create_icon(size))

    def _create_icon(self, size: int) -> G.QIcon:
        with open(self.filename, 'rb') as f:
            exif = exifread.process_file(f, details=False)
        orientation = exif.get('Image Orientation')

        result = G.QPixmap(self.filename)
        if result.width() > size or result.height() > size:
            result = result.scaled(
                size + picture_load_step, size + picture_load_step,
                C.Qt.KeepAspectRatio, C.Qt.SmoothTransformation)
        if orientation is not None:
            transform = orientations.get(
                cast(List[int], orientation.values)[0])
            if transform is not None:
                result = result.transformed(transform)
        return G.QIcon(result)


class InitEvent(C.QEvent):
    EventType: Optional[int] = None

    def __init__(self, paths: List[str]):
        if InitEvent.EventType is None:
            InitEvent.EventType = C.QEvent.registerEventType()
        self.paths = paths
        super(InitEvent, self).__init__(
            cast(C.QEvent.Type, InitEvent.EventType))


class OverrideCursor:
    def __init__(self, cursor: G.QCursor):
        self.cursor = cursor

    def __enter__(self) -> None:
        G.QGuiApplication.setOverrideCursor(self.cursor)

    def __exit__(self, *args: Any) -> None:
        G.QGuiApplication.restoreOverrideCursor()


class MainWindow(W.QMainWindow):
    def __init__(self, paths: List[str]) -> None:
        super(MainWindow, self).__init__()
        self.setWindowTitle('Photo Organizer')
        self.resize(config.config['width'], config.config['height'])
        if config.config['maximized']:
            self.setWindowState(C.Qt.WindowMaximized)
        self.picture_size = config.config['picture_size']

        self.loaded_files: Set[str] = set()

        self.mime_db = C.QMimeDatabase()

        self.from_model = G.QStandardItemModel()
        self.from_list = W.QListView()
        self.from_list.setViewMode(W.QListView.IconMode)
        self.from_list.setMovement(W.QListView.Static)
        self.from_list.setResizeMode(W.QListView.Adjust)
        self.from_list.setSelectionMode(W.QAbstractItemView.ExtendedSelection)
        self.from_list.setModel(self.from_model)
        sm = self.from_list.selectionModel()
        sm.selectionChanged.connect(  # type: ignore
            lambda s, d: self.check_from_selection())

        self.to_model = G.QStandardItemModel()
        self.to_list = W.QListView()
        self.to_list.setViewMode(W.QListView.IconMode)
        self.to_list.setMovement(W.QListView.Static)
        self.to_list.setResizeMode(W.QListView.Adjust)
        self.to_list.setSelectionMode(W.QAbstractItemView.ExtendedSelection)
        self.to_list.setModel(self.to_model)
        self.to_list.selectionModel().selectionChanged.connect(  # type: ignore
            lambda s, d: self.check_to_selection())

        move_layout = W.QVBoxLayout()

        self.add_button = W.QToolButton()
        self.add_button.setArrowType(C.Qt.RightArrow)
        self.add_button.clicked.connect(lambda _: self.add_items())
        self.add_button.setEnabled(False)
        self.remove_button = W.QToolButton()
        self.remove_button.setArrowType(C.Qt.LeftArrow)
        self.remove_button.clicked.connect(lambda _: self.remove_items())
        self.remove_button.setEnabled(False)
        move_layout.addWidget(self.add_button)
        move_layout.addWidget(self.remove_button)

        arrange_layout = W.QVBoxLayout()
        self.up_button = W.QToolButton()
        self.up_button.setArrowType(C.Qt.UpArrow)
        self.up_button.clicked.connect(lambda _: self.move_up())
        self.up_button.setEnabled(False)
        self.down_button = W.QToolButton()
        self.down_button.setArrowType(C.Qt.DownArrow)
        self.down_button.clicked.connect(lambda _: self.move_down())
        self.down_button.setEnabled(False)
        arrange_layout.addWidget(self.up_button)
        arrange_layout.addWidget(self.down_button)

        splitter = W.QSplitter()

        from_layout = W.QHBoxLayout()
        from_layout.addWidget(self.from_list)
        from_layout.addLayout(move_layout)
        from_widget = W.QWidget()
        from_widget.setLayout(from_layout)
        splitter.addWidget(from_widget)

        to_layout = W.QHBoxLayout()
        to_layout.addWidget(self.to_list)
        to_layout.addLayout(arrange_layout)
        to_widget = W.QWidget()
        to_widget.setLayout(to_layout)
        splitter.addWidget(to_widget)

        self.setCentralWidget(splitter)

        toolbar = W.QToolBar()
        toolbar.addAction('Add', lambda: self.add_dir(recursive=False))
        toolbar.addAction('Add tree', lambda: self.add_dir(recursive=True))
        toolbar.addSeparator()
        toolbar.addAction('+', lambda: self.resize_pictures(
            self.picture_size + picture_size_step))
        toolbar.addAction('-', lambda: self.resize_pictures(
            self.picture_size - picture_size_step))
        toolbar.addSeparator()
        self.apply_action = toolbar.addAction('Apply', self.apply)
        self.apply_action.setEnabled(False)
        self.addToolBar(toolbar)

        self.load_pictures_task = task.Task(self.load_pictures)
        C.QCoreApplication.postEvent(self, InitEvent(paths))

    def resizeEvent(self, event: G.QResizeEvent) -> None:
        super(MainWindow, self).resizeEvent(event)
        maximized = self.isMaximized()
        config.config['maximized'] = maximized
        if not maximized:
            config.config['width'] = self.width()
            config.config['height'] = self.height()
        config.save_config()

    def closeEvent(self, event: G.QCloseEvent) -> None:
        self.load_pictures_task.interrupt()
        super(MainWindow, self).closeEvent(event)

    def resize_pictures(self, size: int) -> None:
        self.picture_size = size
        config.config['picture_size'] = size
        config.save_config()
        self.load_pictures_task.run()

    def load_pictures(self, check: Callable[[], None]) -> None:
        separation = 10
        self.from_list.setIconSize(
            C.QSize(self.picture_size, self.picture_size))
        self.from_list.setGridSize(C.QSize(
            self.picture_size + separation, self.picture_size + separation))
        self.from_list.setMinimumWidth(self.picture_size + separation * 2)

        self.to_list.setIconSize(C.QSize(self.picture_size, self.picture_size))
        self.to_list.setGridSize(C.QSize(
            self.picture_size + separation, self.picture_size + separation))
        self.to_list.setMinimumWidth(self.picture_size + separation * 2)

        with OverrideCursor(G.QCursor(C.Qt.BusyCursor)):
            for i in range(self.from_model.rowCount()):
                cast(ModelItem, self.from_model.item(i, 0)).resize(
                    self.picture_size)
                check()
            for i in range(self.to_model.rowCount()):
                cast(ModelItem, self.to_model.item(i, 0)).resize(
                    self.picture_size)
                check()

    def event(self, event: C.QEvent) -> bool:
        if cast(int, event.type()) == InitEvent.EventType:
            init_event = cast(InitEvent, event)
            self.load_pictures_task.run()
            for path in init_event.paths:
                self._add_dir(path, recursive=True)
            self.load_pictures_task.run()
            return True
        return super(MainWindow, self).event(event)

    def _get_selected_items(self, view: W.QListView) -> List[int]:
        return [
            index.row() for index in
            view.selectionModel().selectedIndexes()]

    def _select_next(
            self, view: W.QListView, sorted_rows: List[int]) -> None:
        if not sorted_rows:
            return
        next_row = sorted_rows[0] - len(sorted_rows) + 1
        row_count = view.model().rowCount()
        if next_row >= row_count:
            next_row = row_count - 1
        view.setCurrentIndex(view.model().index(next_row, 0))

    def add_items(self) -> None:
        rows = self._get_selected_items(self.from_list)
        for row in rows:
            item = self.from_model.takeItem(row, 0)
            self.to_model.appendRow(item)
        rows.sort(reverse=True)
        for row in rows:
            self.from_model.removeRow(row)
        self._select_next(self.from_list, rows)
        self.check_from_selection()
        self.check_to_selection()
        self.check_to_items()
        self.load_pictures_task.run()

    def remove_items(self) -> None:
        rows = self._get_selected_items(self.to_list)
        rows.sort(reverse=True)
        for row in rows:
            item = self.to_model.takeItem(row, 0)
            self.to_model.removeRow(row)
            self.from_model.appendRow(item)
        self._select_next(self.to_list, rows)
        self.from_model.sort(0)
        self.check_from_selection()
        self.check_to_selection()
        self.check_to_items()
        self.load_pictures_task.run()

    def _take_to_items(self, first: int, last: int) -> List[G.QStandardItem]:
        result = [self.to_model.takeItem(row, 0)
                  for row in range(first, last)]
        self.to_model.removeRows(first, last - first)
        return result

    def _move(self, rows: List[int], diff: int) -> None:
        for row in rows:
            item = self.to_model.takeItem(row, 0)
            self.to_model.removeRow(row)
            self.to_model.insertRow(row + diff, item)
        selection = C.QItemSelection()
        for row in rows:
            index = self.to_model.index(row + diff, 0)
            selection.select(index, index)
        self.to_list.selectionModel().select(
            selection, C.QItemSelectionModel.ClearAndSelect)
        self.load_pictures_task.run()

    def move_up(self) -> None:
        selection = self._get_selected_items(self.to_list)
        selection.sort()
        self._move(selection, -1)

    def move_down(self) -> None:
        selection = self._get_selected_items(self.to_list)
        selection.sort(reverse=True)
        self._move(selection, 1)

    def check_to_items(self) -> None:
        has_items = self.to_model.rowCount() != 0
        self.apply_action.setEnabled(has_items)

    def check_to_selection(self) -> None:
        selection = self._get_selected_items(self.to_list)
        has_selection = len(selection) != 0
        self.up_button.setEnabled(has_selection and min(selection) != 0)
        self.down_button.setEnabled(
            has_selection and max(selection) != self.to_model.rowCount() - 1)
        self.remove_button.setEnabled(has_selection)

    def check_from_selection(self) -> None:
        self.add_button.setEnabled(
            len(self.from_list.selectionModel().selectedIndexes()) != 0)

    def apply(self) -> None:
        dialog = apply.ApplyDialog(self)
        res = dialog.exec()
        if res != W.QDialog.Accepted:
            return

        target_directory = dialog.get_target_directory()
        prefix = dialog.get_prefix()
        number = dialog.get_starting_number()
        decimals = dialog.get_decimals()
        copy = dialog.is_copy()
        os.makedirs(target_directory, exist_ok=True)
        while self.to_model.rowCount() != 0:
            path = cast(ModelItem, self.to_model.item(0)).filename
            extension = path[path.rfind('.'):]
            numstr = str(number)
            numstr = '0' * (max(0, decimals - len(numstr))) + numstr
            new_path = os.path.join(target_directory, '{}{}{}'.format(
                prefix, numstr, extension))
            if copy:
                shutil.copy(path, new_path)
            else:
                os.rename(path, new_path)
            number += 1
            self.to_model.removeRow(0)
            self.loaded_files.remove(path)
        self.check_to_items()
        self.check_to_selection()
        self.load_pictures_task.run()

    def _is_allowed(self, filename: str) -> bool:
        mime_type = self.mime_db.mimeTypeForFile(filename)
        return mime_type.inherits('image/jpeg') or \
            mime_type.inherits('image/png')

    def _get_files(self, path: str, recursive: bool) -> List[str]:
        result: List[str] = []
        dirs: List[str] = []
        with os.scandir(path) as it:
            for entry in it:
                if self._is_allowed(entry.name) and entry.is_file():
                    file_path = os.path.join(path, entry.name)
                    if file_path not in self.loaded_files:
                        result.append(file_path)
                result.sort()
                if recursive and entry.is_dir() and \
                        entry != '' and not entry.name.startswith('.'):
                    dirs.append(os.path.join(path, entry.name))
        result.sort()
        for dir in dirs:
            result.extend(self._get_files(dir, recursive))
        return result

    def _add_dir(self, path: str, recursive: bool) -> None:
        path = os.path.abspath(path)
        images = self._get_files(path, recursive)
        for image in images:
            self.from_model.appendRow([ModelItem(image)])
            self.loaded_files.add(image)

    def add_dir(self, recursive: bool) -> None:
        title = 'Add tree' if recursive else 'Add directory'
        path = chooser.choose_directory(self, title, 'last_dir')
        if path is None:
            return
        self._add_dir(path, recursive)
        self.load_pictures_task.run()


if __name__ == '__main__':
    config.load_config()

    app = W.QApplication([])

    window = MainWindow(sys.argv[1:])
    window.show()

    app.exec_()

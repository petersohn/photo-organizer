import sys
import os
import PyQt5.QtWidgets as W
import PyQt5.QtGui as G
import PyQt5.QtCore as C
import exifread
import pprint
from typing import Any, cast, Dict, List, Optional, Tuple

import config


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
    def __init__(self, filename: str, size: int):
        self.filename = filename
        super(ModelItem, self).__init__(
            self._create_icon(size), os.path.basename(filename))

    def resize(self, size: int) -> None:
        actual_size = self.icon().actualSize(C.QSize(size, size))
        if actual_size.width() < size and actual_size.height() < size:
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

    def __init__(self, path: str):
        if InitEvent.EventType is None:
            InitEvent.EventType = C.QEvent.registerEventType()
        self.path = path
        super(InitEvent, self).__init__(
            cast(C.QEvent.Type, InitEvent.EventType))


def is_allowed(name: str) -> bool:
    for ex in ['.jpg', '.jpeg', '.png', '.bmp']:
        if name.lower().endswith(ex):
            return True
    return False


class MainWindow(W.QMainWindow):
    def __init__(self, path: str) -> None:
        super(MainWindow, self).__init__()
        self.setWindowTitle("Photo Organizer")
        self.resize(config.config['width'], config.config['height'])
        if config.config['maximized']:
            self.setWindowState(C.Qt.WindowMaximized)
        self.picture_size = config.config['picture_size']

        self.gui_disabled = 0

        self.from_model = G.QStandardItemModel()
        self.from_list = W.QListView()
        self.from_list.setViewMode(W.QListView.IconMode)
        self.from_list.setMovement(W.QListView.Static)
        self.from_list.setResizeMode(W.QListView.Adjust)
        self.from_list.setSelectionMode(W.QAbstractItemView.ExtendedSelection)
        self.from_list.setModel(self.from_model)
        self.from_list.selectionModel().selectionChanged.connect(  # type: ignore
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
        move_widget = W.QWidget()
        move_widget.setLayout(move_layout)

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
        arrange_widget = W.QWidget()
        arrange_widget.setLayout(arrange_layout)

        splitter = W.QSplitter()

        from_layout = W.QHBoxLayout()
        from_layout.addWidget(self.from_list)
        from_layout.addWidget(move_widget)
        from_widget = W.QWidget()
        from_widget.setLayout(from_layout)
        splitter.addWidget(from_widget)

        to_layout = W.QHBoxLayout()
        to_layout.addWidget(self.to_list)
        to_layout.addWidget(arrange_widget)
        to_widget = W.QWidget()
        to_widget.setLayout(to_layout)
        splitter.addWidget(to_widget)

        self.setCentralWidget(splitter)

        toolbar = W.QToolBar()
        toolbar.addAction('+', lambda: self.resize_pictures(
            self.picture_size + picture_size_step))
        toolbar.addAction('-', lambda: self.resize_pictures(
            self.picture_size - picture_size_step))
        toolbar.addAction('Apply', self.apply)
        self.addToolBar(toolbar)

        C.QCoreApplication.postEvent(self, InitEvent(path))

    def resizeEvent(self, event: G.QResizeEvent) -> None:
        super(MainWindow, self).resizeEvent(event)
        maximized = self.isMaximized()
        config.config['maximized'] = maximized
        if not maximized:
            config.config['width'] = self.width()
            config.config['height'] = self.height()
        config.save_config()

    class GuiDisabler:
        def __init__(self, obj: 'MainWindow'):
            self.obj = obj

        def __enter__(self) -> None:
            if self.obj.gui_disabled == 0:
                self.obj.add_button.setEnabled(False)
                self.obj.remove_button.setEnabled(False)
                self.obj.up_button.setEnabled(False)
                self.obj.down_button.setEnabled(False)
                G.QGuiApplication.setOverrideCursor(G.QCursor(C.Qt.BusyCursor))
            self.obj.gui_disabled += 1

        def __exit__(self, *args: Any) -> None:
            assert self.obj.gui_disabled > 0
            self.obj.gui_disabled -= 1
            if self.obj.gui_disabled == 0:
                self.obj.check_to_selection()
                self.obj.check_from_selection()
                G.QGuiApplication.restoreOverrideCursor()

    def disable_gui(self) -> GuiDisabler:
        return self.GuiDisabler(self)

    def resize_pictures(self, size: int) -> None:
        separation = 10
        self.from_list.setIconSize(C.QSize(size, size))
        self.from_list.setGridSize(
            C.QSize(size + separation, size + separation))
        self.from_list.setMinimumWidth(size + separation * 2)

        self.to_list.setIconSize(C.QSize(size, size))
        self.to_list.setGridSize(
            C.QSize(size + separation, size + separation))
        self.to_list.setMinimumWidth(size + separation * 2)

        self.picture_size = size
        config.config['picture_size'] = size
        config.save_config()

        with self.disable_gui():
            for i in range(self.from_model.rowCount()):
                cast(ModelItem, self.from_model.item(i, 0)).resize(size)
                C.QCoreApplication.processEvents()
            for i in range(self.to_model.rowCount()):
                cast(ModelItem, self.to_model.item(i, 0)).resize(size)
                C.QCoreApplication.processEvents()

    def event(self, event: C.QEvent) -> bool:
        if cast(int, event.type()) == InitEvent.EventType:
            init_event = cast(InitEvent, event)
            with self.disable_gui():
                G.QGuiApplication.setOverrideCursor(G.QCursor(C.Qt.WaitCursor))
                self.resize_pictures(self.picture_size)
                self._add_dir(init_event.path)
                G.QGuiApplication.restoreOverrideCursor()
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

    def move_up(self) -> None:
        selection = self._get_selected_items(self.to_list)
        selection.sort()
        self._move(selection, -1)

    def move_down(self) -> None:
        selection = self._get_selected_items(self.to_list)
        selection.sort(reverse=True)
        self._move(selection, 1)

    def check_to_selection(self) -> None:
        if self.gui_disabled != 0:
            return
        selection = self._get_selected_items(self.to_list)
        has_selection = len(selection) != 0
        self.up_button.setEnabled(has_selection and min(selection) != 0)
        self.down_button.setEnabled(
            has_selection and max(selection) != self.to_model.rowCount() - 1)
        self.remove_button.setEnabled(has_selection)

    def check_from_selection(self) -> None:
        if self.gui_disabled != 0:
            return
        self.add_button.setEnabled(
            len(self.from_list.selectionModel().selectedIndexes()) != 0)

    def apply(self) -> None:
        for i in range(self.to_model.rowCount()):
            item = cast(ModelItem, self.to_model.item(i, 0))
            print(item.filename)

    def _add_dir(self, path: str) -> None:
        with os.scandir(sys.argv[1]) as it:
            images = [
                os.path.join(sys.argv[1], entry.name)
                for entry in it if is_allowed(entry.name) and entry.is_file()]
        images.sort()
        with self.disable_gui():
            for image in images:
                self.from_model.appendRow(
                    [ModelItem(image, self.picture_size)])
                W.QApplication.processEvents()


config.load_config()

app = W.QApplication([])

window = MainWindow(sys.argv[1])
window.show()

app.exec_()

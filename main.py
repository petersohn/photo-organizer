import sys
import os
import PyQt6.QtWidgets as W
import PyQt6.QtGui as G
import PyQt6.QtCore as C
import exifread
import shutil
import traceback

# import pprint
from typing import Any, Callable, cast, final, override

import apply
import chooser
import config
import helper
import task


orientations: dict[int, G.QTransform] = {
    2: G.QTransform(-1, 0, 0, 1, 0, 0),
    3: G.QTransform(-1, 0, 0, -1, 0, 0),
    4: G.QTransform(1, 0, 0, -1, 0, 0),
    5: G.QTransform(0, 1, 1, 0, 0, 0),
    6: G.QTransform(0, 1, -1, 0, 0, 0),
    7: G.QTransform(0, -1, -1, 0, 0, 0),
    8: G.QTransform(0, -1, 1, 0, 0, 0),
}


@final
class Exif:
    def __init__(self, filename: str, **kwargs: Any):
        with open(filename, "rb") as f:
            self.data = exifread.process_file(f, **kwargs)

    def get_exif_tag(self, name: str) -> Any:
        tag = self.data.get(name)
        if tag is None:
            return None
        return tag.values

    def get_orientation(self, key: str) -> int | None:
        orientations = self.get_exif_tag(key)
        return orientations[0] if orientations is not None else None

    def is_valid(self) -> bool:
        return len(self.data) != 0


picture_size_step = 10
picture_load_step = picture_size_step * 2


@final
class ModelItem(G.QStandardItem):
    def __init__(
        self,
        filename: str,
        index: int,
        sort_function: "Callable[[ModelItem], Any]",
    ):
        self.sort_function = sort_function
        self.filename = filename
        self.__index = index
        self.__thumbnail_inited = False

        exif = Exif(self.filename, details=False)

        self.__has_exif = exif.is_valid()

        if self.__has_exif:
            self.orientation = exif.get_orientation("Image Orientation")

            date = exif.get_exif_tag("EXIF DateTimeOriginal")
            self.date: str = date if date is not None else ""
        else:
            self.orientation = None
            self.date = ""

        super(ModelItem, self).__init__(os.path.basename(filename))

    def get_index(self) -> int:
        return self.__index

    def resize(self, size: int) -> None:
        self._init_thumbnail()

        actual_size: C.QSize | None = None
        if self.icon() is not None:
            actual_size = self.icon().actualSize(C.QSize(size, size))
        if actual_size is None or (
            actual_size.width() < size and actual_size.height() < size
        ):
            self._create_icon(size)

    def _init_thumbnail(self) -> None:
        if not self.__has_exif or self.__thumbnail_inited:
            return

        exif = Exif(self.filename)

        thumbnail = exif.data.get("JPEGThumbnail")
        if thumbnail is not None:
            try:
                thumbnail_img = G.QPixmap()
                _ = thumbnail_img.loadFromData(cast(bytes, thumbnail))
                self._set_icon(
                    thumbnail_img, exif.get_orientation("Thumbnail Orientation")
                )
            except Exception:
                traceback.print_exc()

        self.__thumbnail_inited = True

    def _set_icon(self, image: G.QPixmap, orientation: int | None) -> None:
        if orientation is not None:
            transform = orientations.get(orientation)
            if transform is not None:
                image = image.transformed(transform)
        self.setIcon(G.QIcon(image))

    def _create_icon(self, size: int) -> None:
        result = G.QPixmap(self.filename)
        if result.width() > size or result.height() > size:
            result = result.scaled(
                size + picture_load_step,
                size + picture_load_step,
                C.Qt.AspectRatioMode.KeepAspectRatio,
                C.Qt.TransformationMode.SmoothTransformation,
            )
        self._set_icon(result, self.orientation)

    @override
    def __lt__(self, other: G.QStandardItem) -> bool:
        if not isinstance(other, ModelItem):
            return NotImplemented
        return self.sort_function(self) < self.sort_function(other)


sort_functions: dict[str, Callable[[ModelItem], Any]] = {
    "index": lambda m: m.get_index(),
    "name": lambda m: (m.text(), m.get_index()),
    "date": lambda m: (m.date, m.get_index()),
    "date_name": lambda m: (m.date, m.text(), m.get_index()),
}


@final
class InitEvent(C.QEvent):
    EventType: int | None = None

    def __init__(self, paths: list[str]):
        if InitEvent.EventType is None:
            InitEvent.EventType = C.QEvent.registerEventType()
        self.paths = paths
        super(InitEvent, self).__init__(
            cast(C.QEvent.Type, InitEvent.EventType)
        )


@final
class OverrideCursor:
    def __init__(self, cursor: G.QCursor):
        self.cursor = cursor

    def __enter__(self) -> None:
        G.QGuiApplication.setOverrideCursor(self.cursor)

    def __exit__(self, *args: Any) -> None:
        G.QGuiApplication.restoreOverrideCursor()


@final
class MainWindow(W.QMainWindow):
    def __init__(self, paths: list[str]) -> None:
        super(MainWindow, self).__init__()
        self.setWindowTitle("Photo Organizer")
        self.resize(config.config["width"], config.config["height"])
        if config.config["maximized"]:
            self.setWindowState(C.Qt.WindowState.WindowMaximized)
        self.picture_size = config.config["picture_size"]

        self.loaded_files: set[str] = set()

        self.mime_db = C.QMimeDatabase()
        self.current_index = 0

        self.from_model = G.QStandardItemModel()
        self.from_list = W.QListView()
        self.from_list.setViewMode(W.QListView.ViewMode.IconMode)
        self.from_list.setMovement(W.QListView.Movement.Static)
        self.from_list.setResizeMode(W.QListView.ResizeMode.Adjust)
        self.from_list.setSelectionMode(
            W.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.from_list.setModel(self.from_model)
        sm = self.from_list.selectionModel()
        assert sm is not None
        _ = sm.selectionChanged.connect(  # type: ignore
            lambda s, d: self.check_from_selection()
        )
        _ = self.from_list.doubleClicked.connect(  # type: ignore
            lambda idx: self.open_file(self.from_model, idx)
        )

        self.to_model = G.QStandardItemModel()
        self.to_list = W.QListView()
        self.to_list.setViewMode(W.QListView.ViewMode.IconMode)
        self.to_list.setMovement(W.QListView.Movement.Static)
        self.to_list.setResizeMode(W.QListView.ResizeMode.Adjust)
        self.to_list.setSelectionMode(
            W.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.to_list.setModel(self.to_model)
        sm = self.to_list.selectionModel()
        assert sm is not None
        _ = sm.selectionChanged.connect(  # type: ignore
            lambda s, d: self.check_to_selection()
        )
        _ = self.to_list.doubleClicked.connect(  # type: ignore
            lambda idx: self.open_file(self.to_model, idx)
        )

        move_layout = W.QVBoxLayout()

        self.add_button = W.QToolButton()
        self.add_button.setText("Add")
        self.add_button.setIcon(config.get_icon("arrow-right-bold"))
        _ = self.add_button.clicked.connect(lambda _: self.add_items())
        self.add_button.setEnabled(False)
        self.add_button.setShortcut(
            G.QKeySequence(C.Qt.Modifier.ALT | C.Qt.Key.Key_Right)
        )
        helper.set_tooltip(self.add_button)
        self.remove_button = W.QToolButton()
        self.remove_button.setText("Remove")
        self.remove_button.setIcon(config.get_icon("arrow-left-bold"))
        _ = self.remove_button.clicked.connect(lambda _: self.remove_items())
        self.remove_button.setEnabled(False)
        self.remove_button.setShortcut(
            G.QKeySequence(C.Qt.Modifier.ALT | C.Qt.Key.Key_Left)
        )
        helper.set_tooltip(self.remove_button)
        move_layout.addWidget(self.add_button)
        move_layout.addWidget(self.remove_button)

        arrange_layout = W.QVBoxLayout()
        self.up_button = W.QToolButton()
        self.up_button.setText("Up")
        self.up_button.setIcon(config.get_icon("arrow-up-bold"))
        _ = self.up_button.clicked.connect(lambda _: self.move_up())
        self.up_button.setEnabled(False)
        self.up_button.setShortcut(
            G.QKeySequence(C.Qt.Modifier.ALT | C.Qt.Key.Key_Up)
        )
        self.down_button = W.QToolButton()
        self.down_button.setText("Down")
        self.down_button.setIcon(config.get_icon("arrow-down-bold"))
        _ = self.down_button.clicked.connect(lambda _: self.move_down())
        self.down_button.setEnabled(False)
        self.down_button.setShortcut(
            G.QKeySequence(C.Qt.Modifier.ALT | C.Qt.Key.Key_Down)
        )
        helper.set_tooltip(self.down_button)
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

        self.current_sort_function = config.config.get("sort_function", "index")

        def create_sort_action(name: str, text: str) -> G.QAction:
            action = G.QAction(text)
            action.setCheckable(True)
            action.setChecked(name == self.current_sort_function)
            action.setData(name)
            return action

        sort_actions = G.QActionGroup(self)
        _ = sort_actions.addAction(create_sort_action("index", "None"))
        _ = sort_actions.addAction(create_sort_action("name", "File name"))
        _ = sort_actions.addAction(create_sort_action("date", "EXIF date"))
        _ = sort_actions.addAction(
            create_sort_action("date_name", "EXIF date or file name")
        )
        _ = sort_actions.triggered.connect(
            lambda action: self.set_sort(cast(str, action.data()))
        )

        sort_menu = W.QMenu()
        sort_menu.addActions(sort_actions.actions())

        toolbar = W.QToolBar()
        clear_action = toolbar.addAction(
            config.get_icon("close-circle-outline"), "Clear", self.clear
        )
        assert clear_action is not None
        clear_action.setShortcut(
            G.QKeySequence(C.Qt.Modifier.ALT | C.Qt.Key.Key_C)
        )
        helper.set_tooltip(clear_action)
        _ = toolbar.addSeparator()
        add_action = toolbar.addAction(
            config.get_icon("folder"),
            "Add folder",
            lambda: self.add_dir(recursive=False),
        )
        assert add_action is not None
        add_action.setShortcut(
            G.QKeySequence(C.Qt.Modifier.ALT | C.Qt.Key.Key_F)
        )
        helper.set_tooltip(add_action)
        _ = toolbar.addAction(
            config.get_icon("file-tree"),
            "Add tree",
            lambda: self.add_dir(recursive=True),
        )
        _ = toolbar.addSeparator()
        _ = toolbar.addAction(
            config.get_icon("sort"),
            "Sort input",
            lambda: sort_menu.popup(G.QCursor.pos()),
        )
        _ = toolbar.addSeparator()
        zoom_in_action = toolbar.addAction(
            config.get_icon("magnify-plus"),
            "Zoom in",
            lambda: self.resize_pictures(self.picture_size + picture_size_step),
        )
        assert zoom_in_action is not None
        zoom_in_action.setShortcut(
            G.QKeySequence(C.Qt.Modifier.CTRL | C.Qt.Key.Key_Plus)
        )
        helper.set_tooltip(zoom_in_action)
        zoom_out_action = toolbar.addAction(
            config.get_icon("magnify-minus"),
            "Zoom out",
            lambda: self.resize_pictures(self.picture_size - picture_size_step),
        )
        assert zoom_out_action is not None
        zoom_out_action.setShortcut(
            G.QKeySequence(C.Qt.Modifier.CTRL | C.Qt.Key.Key_Minus)
        )
        helper.set_tooltip(zoom_out_action)
        _ = toolbar.addSeparator()
        aa = toolbar.addAction(config.get_icon("floppy"), "Apply", self.apply)
        assert aa is not None
        aa.setEnabled(False)
        self.addToolBar(toolbar)
        aa.setShortcut(G.QKeySequence(C.Qt.Modifier.ALT | C.Qt.Key.Key_A))
        helper.set_tooltip(aa)
        self.apply_action = aa

        self.load_pictures_task = task.Task(self.load_pictures)
        C.QCoreApplication.postEvent(self, InitEvent(paths))

    def clear(self) -> None:
        message_box = W.QMessageBox(
            W.QMessageBox.Icon.Question,
            "Clear items",
            "Do you really want to remove all items? Files on the disk will "
            "not be deleted.",
            parent=self,
        )
        _ = message_box.addButton(
            "Clear only unsorted", W.QMessageBox.ButtonRole.YesRole
        )
        _ = message_box.addButton(
            "Clear everything", W.QMessageBox.ButtonRole.AcceptRole
        )
        _ = message_box.addButton(
            "Clear all", W.QMessageBox.ButtonRole.RejectRole
        )
        _ = message_box.exec()

        result = message_box.buttonRole(message_box.clickedButton())

        if result == W.QMessageBox.ButtonRole.RejectRole:
            return

        if result == W.QMessageBox.ButtonRole.YesRole:
            for row in range(self.from_model.rowCount()):
                self.loaded_files.remove(
                    cast(ModelItem, self.from_model.item(row)).filename
                )
            self.from_model.clear()
        elif result == W.QMessageBox.ButtonRole.AcceptRole:
            self.from_model.clear()
            self.to_model.clear()
            self.loaded_files.clear()
            self.current_index = 0
            self.check_to_selection()
            self.check_to_items()

        self.check_from_selection()
        self.save_items()

    @override
    def resizeEvent(self, event: G.QResizeEvent | None) -> None:
        super(MainWindow, self).resizeEvent(event)
        maximized = self.isMaximized()
        config.config["maximized"] = maximized
        if not maximized:
            config.config["width"] = self.width()
            config.config["height"] = self.height()
        config.save_config()

    @override
    def closeEvent(self, event: G.QCloseEvent | None) -> None:
        assert event is not None
        if self.to_model.rowCount() != 0:
            result = W.QMessageBox.question(
                self, "Exit program", "Do you really want to quit?"
            )
            if result != W.QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self.load_pictures_task.interrupt()
        super(MainWindow, self).closeEvent(event)

    def resize_pictures(self, size: int) -> None:
        self.picture_size = size
        config.config["picture_size"] = size
        config.save_config()
        self.load_pictures_task.run()

    def _set_view_size(self, view: W.QListView) -> None:
        separation = 10
        font_metrics = G.QFontMetrics(view.font())
        view.setIconSize(C.QSize(self.picture_size, self.picture_size))
        view.setGridSize(
            C.QSize(
                self.picture_size + separation,
                self.picture_size + separation + font_metrics.height(),
            )
        )
        view.setMinimumWidth(self.picture_size + separation * 2)

    def load_pictures(self, check: Callable[[], None]) -> None:
        self._set_view_size(self.from_list)
        self._set_view_size(self.to_list)

        with OverrideCursor(G.QCursor(C.Qt.CursorShape.BusyCursor)):
            for i in range(self.from_model.rowCount()):
                cast(ModelItem, self.from_model.item(i, 0)).resize(
                    self.picture_size
                )
                check()
            for i in range(self.to_model.rowCount()):
                cast(ModelItem, self.to_model.item(i, 0)).resize(
                    self.picture_size
                )
                check()

    @override
    def event(self, event: C.QEvent | None) -> bool:
        assert event is not None
        if cast(int, event.type()) == InitEvent.EventType:
            init_event = cast(InitEvent, event)
            self.init(init_event)
            return True
        return super(MainWindow, self).event(event)

    def _create_model_item(self, filename: str, index: int) -> ModelItem:
        def sort_function(item: ModelItem) -> Any:
            return sort_functions[self.current_sort_function](item)

        return ModelItem(filename, index, sort_function)

    def init(self, init_event: InitEvent) -> None:
        def add_item(model: G.QStandardItemModel, item: Any) -> None:
            filename = item["filename"]
            index = item["index"]
            model.appendRow([self._create_model_item(filename, index)])
            self.current_index = max(self.current_index, index + 1)
            self.loaded_files.add(filename)

        if init_event.paths:
            for path in init_event.paths:
                self._add_dir(path, recursive=True)
            self.save_items()
        elif "items" in config.config:
            items = config.config["items"]
            for item in items["from"]:
                add_item(self.from_model, item)
            for item in items["to"]:
                add_item(self.to_model, item)
            self.check_to_items()
        else:
            self.load_pictures_task.run()
            return

        self.from_model.sort(0)
        self.load_pictures_task.run()

    def _get_selected_items(self, view: W.QListView) -> list[int]:
        model = view.selectionModel()
        assert model is not None
        return [index.row() for index in model.selectedIndexes()]

    def _select_next(self, view: W.QListView, sorted_rows: list[int]) -> None:
        if not sorted_rows:
            return
        next_row = sorted_rows[0] - len(sorted_rows) + 1
        model = view.model()
        assert model is not None
        row_count = model.rowCount()
        if next_row >= row_count:
            next_row = row_count - 1
        view.setCurrentIndex(model.index(next_row, 0))

    def add_items(self) -> None:
        rows = self._get_selected_items(self.from_list)
        to_rows = self._get_selected_items(self.to_list)
        for row in rows:
            item = self.from_model.takeItem(row, 0)
            if to_rows:
                self.to_model.insertRow(to_rows[0], item)
            else:
                self.to_model.appendRow(item)
        rows.sort(reverse=True)
        for row in rows:
            _ = self.from_model.removeRow(row)
        self._select_next(self.from_list, rows)
        self.check_from_selection()
        self.check_to_selection()
        self.check_to_items()
        self.save_items()
        self.load_pictures_task.run()

    def remove_items(self) -> None:
        rows = self._get_selected_items(self.to_list)
        rows.sort(reverse=True)
        for row in rows:
            item = self.to_model.takeItem(row, 0)
            _ = self.to_model.removeRow(row)
            self.from_model.appendRow(item)
        self._select_next(self.to_list, rows)
        self.from_model.sort(0)
        self.check_from_selection()
        self.check_to_selection()
        self.check_to_items()
        self.save_items()
        self.load_pictures_task.run()

    def set_sort(self, name: str) -> None:
        self.current_sort_function = name
        self.from_model.sort(0)
        config.config["sort_function"] = name
        config.save_config()
        self.load_pictures_task.run()

    def _take_to_items(self, first: int, last: int) -> list[G.QStandardItem]:
        def func(row: int) -> G.QStandardItem:
            res = self.to_model.takeItem(row, 0)
            assert res is not None
            return res

        result = [func(row) for row in range(first, last)]
        _ = self.to_model.removeRows(first, last - first)
        return result

    def _move(self, rows: list[int], diff: int) -> None:
        for row in rows:
            item = self.to_model.takeItem(row, 0)
            _ = self.to_model.removeRow(row)
            self.to_model.insertRow(row + diff, item)
        selection = C.QItemSelection()
        for row in rows:
            index = self.to_model.index(row + diff, 0)
            selection.select(index, index)
            self.to_list.scrollTo(index)

        sm = self.to_list.selectionModel()
        assert sm is not None
        sm.select(selection, C.QItemSelectionModel.SelectionFlag.ClearAndSelect)
        self.load_pictures_task.run()

    def move_up(self) -> None:
        selection = self._get_selected_items(self.to_list)
        selection.sort()
        self._move(selection, -1)
        self.save_items()

    def move_down(self) -> None:
        selection = self._get_selected_items(self.to_list)
        selection.sort(reverse=True)
        self._move(selection, 1)
        self.save_items()

    def check_to_items(self) -> None:
        has_items = self.to_model.rowCount() != 0
        self.apply_action.setEnabled(has_items)

    def check_to_selection(self) -> None:
        selection = self._get_selected_items(self.to_list)
        has_selection = len(selection) != 0
        self.up_button.setEnabled(has_selection and min(selection) != 0)
        self.down_button.setEnabled(
            has_selection and max(selection) != self.to_model.rowCount() - 1
        )
        self.remove_button.setEnabled(has_selection)

    def save_items(self) -> None:
        def convert(item: G.QStandardItem | None) -> Any:
            assert item is not None
            item_ = cast(ModelItem, item)
            return {"filename": item_.filename, "index": item_.get_index()}

        def get_items(model: G.QStandardItemModel) -> list[Any]:
            return [convert(model.item(row)) for row in range(model.rowCount())]

        config.config["items"] = {
            "from": get_items(self.from_model),
            "to": get_items(self.to_model),
        }
        config.save_config()

    def check_from_selection(self) -> None:
        sm = self.from_list.selectionModel()
        assert sm is not None
        self.add_button.setEnabled(len(sm.selectedIndexes()) != 0)

    def apply(self) -> None:
        dialog = apply.ApplyDialog(self)
        res = dialog.exec()
        if res != W.QDialog.DialogCode.Accepted:
            return

        target_directory = dialog.get_target_directory()
        prefix = dialog.get_prefix()
        number = dialog.get_starting_number()
        decimals = dialog.get_decimals()
        copy = dialog.is_copy()
        os.makedirs(target_directory, exist_ok=True)
        while self.to_model.rowCount() != 0:
            path = cast(ModelItem, self.to_model.item(0)).filename
            extension = path[path.rfind(".") :]
            numstr = str(number)
            numstr = "0" * (max(0, decimals - len(numstr))) + numstr
            new_path = os.path.join(
                target_directory, "{}{}{}".format(prefix, numstr, extension)
            )
            if copy:
                _ = shutil.copy(path, new_path)
            else:
                os.rename(path, new_path)
            number += 1
            _ = self.to_model.removeRow(0)
            self.loaded_files.remove(path)
        self.check_to_items()
        self.check_to_selection()
        self.save_items()
        self.load_pictures_task.run()

    def _is_allowed(self, filename: str) -> bool:
        mime_type = self.mime_db.mimeTypeForFile(filename)
        return mime_type.inherits("image/jpeg") or mime_type.inherits(
            "image/png"
        )

    def _get_files(self, path: str, recursive: bool) -> list[str]:
        result: list[str] = []
        dirs: list[str] = []
        with os.scandir(path) as it:
            for entry in it:
                if self._is_allowed(entry.name) and entry.is_file():
                    file_path = os.path.join(path, entry.name)
                    if file_path not in self.loaded_files:
                        result.append(file_path)
                result.sort()
                if (
                    recursive
                    and entry.is_dir()
                    and entry != ""
                    and not entry.name.startswith(".")
                ):
                    dirs.append(os.path.join(path, entry.name))
        result.sort()
        for dir in dirs:
            result.extend(self._get_files(dir, recursive))
        return result

    def _add_dir(self, path: str, recursive: bool) -> None:
        path = os.path.abspath(path)
        images = self._get_files(path, recursive)
        for image in images:
            self.from_model.appendRow(
                [self._create_model_item(image, self.current_index)]
            )
            self.current_index += 1
            self.loaded_files.add(image)

    def add_dir(self, recursive: bool) -> None:
        title = "Add tree" if recursive else "Add directory"
        path = chooser.choose_directory(self, title, "last_dir")
        if path is None:
            return
        self._add_dir(path, recursive)
        self.save_items()
        self.load_pictures_task.run()

    def open_file(
        self, model: G.QStandardItemModel, idx: C.QModelIndex
    ) -> None:
        item = cast(ModelItem, model.itemFromIndex(idx))
        try:
            os.startfile(item.filename)  # type: ignore
        except Exception as e:
            print(e, file=sys.stderr)


if __name__ == "__main__":
    config.load_config()

    app = W.QApplication([])

    window = MainWindow(sys.argv[1:])
    window.show()

    sys.exit(app.exec())

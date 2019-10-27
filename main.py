import sys
import os
import PyQt5.QtWidgets as W
import PyQt5.QtGui as G
import PyQt5.QtCore as C
import exifread
import pprint
from typing import List, cast, Optional, Dict


orientations: Dict[int, G.QTransform] = {
    2: G.QTransform(-1, 0, 0, 1, 0, 0),
    3: G.QTransform(-1, 0, 0, -1, 0, 0),
    4: G.QTransform(1, 0, 0, -1, 0, 0),
    5: G.QTransform(0, 1, 1, 0, 0, 0),
    6: G.QTransform(0, 1, -1, 0, 0, 0),
    7: G.QTransform(0, -1, -1, 0, 0, 0),
    8: G.QTransform(0, -1, 1, 0, 0, 0),
}


def get_pixmap(filename: str, size: int) -> G.QPixmap:
    print(filename)
    key = filename + '///' + str(size)
    result = cast(Optional[G.QPixmap], G.QPixmapCache.find(key))
    if result is not None:
        return result
    with open(filename, 'rb') as f:
        exif = exifread.process_file(f, details=False)
    orientation = exif.get('Image Orientation')

    result = G.QPixmap(filename).scaled(
        size, size, C.Qt.KeepAspectRatio, C.Qt.SmoothTransformation)
    if orientation is not None:
        transform = orientations.get(cast(List[int], orientation.values)[0])
        if transform is not None:
            result = result.transformed(transform)
    G.QPixmapCache.insert(key, result)
    return result


class ModelItem(G.QStandardItem):
    def __init__(self, filename: str):
        self.filename = filename
        super(ModelItem, self).__init__(
            G.QIcon(get_pixmap(filename, 200)), os.path.basename(filename))


class MainWindow(W.QMainWindow):
    def __init__(self, images: List[str]) -> None:
        super(MainWindow, self).__init__()
        self.setWindowTitle("Photo Organizer")
        self.resize(800, 500)

        self.from_model = G.QStandardItemModel()
        self.from_model.appendColumn(
            ModelItem(filename) for filename in images)
        self.from_list = W.QListView()
        self.from_list.setViewMode(W.QListView.IconMode)
        self.from_list.setMovement(W.QListView.Static)
        self.from_list.setResizeMode(W.QListView.Adjust)
        self.from_list.setSelectionMode(W.QAbstractItemView.ExtendedSelection)
        self.from_list.setModel(self.from_model)
        self.from_list.setIconSize(C.QSize(200, 200))
        self.from_list.setMinimumWidth(220)
        self.from_list.setGridSize(C.QSize(210, 210))

        self.to_model = G.QStandardItemModel()
        self.to_list = W.QListView()
        self.to_list.setFlow(W.QListView.TopToBottom)
        self.to_list.setWrapping(False)
        self.to_list.setViewMode(W.QListView.IconMode)
        self.to_list.setMovement(W.QListView.Static)
        self.to_list.setResizeMode(W.QListView.Adjust)
        self.to_list.setSelectionMode(W.QAbstractItemView.ExtendedSelection)
        self.to_list.setModel(self.to_model)
        self.to_list.setIconSize(C.QSize(200, 200))
        self.to_list.setFixedWidth(220)

        move_layout = W.QVBoxLayout()

        add_button = W.QPushButton('->')
        add_button.clicked.connect(lambda _: self.add_items())
        move_layout.addWidget(add_button)

        remove_button = W.QPushButton('<-')
        remove_button.clicked.connect(lambda _: self.remove_items())
        move_layout.addWidget(remove_button)

        apply_button = W.QPushButton('Apply')
        apply_button.clicked.connect(lambda _: self.apply())
        move_layout.addWidget(apply_button)

        move_widget = W.QWidget()
        move_widget.setLayout(move_layout)

        splitter = W.QHBoxLayout()
        splitter.addWidget(self.from_list)
        splitter.addWidget(move_widget)
        splitter.addWidget(self.to_list)
        central_widget = W.QWidget()
        central_widget.setLayout(splitter)
        self.setCentralWidget(central_widget)

    def add_items(self) -> None:
        rows = [
            index.row() for index in
            self.from_list.selectionModel().selectedIndexes()]
        rows.sort(reverse=True)
        for row in rows:
            item = self.from_model.takeItem(row, 0)
            self.from_model.removeRow(row)
            self.to_model.appendRow(item)

    def remove_items(self) -> None:
        rows = [
            index.row() for index in
            self.to_list.selectionModel().selectedIndexes()]
        rows.sort(reverse=True)
        for row in rows:
            item = self.to_model.takeItem(row, 0)
            self.to_model.removeRow(row)
            self.from_model.appendRow(item)
        self.from_model.sort(0)

    def apply(self) -> None:
        for i in range(self.to_model.rowCount()):
            item = cast(ModelItem, self.to_model.item(i, 0))
            print(item.filename)


def is_allowed(name: str) -> bool:
    for ex in ['.jpg', '.jpeg', '.png', '.bmp']:
        if name.endswith(ex):
            return True
    return False


with os.scandir(sys.argv[1]) as it:
    images = [
        os.path.join(sys.argv[1], entry.name)
        for entry in it if is_allowed(entry.name) and entry.is_file()]
images.sort()

app = W.QApplication([])

window = MainWindow(images)
window.show()

app.exec_()

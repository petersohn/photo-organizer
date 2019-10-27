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


class MainWindow(W.QMainWindow):
    def __init__(self, images: List[str]) -> None:
        super(MainWindow, self).__init__()
        self.setWindowTitle("Photo Organizer")
        self.resize(800, 500)
        self.model = G.QStandardItemModel()
        self.model.appendColumn(G.QStandardItem(
            G.QIcon(get_pixmap(filename, 200)),
            os.path.basename(filename)) for filename in images)
        self.from_list = W.QListView()
        self.from_list.setViewMode(W.QListView.IconMode)
        # self.from_list.setFlow(W.QListView.TopToBottom)
        self.from_list.setMovement(W.QListView.Static)
        self.from_list.setResizeMode(W.QListView.Adjust)
        self.from_list.setSelectionMode(W.QAbstractItemView.ExtendedSelection)
        # self.from_list.setWrapping(False)
        self.from_list.setModel(self.model)
        self.from_list.setIconSize(C.QSize(200, 200))
        self.setCentralWidget(self.from_list)


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

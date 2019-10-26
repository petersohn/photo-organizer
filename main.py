import sys
import os
import PyQt5.QtWidgets as W
import PyQt5.QtGui as G
import PyQt5.QtCore as C
from typing import List, cast, Optional


def get_pixmap(filename: str, size: int) -> G.QPixmap:
    print(filename)
    key = filename + '///' + str(size)
    result = G.QPixmapCache.find(key)
    if result is not None:
        return result
    result = G.QPixmap(filename).scaled(size, size, C.Qt.KeepAspectRatio)
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

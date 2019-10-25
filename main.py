import sys
import os
import PyQt5.QtWidgets as W
import PyQt5.QtGui as G
import PyQt5.QtCore as C
from typing import List


def get_pixmap(filename: str, size: int) -> G.QPixmap:
    key = filename + '///' + str(size)
    result = G.QPixmapCache.find(key)
    if result is not None:
        return result
    result = G.QPixmap(filename).scaled(size, size, C.Qt.KeepAspectRatio)
    G.QPixmapCache.insert(key, result)
    return result


class ImageScroller(W.QAbstractScrollArea):
    def __init__(self, size: int, images: List[str]):
        super(ImageScroller, self).__init__()
        self.spacing = 10
        self.image_size = size
        total_size = self.image_size + self.spacing
        self.cols = self.width() // total_size
        h = G.QFontMetrics(W.QLabel('X').font()).height()
        self.rows = self.height() // (total_size + h)
        self.verticalScrollBar().setRange(
            0, max(0, (len(images) // self.cols + 1) - self.rows))
        self.verticalScrollBar().setPageStep(self.rows)
        self.verticalScrollBar().valueChanged.connect(  # type: ignore
            self.redraw)

        self.images = images
        self.setHorizontalScrollBarPolicy(C.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(C.Qt.ScrollBarAsNeeded)
        self.redraw(0)

    def redraw(self, position: int) -> None:
        grid = W.QGridLayout()
        grid.setSpacing(self.spacing)
        print(position)
        for y in range(self.rows):
            for x in range(self.cols):
                idx = (y + position) * self.cols + x
                print('({}, {}) {}: {}'.format(x, y, idx, self.images[idx]))
                image = W.QLabel()
                image.setPixmap(get_pixmap(self.images[idx], self.image_size))
                label = W.QLabel(os.path.basename(self.images[idx]))
                label.setTextFormat(C.Qt.PlainText)
                layout = W.QVBoxLayout()
                layout.addWidget(image)
                layout.addWidget(label)
                # layout.addWidget(label)
                w = W.QWidget()
                w.setLayout(layout)
                grid.addWidget(w, y, x)
        w = W.QWidget()
        w.setLayout(grid)
        self.setViewport(w)


class MainWindow(W.QMainWindow):
    def __init__(self, images: List[str]) -> None:
        super(MainWindow, self).__init__()
        self.setWindowTitle("Photo Organizer")
        self.resize(600, 400)
        self.scroller = ImageScroller(200, images)
        self.setCentralWidget(self.scroller)

        # self.images = images
        # self.label = W.QLabel()
        # btn = W.QPushButton('next')
        # btn.clicked.connect(lambda _: self.increment())  # type: ignore
        # layout = W.QGridLayout()
        # layout.addWidget(self.label, 0, 0)
        # layout.addWidget(btn, 1, 0)
        # widget = W.QWidget()
        # widget.setLayout(layout)
        # self.setCentralWidget(widget)
        # self.idx = 0
        # self.draw()

    # def increment(self) -> None:
    #     self.idx = (self.idx + 1) % len(images)
    #     self.draw()
    #
    # def draw(self) -> None:
    #     print(self.images[self.idx])
    #     self.label.setPixmap(G.QPixmap(
    #         self.images[self.idx]).scaled(200, 200, C.Qt.KeepAspectRatio))


with os.scandir(sys.argv[1]) as it:
    images = [
        os.path.join(sys.argv[1], entry.name)
        for entry in it if entry.is_file()]

app = W.QApplication([])

window = MainWindow(images)
window.show()

app.exec_()

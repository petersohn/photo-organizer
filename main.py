import sys
import os
import PyQt5.QtWidgets as W
import PyQt5.QtGui as G
import PyQt5.QtCore as C
from typing import List, cast, Optional


def get_pixmap(filename: str, size: int) -> G.QPixmap:
    key = filename + '///' + str(size)
    result = G.QPixmapCache.find(key)
    if result is not None:
        return result
    result = G.QPixmap(filename).scaled(size, size, C.Qt.KeepAspectRatio)
    G.QPixmapCache.insert(key, result)
    return result


class RedrawEvent(C.QEvent):
    Type = cast(C.QEvent.Type, C.QEvent.User + 1)

    def __init__(self, position: int):
        super(RedrawEvent, self).__init__(self.Type)
        self.position = position


class ImageScroller(W.QAbstractScrollArea):
    def __init__(self, size: int, images: List[str]):
        super(ImageScroller, self).__init__()
        self.spacing = 10
        self.image_size = size
        self.rows = 0
        self.cols = 0
        self.calculated_size: Optional[C.QSize] = None

        self.images = images
        self.setHorizontalScrollBarPolicy(C.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(C.Qt.ScrollBarAsNeeded)
        self.verticalScrollBar().valueChanged.connect(  # type: ignore
            self.redraw)

    def redraw(self, position: int) -> None:
        print('redraw')
        grid = W.QGridLayout()
        grid.setSpacing(self.spacing)
        print(position)
        for y in range(self.rows):
            for x in range(self.cols):
                idx = (y + position) * self.cols + x
                if idx >= len(self.images):
                    break
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

    def recalculate(self, size: C.QSize) -> None:
        print('recalculate')
        total_size = self.image_size + self.spacing
        cols = size.width() // total_size
        h = G.QFontMetrics(W.QLabel('X').font()).height()
        rows = size.height() // (total_size + h)
        print('{} / ({} + {}) = {}'.format(size.height(), total_size, h, rows))

        current_position = self.verticalScrollBar().sliderPosition()
        position = current_position * self.cols // cols

        self.rows = rows
        self.cols = cols

        self.calculated_size = size

        self.verticalScrollBar().setRange(
            0, max(0, (len(images) // self.cols + 1) - self.rows))
        self.verticalScrollBar().setPageStep(self.rows)
        if position != current_position:
            self.verticalScrollBar().setValue(position)
        else:
            C.QCoreApplication.postEvent(self, RedrawEvent(position))

    def event(self, event: C.QEvent) -> bool:
        if event.type() == RedrawEvent.Type:
            self.redraw(cast(RedrawEvent, event).position)
            return True
        return super(ImageScroller, self).event(event)

    def resizeEvent(self, event: G.QResizeEvent) -> None:
        print('resize: {} -> {}'.format(self.calculated_size, event.size()))
        if self.calculated_size != event.size():
            self.recalculate(event.size())


class MainWindow(W.QMainWindow):
    def __init__(self, images: List[str]) -> None:
        super(MainWindow, self).__init__()
        self.setWindowTitle("Photo Organizer")
        self.resize(800, 500)
        self.scroller = ImageScroller(200, images)
        self.setCentralWidget(self.scroller)


with os.scandir(sys.argv[1]) as it:
    images = [
        os.path.join(sys.argv[1], entry.name)
        for entry in it if entry.is_file()]

app = W.QApplication([])

window = MainWindow(images)
window.show()

app.exec_()

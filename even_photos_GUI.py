import sys
import typing
from PyQt6 import QtCore
from PyQt6.QtGui import *
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
import even_photos_resolve
from python_get_resolve import ResolveConnectionFailed

import signal

from PyQt6.QtWidgets import QWidget

class ResolvePrjCheckerGUI(QWidget):
    def __init__(self):
        super(ResolvePrjCheckerGUI, self).__init__()

        self.initUI()

    def initUI(self):
        self.setWindowTitle('Resolve Project Problem Checker')
        self.setGeometry(300, 300, 400, 200)

        #self.statusBar = QStatusBar()
        #self.setStatusBar(self.statusBar)

        # Create a layout
        layout = QVBoxLayout()

        # Create a button
        self.button = QPushButton('Check for odd resolution photos', self)
        self.button.clicked.connect(self.start_converting_photos)

        # Add widgets to the layout
        layout.addWidget(self.button)
        # layout.addWidget(self.file_list)

        # Set the layout for the main window
        self.setLayout(layout)

    def start_converting_photos(self, checked) -> (bool, list|None):
        try:
            even_photos_resolve.convert_photos_in_media_pool()
            print("hi")
        except ResolveConnectionFailed:
            print("Resolve be closed dog")




        


if __name__ == '__main__':
    # If control-C is sent in terminal, pass to GUI to kill program
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    window = ResolvePrjCheckerGUI()
    window.show()
    sys.exit(app.exec())
    
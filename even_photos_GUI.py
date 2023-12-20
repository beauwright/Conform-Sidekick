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
        self.setWindowTitle('Resolve Odd Resolution Image Replacer')
        self.setGeometry(300, 300, 400, 200)

        # Create a layout
        layout = QVBoxLayout()

        # Create a button
        self.button = QPushButton('Replace odd resolution images', self)
        self.button.clicked.connect(self.start_converting_photos)

        # Add widgets to the layout
        layout.addWidget(self.button)
        # layout.addWidget(self.file_list)

        # Progress Bar
        self.progress_bar = QProgressBar(self)
        layout.addWidget(self.progress_bar)

        # Table for failed conversions
        self.failed_table = QTableWidget(self)
        self.failed_table.setColumnCount(3)  # Filepath and Error Message
        self.failed_table.setHorizontalHeaderLabels(["Name", "File Path", "Error Message"])
        layout.addWidget(self.failed_table)

        # Set the layout for the main window
        self.setLayout(layout)

    def start_converting_photos(self, checked) -> (bool, list|None):
        try:
            even_photos_resolve.convert_photos_in_media_pool()
            print("Photos successfully converted")
        except ResolveConnectionFailed:
            print("Resolve be closed dog")

    def start_converting_photos(self, checked):
        self.thread = ImageConverterThread()
        self.thread.progress_updated.connect(self.update_progress)
        self.thread.conversion_failed.connect(self.log_failure)
        self.thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def log_failure(self, name, file_path, error_message):
        # Add row to table with file_path and error_message
        # Get the current row count
        row_count = self.failed_table.rowCount()

        # Insert a new row at the end of the table
        self.failed_table.insertRow(row_count)

        # Create QTableWidgetItem for each piece of data
        name_item = QTableWidgetItem(name)
        file_path_item = QTableWidgetItem(file_path)
        error_message_item = QTableWidgetItem(error_message)

        # Add the items to the respective columns in the new row
        self.failed_table.setItem(row_count, 0, name_item)
        self.failed_table.setItem(row_count, 1, file_path_item)
        self.failed_table.setItem(row_count, 2, error_message_item)


class ImageConverterThread(QThread):
    progress_updated = pyqtSignal(int)
    conversion_failed = pyqtSignal(str, str, str)
        

    def run(self):
        # Open current Resolve project
        project = even_photos_resolve.get_resolve_current_project()


        # Find the odd res media
        media = even_photos_resolve.get_all_media_paths(project)
        odd_res_media = even_photos_resolve.get_all_odd_resolution_media(media)
        
        count = 0
        # Convert the photos
        for entry in odd_res_media:
            # Try to convert every odd resolution file, replace the MediaPoolItem with the
            # converted one if succesful
            even_photos_resolve.replace_single_odd_resolution_file(entry, odd_res_media[entry])
            count += 1
            self.progress_updated.emit(count // len(odd_res_media)*100)



def main():
    # If control-C is sent in terminal, pass to GUI to kill program
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    window = ResolvePrjCheckerGUI()
    window.show()
    sys.exit(app.exec())       


if __name__ == '__main__':
    main()
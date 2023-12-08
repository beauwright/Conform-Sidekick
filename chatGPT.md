```
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QListWidget, QHBoxLayout, QFileDialog

class FileListApp(QWidget):
    def __init__(self):
        super().__init__()

        self.initUI()

    def initUI(self):
        self.setWindowTitle('File List App')
        self.setGeometry(300, 300, 400, 200)

        # Create a layout
        layout = QVBoxLayout()

        # Create a button
        self.button = QPushButton('Add Files', self)
        self.button.clicked.connect(self.showDialog)

        # Create a list widget
        self.file_list = QListWidget(self)

        # Add widgets to the layout
        layout.addWidget(self.button)
        layout.addWidget(self.file_list)

        # Set the layout for the main window
        self.setLayout(layout)

    def showDialog(self):
        # Open a file dialog to select files
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.ExistingFiles)

        if file_dialog.exec_():
            # Get selected file(s) and add them to the list
            selected_files = file_dialog.selectedFiles()
            self.file_list.addItems(selected_files)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = FileListApp()
    ex.show()
    sys.exit(app.exec_())
```
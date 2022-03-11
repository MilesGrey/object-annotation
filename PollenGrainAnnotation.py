import json
import sys
from pathlib import Path

import pandas as pd
from PyQt6 import QtWidgets
from PyQt6.QtWidgets import QApplication, QDialog, QPushButton, QVBoxLayout, QDialogButtonBox, QLabel, QInputDialog, \
    QHBoxLayout, QListWidget, QFileDialog, QMessageBox

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, \
    NavigationToolbar2QT as NavigationToolbar

import matplotlib.pyplot as plt
from matplotlib import patches
from matplotlib.widgets import RectangleSelector

from process_tif_map import process_probe_directories

POLLEN_CLASSES = [
    'Alnus',
    'Artemisia',
    'Betula',
    'Carpinus',
    'Corylus',
    'Cyperaceae',
    'Fagus',
    'Fraxinus',
    'Juglans',
    'Larix'
    'Papaveraceae',
    'Picea',
    'Pinaceae',
    'Plantago',
    'Platanus',
    'Poaceae',
    'Populus',
    'Rumex',
    'Salix',
    'Taxus',
    'Tilia',
    'Ulmus',
    'Urticaceae',
    'Quercus',
    'Sporen',
    'NoPollen',
    'Varia',
    'Pinus',
    'Acer',
    'Asteraceae',
    'Thalictrum',
    'Cyperacea',
    'Fabaceae',
    'Sambucus',
    'Ambrosia',
    'Tsuga',
    'Juncaceae',
    'Impatiens',
    'Ericaceae',
    'Brassicaceae',
    'Cladosporium',
    'Alternaria',
]


class CloseDialog(QMessageBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setIcon(QMessageBox.Icon.Information)
        self.setText("There are no more images to annotate in the selected directory.")
        self.setWindowTitle("Closing Object Annotation")
        self.setStandardButtons(QMessageBox.StandardButton.Ok)


class Window(QtWidgets.QWidget):
    PROCESSED_FOLDERS_FILE_NAME = 'processed_folder.json'

    def __init__(self, parent=None):
        super(Window, self).__init__(parent)

        self.processing_directory = QFileDialog.getExistingDirectory(self)

        self.figure = plt.figure(figsize=(12.80, 9.60))

        self.canvas = FigureCanvas(self.figure)

        self.image_generator = self.get_image_generator()
        self.crop, self.crop_name, self.bounding_boxes, self.probe_directory_name = None, None, None, None
        self.ax = None
        self.new_bounding_boxes = []
        self.directory_label_info = pd.DataFrame()
        self.processed_folders = self.load_processed_folders()

        self.header = QLabel('')

        NavigationToolbar.toolitems = [
            ('Home', 'Reset original view', 'home', 'home'),
            ('Back', 'Back to previous view', 'back', 'back'),
            ('Forward', 'Forward to next view', 'forward', 'forward'),
            ('Pan', 'Left button pans, Right button zooms\nx/y fixes axis, CTRL fixes aspect', 'move', 'pan'),
            ('Zoom', 'Zoom to rectangle\nx/y fixes axis', 'zoom_to_rect', 'zoom'),
        ]
        self.toolbar = NavigationToolbar(self.canvas, self)

        self.button = QPushButton('Next Image')
        self.button.clicked.connect(self.show_next_image)

        self.new_bounding_boxes_view = QListWidget()
        self.new_bounding_boxes_view.itemSelectionChanged.connect(self.select_current_bounding_box)
        self.new_bounding_boxes_view.itemDoubleClicked.connect(self.delete_bounding_box)

        layout = QVBoxLayout()
        layout.addWidget(self.header)
        row1 = QHBoxLayout()
        row1.addWidget(self.canvas)
        row1.addWidget(self.new_bounding_boxes_view)
        layout.addLayout(row1)
        row2 = QHBoxLayout()
        row2.addWidget(self.toolbar)
        row2.addWidget(self.button)
        layout.addLayout(row2)
        self.setLayout(layout)

        self.show_next_image()

    def get_image_generator(self):
        directories_generator = process_probe_directories(Path(self.processing_directory))
        for crops, crop_names, existing_bounding_boxes, probe_directory_name in directories_generator:
            if probe_directory_name not in self.processed_folders:
                for crop, crop_name, bounding_boxes in zip(crops, crop_names, existing_bounding_boxes):
                    yield crop, crop_name, bounding_boxes, probe_directory_name
                self.persist_new_bounding_boxes()

    def select_current_bounding_box(self):
        index = self.new_bounding_boxes_view.currentRow()
        self.annotate_image(highlighted_index=index)

    def delete_bounding_box(self, item):
        delete_dialog = QDialog()
        delete_dialog.setWindowTitle('Delete Bounding Box')

        q_btn = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel

        delete_dialog.buttonBox = QDialogButtonBox(q_btn)
        delete_dialog.buttonBox.accepted.connect(delete_dialog.accept)
        delete_dialog.buttonBox.rejected.connect(delete_dialog.reject)

        delete_dialog.layout = QVBoxLayout()
        message = QLabel(f'Delete Bounding Box: {item.text()}')
        delete_dialog.layout.addWidget(message)
        delete_dialog.layout.addWidget(delete_dialog.buttonBox)
        delete_dialog.setLayout(delete_dialog.layout)
        if delete_dialog.exec():
            index = self.new_bounding_boxes_view.currentRow()
            self.new_bounding_boxes_view.takeItem(index)
            del self.new_bounding_boxes[index]
            self.annotate_image()

    def line_select_callback(self, click_event, release_event):
        x1, y1 = int(click_event.xdata), int(click_event.ydata)
        x2, y2 = int(release_event.xdata), int(release_event.ydata)
        selected, ok = QInputDialog.getItem(
            self,
            'Annotate Bounding Box',
            'Select pollen class:',
            POLLEN_CLASSES
        )
        if ok:
            new_bounding_box = (x1, y1, x2, y2, selected)
            self.new_bounding_boxes.append(new_bounding_box)
            self.new_bounding_boxes_view.addItem(f'{selected} {x1, y1, x2, y2}')
            toggle_selector.RS.clear()
            self.annotate_image()
            print(f'Adding box at {(x1, y1, x2, y2)} with label {selected}')

    @staticmethod
    def add_bounding_box(bounding_box, label, color, ax):
        width = bounding_box[2] - bounding_box[0]
        height = bounding_box[3] - bounding_box[1]

        rectangle = patches.Rectangle(
            (bounding_box[0], bounding_box[1]),
            width,
            height,
            linewidth=1,
            edgecolor=color,
            facecolor='none'
        )
        label_y = bounding_box[1]
        ax.add_patch(rectangle)
        ax.text(
            bounding_box[0],
            label_y,
            label,
            color='white',
            bbox=dict(facecolor=color, edgecolor=color)
        )

    def annotate_image(self, highlighted_index=None):
        self.figure.clear()

        self.figure.subplots_adjust(bottom=0, top=1, left=0, right=1)

        self.ax = self.figure.add_subplot(111)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.ax.imshow(self.crop, cmap='gray')

        for current_bounding_box, current_label in self.bounding_boxes:
            self.add_bounding_box(current_bounding_box, current_label, 'red', self.ax)
        for index, row in enumerate(self.new_bounding_boxes):
            if index is not None and index == highlighted_index:
                color = 'blue'
            else:
                color = 'green'
            current_bounding_box = row[:4]
            current_label = row[4]
            self.add_bounding_box(current_bounding_box, current_label, color, self.ax)

        toggle_selector.RS = RectangleSelector(self.ax, self.line_select_callback,
                                               useblit=True,
                                               button=[1, 3],  # don't use middle button
                                               minspanx=5, minspany=5,
                                               spancoords='pixels',
                                               interactive=True)
        self.canvas.mpl_connect('key_press_event', toggle_selector)
        self.canvas.draw()

    def show_next_image(self):
        if len(self.new_bounding_boxes) > 0:
            self.save_new_bounding_boxes()
        try:
            self.crop, self.crop_name, self.bounding_boxes, self.probe_directory_name = next(self.image_generator)
            self.header.setText(f'{self.probe_directory_name}/images/{self.crop_name}')
            self.annotate_image()
        except StopIteration:
            CloseDialog().exec()
            sys.exit()

    def save_new_bounding_boxes(self):
        label_info = pd.DataFrame(self.new_bounding_boxes)
        self.new_bounding_boxes = []
        self.new_bounding_boxes_view.clear()
        label_info.insert(0, 'file', f'{self.probe_directory_name}/images/{self.crop_name}')
        self.directory_label_info = pd.concat([self.directory_label_info, label_info])

    def persist_new_bounding_boxes(self):
        self.directory_label_info.to_csv(
            f'{self.processing_directory}/additional_manual_annotations.csv',
            mode='a',
            header=False,
            index=False
        )
        self.directory_label_info = pd.DataFrame()
        self.processed_folders.append(self.probe_directory_name)
        with open(f'{self.processing_directory}/{self.PROCESSED_FOLDERS_FILE_NAME}', 'w') as file:
            json.dump(self.processed_folders, file)

    def load_processed_folders(self):
        try:
            with open(f'{self.processing_directory}/{self.PROCESSED_FOLDERS_FILE_NAME}', 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            print('No processed folders file exists, yet.')
            return []


def toggle_selector(self, event):
    print(' Key pressed.', event.key)
    if event.key in ['Q', 'q'] and self.toggle_selector.RS.active:
        print(' RectangleSelector deactivated.')
        self.toggle_selector.RS.set_active(False)
    if event.key in ['A', 'a'] and not self.toggle_selector.RS.active:
        print(' RectangleSelector activated.')
        self.toggle_selector.RS.set_active(True)


if __name__ == '__main__':
    app = QApplication(sys.argv)

    main = Window()
    main.show()

    sys.exit(app.exec())

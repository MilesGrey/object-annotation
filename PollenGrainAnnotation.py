import glob
import json
import os
import shutil
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path

import numpy as np
import pandas as pd
from PyQt6 import QtWidgets, QtGui
from PyQt6.QtWidgets import QApplication, QDialog, QPushButton, QVBoxLayout, QDialogButtonBox, QLabel, QInputDialog, \
    QHBoxLayout, QListWidget, QFileDialog, QMessageBox

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, \
    NavigationToolbar2QT as NavigationToolbar

import matplotlib.pyplot as plt
from matplotlib import patches
from matplotlib.widgets import RectangleSelector

from process_tif_map import crop_tif_map

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


class BoxesType(Enum):
    MANUAL = 'manual_boxes'
    EXISTING = 'existing_boxes'


class CloseDialog(QMessageBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setIcon(QMessageBox.Icon.Information)
        self.setText("There are no more images to annotate in the selected directory.")
        self.setWindowTitle("Closing Object Annotation")
        self.setStandardButtons(QMessageBox.StandardButton.Ok)


class Window(QtWidgets.QWidget):
    SAVED_STATE_FILE_NAME = 'saved_state.json'
    BACKUP_DIRECTORY = 'backups'
    BACKUP_INTERVAL = 100

    def __init__(self, parent=None):
        super(Window, self).__init__(parent)

        self.backup_counter = 0

        self.current_probe_directory = None
        self.current_crops = None
        self.current_crop_names = None
        self.current_existing_bounding_boxes = None

        self.current_crop_index = 0
        self.current_crop = None
        self.current_crop_name = None
        self.current_crop_existing_boxes = None
        self.current_crop_new_boxes = None

        self.internal_boxes = {}

        self.processing_directory = QFileDialog.getExistingDirectory(self)
        self.probe_directories = next(os.walk(self.processing_directory))[1]
        try:
            self.probe_directories.remove(self.BACKUP_DIRECTORY)
        except ValueError:
            print('No backup directory present.')
        self.probe_directories = sorted(self.probe_directories)
        self.load_state()

        self.figure = plt.figure()

        self.canvas = FigureCanvas(self.figure)

        self.ax = None
        self.header = QLabel('')

        NavigationToolbar.toolitems = [
            ('Home', 'Reset original view', 'home', 'home'),
            ('Back', 'Back to previous view', 'back', 'back'),
            ('Forward', 'Forward to next view', 'forward', 'forward'),
            ('Pan', 'Left button pans, Right button zooms\nx/y fixes axis, CTRL fixes aspect', 'move', 'pan'),
            ('Zoom', 'Zoom to rectangle\nx/y fixes axis', 'zoom_to_rect', 'zoom'),
        ]
        self.toolbar = NavigationToolbar(self.canvas, self)

        self.export_button = QPushButton('Export to CSV')
        self.export_button.setMaximumWidth(100)
        self.export_button.clicked.connect(self.export_csv)

        self.next_button = QPushButton('Next Image')
        self.next_button.clicked.connect(self.show_next_image)

        self.previous_button = QPushButton('Previous Image')
        self.previous_button.clicked.connect(self.show_previous_image)

        self.new_bounding_boxes_view = QListWidget()
        self.new_bounding_boxes_view.setMinimumWidth(200)
        self.new_bounding_boxes_view.itemSelectionChanged.connect(self.select_current_bounding_box)
        self.new_bounding_boxes_view.itemDoubleClicked.connect(self.delete_bounding_box)

        self.existing_bounding_boxes_view = QListWidget()
        self.existing_bounding_boxes_view.setMinimumWidth(200)
        self.existing_bounding_boxes_view.itemSelectionChanged.connect(self.select_current_existing_bounding_box)
        self.existing_bounding_boxes_view.itemDoubleClicked.connect(self.delete_existing_bounding_box)

        layout = QVBoxLayout()
        row0 = QHBoxLayout()
        row0.addWidget(self.header)
        row0.addWidget(self.export_button)
        layout.addLayout(row0)
        row1 = QHBoxLayout()
        row1.addWidget(self.canvas)
        boxes_list_layout = QVBoxLayout()
        boxes_list_layout.addWidget(self.new_bounding_boxes_view)
        boxes_list_layout.addWidget(self.existing_bounding_boxes_view)
        row1.addLayout(boxes_list_layout)
        layout.addLayout(row1)
        row2 = QHBoxLayout()
        row2.addWidget(self.toolbar)
        row2.addWidget(self.previous_button)
        row2.addWidget(self.next_button)
        layout.addLayout(row2)
        self.setLayout(layout)

        self.set_initial_crop()

    def process_probe_directory(self, probe_directory):
        tif_path_string = f'{self.processing_directory}/{probe_directory}/images/{probe_directory}_map.tif'
        tif_path = Path(glob.glob(tif_path_string)[0])
        self.current_crops, self.current_crop_names, self.current_existing_bounding_boxes = crop_tif_map(tif_path)

    def set_initial_crop(self):
        self.process_probe_directory(self.current_probe_directory)
        self.current_crop = self.current_crops[self.current_crop_index]
        self.current_crop_name = self.current_crop_names[self.current_crop_index]
        self.set_crop_bounding_boxes()
        self.set_button_activation()
        self.show_current_crop()

    def set_next_crop(self):
        current_folder_index = self.probe_directories.index(self.current_probe_directory)
        if self.current_crop_index + 1 >= len(self.current_crops):
            if current_folder_index + 1 < len(self.probe_directories):
                self.current_probe_directory = self.probe_directories[current_folder_index + 1]
                self.process_probe_directory(self.current_probe_directory)
                self.current_crop_index = 0
        else:
            self.current_crop_index += 1
        self.current_crop = self.current_crops[self.current_crop_index]
        self.current_crop_name = self.current_crop_names[self.current_crop_index]
        self.set_crop_bounding_boxes()
        self.set_button_activation()

    def set_previous_crop(self):
        current_folder_index = self.probe_directories.index(self.current_probe_directory)
        if self.current_crop_index - 1 < 0:
            if current_folder_index > 0:
                self.current_probe_directory = self.probe_directories[current_folder_index - 1]
                self.process_probe_directory(self.current_probe_directory)
                self.current_crop_index = len(self.current_crops) - 1
        else:
            self.current_crop_index -= 1
        self.current_crop = self.current_crops[self.current_crop_index]
        self.current_crop_name = self.current_crop_names[self.current_crop_index]
        self.set_crop_bounding_boxes()
        self.set_button_activation()

    def set_button_activation(self):
        if self.current_crop_index + 1 < len(self.current_crops) \
                or self.probe_directories.index(self.current_probe_directory) + 1 < len(self.probe_directories):
            self.next_button.setEnabled(True)
        else:
            self.next_button.setEnabled(False)

        if self.current_crop_index > 0 or self.probe_directories.index(self.current_probe_directory) > 0:
            self.previous_button.setEnabled(True)
        else:
            self.previous_button.setEnabled(False)

    def set_crop_bounding_boxes(self):
        try:
            crop_path = self.build_crop_path()
            self.current_crop_new_boxes = self.internal_boxes[crop_path][BoxesType.MANUAL.value]
            self.current_crop_existing_boxes = self.internal_boxes[crop_path][BoxesType.EXISTING.value]
        except KeyError:
            self.current_crop_existing_boxes = self.current_existing_bounding_boxes[self.current_crop_index]
            self.current_crop_new_boxes = []
        existing_labels = [f'{box[1]} {tuple(box[0])}' for box in self.current_crop_existing_boxes]
        new_labels = [f'{box[1]} {tuple(box[0])}' for box in self.current_crop_new_boxes]
        self.existing_bounding_boxes_view.addItems(existing_labels)
        self.new_bounding_boxes_view.addItems(new_labels)

    def build_crop_path(self):
        return f'{self.current_probe_directory}/images/{self.current_crop_name}'

    def select_current_bounding_box(self):
        index = self.new_bounding_boxes_view.currentRow()
        self.annotate_image(highlighted_index=index, highlight_type=BoxesType.MANUAL)

    def select_current_existing_bounding_box(self):
        index = self.existing_bounding_boxes_view.currentRow()
        self.annotate_image(highlighted_index=index, highlight_type=BoxesType.EXISTING)

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
            del self.current_crop_new_boxes[index]
            self.annotate_image()

    def delete_existing_bounding_box(self, item):
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
            index = self.existing_bounding_boxes_view.currentRow()
            self.existing_bounding_boxes_view.takeItem(index)
            del self.current_crop_existing_boxes[index]
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
            new_bounding_box = [[x1, y1, x2, y2], selected]
            self.current_crop_new_boxes.append(new_bounding_box)
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

    def annotate_image(self, highlighted_index=None, highlight_type=None):
        self.figure.clear()

        self.figure.subplots_adjust(bottom=0, top=1, left=0, right=1)

        self.ax = self.figure.add_subplot(111)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.ax.imshow(self.current_crop, cmap='gray')

        for index, (current_bounding_box, current_label) in enumerate(self.current_crop_existing_boxes):
            if index is not None and index == highlighted_index and highlight_type == BoxesType.EXISTING:
                color = 'blue'
            else:
                color = 'red'
            self.add_bounding_box(current_bounding_box, current_label, color, self.ax)
        for index, row in enumerate(self.current_crop_new_boxes):
            if index is not None and index == highlighted_index and highlight_type == BoxesType.MANUAL:
                color = 'blue'
            else:
                color = 'green'
            current_bounding_box = row[0]
            current_label = row[1]
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
        self.existing_bounding_boxes_view.clear()
        self.new_bounding_boxes_view.clear()
        self.save_bounding_boxes()
        # Skip images with no structure.
        while True:
            self.set_next_crop()
            if self.current_crop.min() != self.current_crop.max():
                break
        self.backup_counter += 1
        backup = self.backup_counter % self.BACKUP_INTERVAL == 0
        self.persist_state(backup)
        self.show_current_crop()

    def show_previous_image(self):
        self.existing_bounding_boxes_view.clear()
        self.new_bounding_boxes_view.clear()
        self.save_bounding_boxes()
        # Skip images with no structure.
        while True:
            self.set_previous_crop()
            if self.current_crop.min() != self.current_crop.max():
                break
        self.backup_counter += 1
        backup = self.backup_counter % self.BACKUP_INTERVAL == 0
        self.persist_state(backup)
        self.show_current_crop()

    def show_current_crop(self):
        self.header.setText(f'{self.current_probe_directory}/images/{self.current_crop_name}')
        self.annotate_image()

    def save_bounding_boxes(self):
        boxes = {
            BoxesType.MANUAL.value: self.current_crop_new_boxes,
            BoxesType.EXISTING.value: self.current_crop_existing_boxes
        }
        self.internal_boxes[self.build_crop_path()] = boxes

    def persist_state(self, backup=False):
        state = {
            'current_crop_index': self.current_crop_index,
            'current_probe_directory': self.current_probe_directory,
            'internal_boxes': self.internal_boxes
        }
        saved_state_file = Path(f'{self.processing_directory}/{self.SAVED_STATE_FILE_NAME}')
        if backup:
            backup_directory = Path(f'{self.processing_directory}/{self.BACKUP_DIRECTORY}')
            backup_directory.mkdir(exist_ok=True)
            saved_state_backup_file = backup_directory / f'{datetime.now().timestamp()}_{self.SAVED_STATE_FILE_NAME}'
            shutil.copy(saved_state_file, saved_state_backup_file)
        with open(saved_state_file, 'w') as file:
            json.dump(state, file)

    def load_state(self):
        try:
            with open(f'{self.processing_directory}/{self.SAVED_STATE_FILE_NAME}', 'r') as file:
                saved_state = json.load(file)
            self.current_crop_index = saved_state['current_crop_index']
            self.current_probe_directory = saved_state['current_probe_directory']
            self.internal_boxes = saved_state['internal_boxes']
        except FileNotFoundError:
            print('No previously save state exists, yet.')
            self.current_crop_index = 0
            self.current_probe_directory = self.probe_directories[0]
            self.internal_boxes = {}

    def export_csv(self):
        export_directory, _ = QFileDialog.getSaveFileName(
            self,
            "Export New Annotations",
            "updated_annotations",
            "CSV (*.csv)"
        )
        file_paths = []
        bounding_boxes = []
        label = []
        updated = []
        for probe_directory, boxes in self.internal_boxes.items():
            for box in boxes[BoxesType.EXISTING.value]:
                file_paths.append(probe_directory)
                bounding_boxes.append(box[0])
                label.append(box[1])
                updated.append(False)
            for box in boxes[BoxesType.MANUAL.value]:
                file_paths.append(probe_directory)
                bounding_boxes.append(box[0])
                label.append(box[1])
                updated.append(True)
        bounding_boxes = np.array(bounding_boxes)
        label_info = pd.DataFrame({
            'file_path': file_paths,
            'x1': bounding_boxes[:, 0] if len(bounding_boxes) > 0 else [],
            'y1': bounding_boxes[:, 1] if len(bounding_boxes) > 0 else [],
            'x2': bounding_boxes[:, 2] if len(bounding_boxes) > 0 else [],
            'y2': bounding_boxes[:, 3] if len(bounding_boxes) > 0 else [],
            'label': label,
            'updated': updated,
        })
        label_info.to_csv(
            export_directory,
            mode='w',
            header=True,
            index=False
        )

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        self.save_bounding_boxes()
        self.persist_state(backup=True)
        close_dialog = QDialog()
        close_dialog.setWindowTitle('Close Application')

        q_btn = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel

        close_dialog.buttonBox = QDialogButtonBox(q_btn)
        close_dialog.buttonBox.accepted.connect(close_dialog.accept)
        close_dialog.buttonBox.rejected.connect(close_dialog.reject)

        close_dialog.layout = QVBoxLayout()
        message = QLabel('Do you wish to close the annotation application?')
        close_dialog.layout.addWidget(message)
        close_dialog.layout.addWidget(close_dialog.buttonBox)
        close_dialog.setLayout(close_dialog.layout)
        if close_dialog.exec():
            a0.accept()
        else:
            a0.ignore()


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

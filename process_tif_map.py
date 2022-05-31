import glob
import os
import sys
from enum import Enum
from pathlib import Path

import cv2
import pandas as pd

IMAGE_WIDTH = 1280
IMAGE_HEIGHT = 960


class ImageTypeString(Enum):
    RAW = 'RAW.png'
    SYNTHETIC = 'FAST.SYN._FP.png'
    TIF = '.tif'


def process_probe_directories(
        probe_directory: Path,
):
    folders = sorted(next(os.walk(probe_directory))[1])
    for folder in folders:
        try:
            tif_path = Path(glob.glob(f'{probe_directory}/{folder}/images/{folder}_map.tif')[0])
            crops, crop_names, existing_bounding_boxes = crop_tif_map(tif_path)
            yield crops, crop_names, existing_bounding_boxes, folder
        except IndexError:
            print('Did not find files to process.')
            sys.exit()


def crop_tif_map(
        tif_path: Path,
        label_end: int,
):
    tif_map = cv2.imread(str(tif_path), cv2.IMREAD_UNCHANGED)

    vertical_tiles = tif_map.shape[0] // IMAGE_HEIGHT
    vertical_tif_labels = range(23, 23 - vertical_tiles, -1)
    horizontal_tiles = tif_map.shape[1] // IMAGE_WIDTH
    horizontal_tif_labels = range(label_end, label_end - horizontal_tiles, -1)
    crops = []
    crop_names = []
    existing_bounding_boxes = []
    for i, label_i in zip(range(horizontal_tiles), horizontal_tif_labels):
        for j, label_j in zip(range(vertical_tiles), vertical_tif_labels):
            probe_directory = tif_path.parents[1]
            crop = tif_map[j * IMAGE_HEIGHT:(j + 1) * IMAGE_HEIGHT, i * IMAGE_WIDTH:(i + 1) * IMAGE_WIDTH]
            crops.append(crop)
            crop_name = _build_crop_name(probe_directory.name, label_i, label_j, ImageTypeString.RAW)
            crop_names.append(crop_name)
            bounding_boxes = _get_image_bounding_boxes(
                probe_directory,
                _build_crop_name(probe_directory.name, label_i, label_j, ImageTypeString.TIF)
            )
            existing_bounding_boxes.append(bounding_boxes)
    crops.reverse()
    crop_names.reverse()
    existing_bounding_boxes.reverse()
    return crops, crop_names, existing_bounding_boxes


def _get_image_bounding_boxes(probe_directory, image_name):
    label_info = pd.read_csv(probe_directory / 'csv' / f'{probe_directory.name}_01_class.csv', sep=';')
    label_info = label_info.loc[label_info['ImageName'] == image_name][['x', 'y', 'Width', 'Height', 'PollenSpecies', 'PredictedPollenSpecies', 'PredictedPollenSpeciesLatin']]
    label_info['x2'] = label_info['x'] + label_info['Width']
    label_info['y2'] = label_info['y'] + label_info['Height']
    label_info['bounding_boxes'] = list(label_info[['x', 'y', 'x2', 'y2']].to_numpy())
    label_info['label'] = label_info['PollenSpecies']
    label_info['label'] = label_info['label'].where(label_info['PollenSpecies'] != '--', label_info['PredictedPollenSpecies'])
    label_info['label'] = label_info['label'].where(label_info['PollenSpecies'] != 'Y', label_info['PredictedPollenSpeciesLatin'])
    return [[row[0].tolist(), row[1]] for row in label_info[['bounding_boxes', 'label']].to_numpy()]


def _build_crop_name(
        directory_name: str,
        horizontal_label,
        vertical_label,
        image_type_string: ImageTypeString,
        pmon_string: str = 'pmon-00013',
):
    directory_date, directory_probe = directory_name.split('_')
    return f'polle-im_01_{str(horizontal_label).zfill(2)}_{str(vertical_label).zfill(2)}-{directory_date}-' \
           f'{pmon_string}-{directory_probe}-tiff{image_type_string.value}'

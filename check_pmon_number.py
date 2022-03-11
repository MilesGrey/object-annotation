import glob
import os
from pathlib import Path

import pandas as pd

pmon_string = 'pmon-00013'


def check_pmon_number():
    probe_directories = glob.glob('/Volumes/Samsung_T5/UNIKAT_2018_PART_1/*')
    for probe_directory in probe_directories:
        pmon_files = glob.glob(f'{probe_directory}/images/*pmon*')
        for pmon_file in pmon_files:
            if pmon_string not in pmon_file:
                print(f'Found file with pmon-string other than {pmon_string}: {pmon_file}')
                return False
        print(f'{probe_directory} does not contain file with other pmon string other than {pmon_string}')
    return True


def get_all_classes():
    weird_labels = [
        'BetulaCarpinus',
        'FraxinusCarpinus',
        'NBetula',
        'QuercusQuercus',
        'CladFraxinus',
        'BetulaBetula',
        'Betgula',
        'NCarpinus',
        'CarpinusCarpinus',
        'PLatanus',
        'Piceae',
        'VBetula',
        'NFraxinus',
        'CarpinusFraxinus',
        'BetulaFraxinus',
        'Brassicaceae',
        'CarpinusSpore',
        'NFagus',
        'NSalix',
        'NUlmus',
        'CarpinusFagus',
        'VFagus',
        'AlnusAlnus',
        'NPopulus',
        'SalixSalix',
        'Coylus',
        'QuercusTaxus',
        'BetulaTaxus',
        'QuercusVaria',
        'VTaxus',
        'BetulaPoaceae',
        'ALnus',
        'AcerBetula',
        'NPoaceae',
        'Fraxisnu',
        'PlatanusQuercus',
        'FraxinusSalix',
        'Spore',
        'AlnusFagus',
        'Quecus',
        'BetulaFagus',
        'AlnusCorylus',
        'Lanus',
        'TaxusTaxus',
        'BetulaQuercus',
        'VQuercus',
        'NTaxus',
        'Ulrticaceae',
        'CarpinusVaria',
        'YY',
        'CorylusAlnus',
        'NCorylus',
        'FraxinusTaxus',
        'CarpinusSalix',
        'NQuercus',
        'Plaranus',
        'AlnusBetula',
        'BrassicaceaeLarix',
        'FagusQuercus',
        'Betulaa',
        'VCarpinus',
        'Y ',
        'BetulaVaria',
        'SporeVaria',
        'TAxus',
        'y',
        'FagusVaria',
        'CarpinusTaxus',
        'BetulaCorylus',
    ]

    all_labels = set()
    probe_directories = glob.glob('/Volumes/Samsung_T5/UNIKAT_2018_PART_1/*')
    for probe_directory in probe_directories:
        directory_name = Path(probe_directory).name
        class_csv = f'{probe_directory}/csv/{directory_name}_01_class.csv'
        class_info = pd.read_csv(class_csv, sep=';')
        labels = class_info['PollenSpecies'].where(class_info['PollenSpecies'] != 'Y', class_info['PredictedPollenSpeciesLatin'])
        labels = labels.where(labels != 'nn', 'Sporen')
        labels = labels.where(labels != '--', 'NoPollen')
        labels = set(labels)

        detections = [label for label in labels if label in weird_labels]
        if len(detections) > 0:
            print(f' Weird label detected in {directory_name}: {detections}')

        all_labels = all_labels.union(labels)
    return print(all_labels)


def concat_single_csv_files():
    directory = '20180430030003_A050570'
    csv_files = glob.glob(f'/Volumes/Samsung_T5/UNIKAT_2018_PART_1/{directory}/csv/*tiff.csv')
    single_files = []
    for file in csv_files:
        single_files.append(pd.read_csv(file, sep=';'))
    aggregated = pd.concat(single_files)
    try:
        aggregated = aggregated.drop(['no', 'objects', 'found'], axis=1)
    except KeyError:
        pass
    aggregated.to_csv(f'/Volumes/Samsung_T5/UNIKAT_2018_PART_1/{directory}/csv/{directory}_01_class.csv', sep=';', index=False)


get_all_classes()
# concat_single_csv_files()

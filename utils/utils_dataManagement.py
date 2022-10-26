"""
Utilisation functions as part of (updrsTapping-repo)
ReTap-Toolbox
"""

# import public packages and functions
import os
from sys import platform
import numpy as np
from dataclasses import dataclass
from array import array


def get_proj_dir():
    """
    Takes parent-directory until main-project
    folder is found, containing code/, data/,
    figures/
    """
    dir = os.getcwd()

    while dir[-4:] != 'code':

        dir = os.path.dirname(dir)

    proj_dir = os.path.dirname(dir)

    return proj_dir


def find_stored_data_path():

    if platform == 'win32':
        
        path = os.getcwd()
        while os.path.dirname(path)[-5:] != 'Users':
            lastpath = path
            path = os.path.dirname(path)
        # path is now Users/username
        onedrive_f = [
            f for f in os.listdir(path) if np.logical_and(
                'onedrive' in f.lower(),
                'charit' in f.lower()
            ) 
        ]
        onedrivepath = os.path.join(path, onedrive_f[0])
        uncut_path = os.path.join(
            onedrivepath, 'ReTap', 'data', 'BER', 'UNCUT'
        )


    elif platform == 'darwin':

        print('create Python equivalent')
    
    return uncut_path


def get_file_selection(
    path, sub, state,
    joker_string = None
):
    sel_files = []
        
    for f in os.listdir(path):

        if not np.array([
            f'sub{sub}' in f.lower() or
            f'sub{sub[1:]}' in f.lower() or
            f'sub-{sub}' in f.lower()
        ]).any(): continue

        if type(joker_string) == str:

            if joker_string not in f:

                continue

        if state.lower() in f.lower():

            sel_files.append(f)
    
    return sel_files


def get_arr_key_indices(ch_names, hand_code):

    dict_out = {}
    print(f'HANDCODE {hand_code}')
    if hand_code == 'bilat':
        
        side = 'bilat'
        aux_keys = [
            'L_X', 'L_Y', 'L_Z',
            'R_X', 'R_Y', 'R_Z'
        ]
    
    else:

        if 'L' in hand_code:
            S = 'L'
            side = 'left'
        elif 'R' in hand_code:
            S = 'R'
            side = 'right'

        aux_keys = [
            f'{S}_X', f'{S}_Y', f'{S}_Z'
        ]

    
    aux_count = 0

    for i, key in enumerate(ch_names):

        if key in ['X', 'Y', 'Z']:

            if f'L_{key}' in dict_out.keys():

                dict_out[f'R_{key}'] = i
            
            else:

                dict_out[f'L_{key}'] = i
        
        elif 'aux' in key.lower():

            if 'iso' in key.lower(): continue

            dict_out[aux_keys[aux_count]] = i
            aux_count += 1

    return dict_out, side


@dataclass(init=True, repr=True)
class triAxial:
    """
    Select accelerometer keys

    TODO: add Cfg variable to indicate
    user-specific accelerometer-key
    """
    data: array
    key_indices: dict

    def __post_init__(self,):

        try:
            self.left = self.data[
                self.key_indices['L_X']:
                self.key_indices['L_Z'] + 1
            ]
        except KeyError:
            print('No left indices')

        try:
            self.right = self.data[
                self.key_indices['R_X']:
                self.key_indices['R_Z'] + 1
            ]
        except KeyError:
            print('No right indices')

"""
Function to detect continuous tapping blocks
"""

# Import public packages and functions
import numpy as np
import matplotlib.pyplot as plt
from os.path import join, exists
from os import makedirs
from pandas import DataFrame

# Import own functions
from tap_extract_fts.tapping_featureset import signalvectormagn
from tap_load_data.tapping_preprocess import find_main_axis

def find_active_blocks(
    acc_arr, fs, buff=5, buff_thr=.3, blocks_p_sec=8,
    act_wins_for_block=2, to_plot=True, verbose=True,
    to_store_csv=False, csv_dir: str='', csv_fname: str='',
    figsave_dir: str='', figsave_name: str='',
    plot_orig_fname: str = '',
):
    """
    Detects tapping blocks in triaxial acc array.
    First determines which windows are above a threshold,
    this threshold is based on the std-dev (default .5 SD).
    The creates longer blocks, every block contains
    several windows, and based on the part of active
    windows, a block is made active.
    Then merges active-blocks too close to each other (to 
    merge two blocks from the same tapping movement), and
    removes active blocks too small (small non-tap movements).

    Input:
        - acc_arr: tri-axial acc-array
        - fs (int): sample frequency
        - buff_thr (float): part of window that has
            to increase the (> std-dev) threshold to
            be set active
        - blocks_p_sec (int): divide one second by n blocks
        - act_wins_for_block: number of windows that have to
            be active to set a block as active
    
    Returns:
        - acc_blocks (list): list containing one
            2d array with triaxial acc-data per block
        - block_indices (dict): containing two lists
            with the start and end sample-indices
            of the detected blocks (in original
            sampled indices)
    """
    sig = signalvectormagn(acc_arr)
    thresh = np.nanstd(sig) * .5
    print(
        f'\n\nACT THRESH. {thresh}\n\n'
    )

    winl = int(fs / blocks_p_sec)

    # activity per window (acc > std.dev)
    act = np.array([sum(sig[i_start:i_start + winl] > thresh) / winl for
        i_start in np.arange(0, sig.shape[0], winl)])
    
    # blocks of windows with sufficient activity
    blocks = [sum(
        act[i_start - buff:i_start + buff] > buff_thr
    ) > act_wins_for_block for i_start in np.arange(buff, len(act) - buff)]
    
    # finding start and end indices of blocks
    block_indices = {'start': [], 'end': []}
    block_active = False
    for n, b in enumerate(blocks):
        if block_active:
            if b: continue
            else:
                block_indices['end'].append(n)
                block_active = False
        else:
            if b:
                block_indices['start'].append(n)
                block_active = True
            else:
                continue

    block_indices = merge_close_blocks(
        block_indices=block_indices,
        min_distance=blocks_p_sec * 2,
        verbose=verbose
    )

    block_indices = convert_win_ind_2_sample_ind(
        block_indices=block_indices, fs=fs, winl=winl,
    )
    block_indices = remove_short_blocks(
        block_indices=block_indices, fs=fs, min_length=2.5,
    )

    acc_blocks = convert_sample_ind_2_acc_arrays(
        acc_arr, block_indices
    )

    acc_blocks, block_indices = select_on_block_length(
        acc_blocks, block_indices, fs=fs
    )

    if verbose: report_detected_blocks(block_indices, fs)
    print(f'\n\n# BLOCKS {len(acc_arr)}')
    if to_plot: plot_blocks(
        acc_arr, block_indices, fs, 
        figsave_dir, figsave_name,
        plot_orig_fname,
    )

    if to_store_csv: save_block_csv(
        acc_blocks, fs, csv_dir, csv_fname,
    )

    return acc_blocks, block_indices


def merge_close_blocks(
    block_indices, min_distance, verbose
):
    """
    Merges blocks with a too small distance to
    each other. Blocks are still expreseed in windows,
    not yet in samples.

    Input:
        - block_indices: list with lists of starting and
            ending indices of detected blocks
        - min_distance: blocks which are lesser than
            this time-distance separated will be merged
    
    Returns:
        - new_block_indices: containing new starts and end
            indices in two lists
    """
    new_block_indices = {'start': [], 'end': []}

    mergecount = 0

    ongoing = False

    for win, end in enumerate(block_indices['end']):
            # take start index of next block (if end not from the last block)
        try:
            start = block_indices['start'][win + 1]
        
        except IndexError:  # in case of last current block

            if not ongoing:
                i_start = block_indices['start'][win]  # no existing i-start
            # include last block
            i_end = block_indices['end'][win]
            new_block_indices['start'].append(i_start)
            new_block_indices['end'].append(i_end)
            

        if (start - end) < min_distance:
            # start (win n+1) vs end (win n)
            # too short -> block is not closed and stored

            if not ongoing:
                # save start-index from current block for new block later to store 
                i_start = block_indices['start'][win]
                ongoing = True
                mergecount += 1
            

        else:  # next block too far away -> close current/ongoing block
            # if only this block is taken, take current i-start
            if not ongoing: i_start = block_indices['start'][win]
            # take current i-end too close the block
            i_end = block_indices['end'][win]

            new_block_indices['start'].append(i_start)
            new_block_indices['end'].append(i_end)

            ongoing = False

    return new_block_indices


def remove_short_blocks(
    block_indices: dict, fs: int, min_length: float,
):
    """
    Removes blocks which are shorter then defined
    seconds
    
    Inputs:
        - block_indices (dict): current block-indices
            in array sample frequency samples
        - fs (int): sampling freq
        - min_length (float): minimal block duration
            in seconds
    
    Returns:
        - block_indices (dict): selected block indices
    """
    new_block_indices = {'start': [], 'end': []}
    min_samples = min_length * fs

    for start, end in zip(
        block_indices['start'], block_indices['end']
    ):
        if (end - start) < min_samples:
            continue
        
        else:
            new_block_indices['start'].append(start)
            new_block_indices['end'].append(end)
    
    return new_block_indices


def convert_win_ind_2_sample_ind(
    block_indices: dict, fs: int, winl: int,
):
    """
    Set indices back to original sample-indices
    of high freq acc array instead of indices of
    window lengths
    """
    sample_indices = {'start': [], 'end': []}
    for key in block_indices.keys():
        sample_indices[key] = np.around(np.array(
            block_indices[key]) * winl, 0
        ).astype(int)
    
    return sample_indices


def convert_sample_ind_2_acc_arrays(
    acc_arr, block_indices
):
    """
    Stores tri-axial acc-arrays per block, in a
    Python list.
    """
    acc_blocks = [
        acc_arr[:, i1:i2] for i1, i2 in zip(
            block_indices['start'], block_indices['end']
        )
    ]

    return acc_blocks

def select_on_block_length(
    acc_blocks, block_indices, fs,
    min_block_length_sec=3,
    max_block_length_sec=None,
):
    """
    Select blocks with appropriate block-lengths
    """
    # find blocks with too long length
    to_del = []

    for i in np.arange(len(block_indices['start'])):
        
        length = (block_indices['end'][i] - 
                  block_indices['start'][i]) / fs

        if length < min_block_length_sec: to_del.append(i)

    # select the blocks and indices based on the found indices
    sel_blocks = [
        block for i, block in enumerate(acc_blocks)
        if i not in to_del
    ]
    sel_indices = {}
    for time in ['start', 'end']:
        
        sel_indices[time] = [
            indx for i, indx in enumerate(block_indices[time])
            if i not in to_del
        ]
    
    print(f'deleted blocks: {to_del}')

    return sel_blocks, sel_indices


def report_detected_blocks(block_indices, fs):
    """
    Report on detected block number and lengths, takes
    block_indices after conversion to sample-indices
    """
    block_lengths = []
    for b in np.arange(len(block_indices['start'])):
        
        block_lengths.append(
            (block_indices['end'][b] - 
            block_indices['start'][b]) / fs
        )

    print(f'# {len(block_lengths)} tapping blocks detec'
            f'ted, lengths (in sec): {block_lengths}')


def save_block_csv(
    acc_blocks, fs, csv_dir, csv_fname,
):
    """
    Store csv-files per blocks
    """
    if not exists(csv_dir):
        makedirs(csv_dir)

    for n, block_arr in enumerate(acc_blocks):

        storeData = DataFrame(
            block_arr.T, columns=['X', 'Y', 'Z'])

        fname = csv_fname + f'_block{n + 1}_{fs}Hz.csv'

        storeData.to_csv(join(csv_dir, fname))

        print(f'saved block {n}: {fname} @ {csv_dir}')


def plot_blocks(
    acc_arr, block_indices, fs, 
    figsave_dir, figsave_name,
    plot_orig_fname,
):
    """
    Plots overview of selected blocks and main axes
    """
    if not exists(figsave_dir):
        makedirs(figsave_dir)

    print(f'plotting {figsave_name}...')
    mainax = find_main_axis(acc_arr)
    otheraxes = [0, 1, 2]
    otheraxes.remove(mainax)

    fig, ax = plt.subplots(1, 1, figsize=(24,12))
    ax.plot(
        acc_arr[mainax],
        label=f'Main Axis ({mainax})',
        alpha=.8,
    )
    for axis in otheraxes:
        ax.plot(
            acc_arr[axis],
            label=f'Axis ({axis})',
            alpha=.4,
        )

    for pos1, pos2 in zip(
        block_indices['start'], block_indices['end']
    ):
        ax.fill_betweenx(
            y=np.arange(5.5,6.1,.5),
            x1=pos1, x2=pos2,
            color='red', alpha=.3,
            label='detected tapping blocks')
        ax.set_xlabel(f'Samples ({fs} Hz)', fontsize=16)
        ax.set_ylabel('Acceleration (in g in m/s/s)', fontsize=16)
        ax.set_title(figsave_name, size=20)


    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    plt.legend(
        by_label.values(), by_label.keys(),
        frameon=False, fontsize=16,
        ncol=4, loc='lower center'
    )

    if len(plot_orig_fname) > 1:
        plt.suptitle(
            plot_orig_fname, x=.05, y=.97,
            ha='left', size=16,
            color='gray', alpha=.8,)

    plt.tight_layout()
    plt.savefig(
        join(figsave_dir, figsave_name),
        dpi=150, facecolor='w',
    )
    plt.close()


"""
For visualisation:
thresh = np.nanstd(sig)
act = np.array([sum(svm[i_start:i_start + winl] > thresh) / winl for
        i_start in np.arange(0, sig.shape[0], winl)])
blocks = [sum(act[i_start - buff:i_start + buff] > buff_thr) > 5 for
        i_start in np.arange(buff, len(act) - buff)]

axes[n].plot(act, color='blue', alpha=.4,
        label=f' Part of sig > std.dev. (window: {np.round(winl / fs, 2)})')
    axes[n].plot(blocks, color='red', alpha=.5,
        label=f'>70% active in window {np.round(2 * buff * winl / fs)} s')

func_blocks = find_blocks.find_active_blocks(dat, 250)
for start_i, end_i in zip(func_blocks['start'], func_blocks['end']):
    axes[1].fill_betweenx(x1=start_i, x2=end_i, y=[1.1, 1.2],
        color='gray',alpha=.7,
    )
"""
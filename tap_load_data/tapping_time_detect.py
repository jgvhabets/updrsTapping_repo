'''Feature Extraction Preparation Functions'''

# Import public packages and functions
import numpy as np
from scipy.signal import find_peaks


# Import own functions
from tap_load_data.tapping_impact_finder import find_impacts
from tap_extract_fts.tapping_featureset import signalvectormagn
from tap_load_data.tapping_preprocess import remove_acc_nans
   

def updrsTapDetector(
    acc_triax, main_ax_i: int, fs: int,
):
    """
    Detect the moments of finger-raising and -lowering
    during a fingertapping task.
    Function detects the axis with most variation and then
    first detects several large/small pos/neg peaks, then
    the function determines sample-wise in which part of a
    movement or tap the acc-timeseries is, and defines the
    exact moments of finger-raising, finger-lowering, and
    the in between stopping moments. 

    Input:
        - acc_triax (arr): tri-axial accelerometer data-
            array containing x, y, z, shape: [3 x nsamples].
        - main_ax_i (int): index of axis which detected
            strongest signal during tapping (0, 1, or 2)
        - fs (int): sample frequency in Hz
    
    Return:
        - tapi (list of lists): list with full-recognized taps,
            every list is one tap. Every list contains 6 moments
            of the tap: [startUP, fastestUp, stopUP, startDown, 
            fastestDown, impact, stopDown]
        - tapTimes (list of lists): lists per tap corresponding
            with tapi, expressed in seconds after start data array
        - endPeaks (array): indices of impact-peak which correspond
            to end of finger closing moment.
    """
    if np.isnan(acc_triax).any():
        acc_triax = remove_acc_nans(acc_triax)
        # get timepoints with any nans in all 3 axes
        sel = ~np.isnan(acc_triax).any(axis=0)
        # if len(sel) == 3: sel = len(np.isnan(acc_triax).any(axis=1))  # for debugging if acc_triax has other shape
        acc_triax = acc_triax[:, sel]
    
    sig = acc_triax[main_ax_i]
    sigdf = np.diff(sig)
    # timeStamps = np.arange(0, len(sig), 1 / fs)

    # use svm for impact finding now
    svm = signalvectormagn(acc_triax)

    # Thresholds for movement detection
    posThr = np.nanmean(sig)
    negThr = -np.nanmean(sig)
    
    # Find peaks to help movement detection
    peaksettings = {
        'peak_dist': 0.1,
        'cutoff_time': .25,
    }

    impacts = find_impacts(svm, fs)  # svm-impacts are more robust, regardless of main ax

    posPeaks = find_peaks(
        sig,
        height=(posThr, np.nanmax(sig)),
        distance=fs * .05,
    )[0]

    # delete impact-indices from posPeak-indices
    for i in impacts:
        idel = np.where(posPeaks == i)
        posPeaks = np.delete(posPeaks, idel)

    negPeak = find_peaks(
        -1 * sig,
        height=-.5e-7,
        distance=fs * peaksettings['peak_dist'] * .5,
        prominence=abs(np.nanmin(sig)) * .05,
    )[0]

    # Lists to store collected indices and timestamps
    tapi = []  # list to store indices of tap
    empty_timelist = np.array([np.nan] * 7)
    # [startUP, fastestUp, stopUP, startDown, fastestDown, impact, stopDown]
    tempi = empty_timelist.copy()
    state = 'lowRest'
    post_impact_blank = int(fs / 1000 * 15)  # last int defines n ms
    blank_count = 0
    end_last_tap_n = 0  # needed for backup filling of tap-start-index

    # Sample-wise movement detection        
    for n, y in enumerate(sig[:-1]):

        if n in impacts:

            state = 'impact'
            tempi[5] = n
        
        elif state == 'impact':
            if blank_count < post_impact_blank:
                blank_count += 1
                continue
            
            else:
                if sigdf[n] > 0:
                    blank_count = 0
                    tempi[6] = n
                    # always set first index of tap
                    if np.isnan(tempi[0]):
                        # if not detected, than use end of last tap
                        tempi[0] = end_last_tap_n + 5

                    tapi.append(np.array(tempi))  # add detected tap-indices as array
                    end_last_tap_n = tempi[6]  # update last impact n to possible fill next start-index

                    tempi = empty_timelist.copy()  # start with new empty list
                    state='lowRest'  # reset state
                    

        elif state == 'lowRest':
            # debugging to get start of tap every time in
            if np.logical_and(
                y > posThr,  # try with half the threshold to detect start-index
                sigdf[n] > np.percentile(sigdf, 50)  # was 75th percentile 
            ):                
                state='upAcc1'
                tempi[0] = n  # START OF NEW TAP, FIRST INDEX
                
        elif state == 'upAcc1':
            if n in posPeaks:
                state='upAcc2'

        elif state == 'upAcc2':
            if y < 0:  # crossing zero-line, start of decelleration
                tempi[1] = n  # save n as FASTEST MOMENT UP
                state='upDec1'

        elif state=='upDec1':
            if n in posPeaks:  # later peak found -> back to up-accel
                state='upAcc2'
            elif n in negPeak:
                state='upDec2'

        elif state == 'upDec2':
            if np.logical_or(y > 0, sigdf[n] < 0):
                # if acc is pos, or goes into acceleration
                # phase of down movement
                state='highRest'  # end of UP-decell
                tempi[2]= n  # END OF UP !!!

        elif state == 'highRest':
            if np.logical_and(
                y < negThr,
                sigdf[n] < 0
            ):
                state='downAcc1'
                tempi[3] = n  # START OF LOWERING            

        elif state == 'downAcc1':
            if np.logical_and(
                y > 0,
                sigdf[n] > 0
            ):
                state='downDec1'
                tempi[4] = n  # fastest down movement

    
    tapi = tapi[1:]  # drop first tap due to starting time

    return tapi, impacts, acc_triax

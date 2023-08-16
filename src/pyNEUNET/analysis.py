"""
analysis.py
Sabine Chu, Sean Fayfar
August 2023
"""

import numpy as np
from scipy.stats import binned_statistic

def rebin(inp, bins, save=False, label="", fldr=""):
    """
    Rebins histogram data from input numpy array or file

    Parameters
    -------
    inp: numpy array or str
            Output from previous reading
    bins: int
            Number of bins for new histogram
    save: boolean, optional
            Save data?
    label: str, optional
            File to save to
            Only used if input is an array and save is true
    fldr: str, optional
            Folder to save to
            Only used if input is an array and save is true

    Returns
    -------
    new_hist: numpy array
            Histogram with correct number of bins
    """
    inptype = type(inp)
    if isinstance(inp, str):
        inp = np.loadtxt(inp)
    rebinned = binned_statistic(inp[:,0], inp[:,1], "sum", bins=bins)
    rebinned_x = np.linspace(rebinned.bin_edges[0], rebinned.bin_edges[-1], bins)
    rebinned_y = rebinned.statistic
    new_hist = np.column_stack((rebinned_x, rebinned_y))
    if save:
        if inptype == str:
            splitup = inp.split("/")
            new_filename = "/".join(splitup[:-1])+f"rebinned_{bins}bins"+splitup[-1]
        elif inptype == np.ndarray:
            if fldr[-1] != "/":
                fldr = fldr+"/"
            new_filename = fldr+label
        np.savetxt(new_filename, new_hist)
    return new_hist
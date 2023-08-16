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
    if isinstance(inp, str):
        orig_hist = np.loadtxt(inp).transpose()
    elif isinstance(inp, np.ndarray):
        orig_hist = inp.transpose()
    rebinned = binned_statistic(orig_hist[0], orig_hist[1], "sum", bins=bins)
    rebinned_x = [(rebinned.bin_edges[j] + rebinned.bin_edges[j+1])/2
                  for j in range(len(rebinned.bin_edges)-1)]
    rebinned_y = rebinned.statistic
    new_hist = np.array([rebinned_x, rebinned_y]).transpose()
    if save:
        if isinstance(inp, str):
            splitup = inp.split("/")
            new_filename = "/".join(splitup[:-1])+f"rebinned_{bins}bins"+splitup[-1]
        elif isinstance(inp, np.ndarray):
            if fldr[-1] != "/":
                fldr = fldr+"/"
            new_filename = fldr+label
        np.savetxt(new_filename, new_hist)
    return new_hist

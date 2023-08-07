"""
translaters.py
Sabine Chu
08-01-2023

Translates data from detectors
Formulae from Canon documentation
"""

def translate_neutron_data(bin_data):
    nanoseconds = 25*10**-9*(2**16*bin_data[1] + 2**8*bin_data[2] + bin_data[3])
    psd_number = (bin_data[4] // 2**4) % 2**3
    pl = 2**10*(bin_data[4] % 2**4) + 2**2*bin_data[5] + bin_data[6] // 2**6
    pr = 2**8*(bin_data[6] % 2**6) + bin_data[7]
    pulse_height = pl + pr
    try:
        position = pl/pulse_height
    except ZeroDivisionError:
        position = None
    return psd_number, position

# We don't use trigger data or TOF
def translate_trigger_id(bin_data):
    return bin_data[1], bin_data[2], bin_data[3]

def translate_instrument_time(bin_data):
    seconds1 = 2**24*bin_data[1] + 2**16*bin_data[2] + 2**8*bin_data[3] + bin_data[4]
    seconds2 = 2**-15*(2**7*bin_data[5] + bin_data[6] // 2**1)
    seconds3 = 25*10**-8*(2**8*(bin_data[6] % 2**3) + bin_data[7])
    return seconds1 + seconds2 + seconds3
"""
translaters.py
Sabine Chu
08-01-2023

Translates data from detectors.
"""

def translate_neutron_data(hex_data):
    time = 25*10**-9*(65536*int(hex_data[2:4], 16) + 256*int(hex_data[4:6], 16)
                        + int(hex_data[6:8], 16)) # time in nanoseconds
    psd_number = (int(hex_data[8:10], 16) // 16) % 8
    pl = 1024*(int(hex_data[8:10], 16) % 16) + 4*int(hex_data[10:12], 16) \
        + int(hex_data[12:14], 16) // 64
    pr = 256*(int(hex_data[12:14], 16) % 64) + int(hex_data[14:16], 16)
    pulse_height = pl + pr
    try:
        position = pl/pulse_height
    except ZeroDivisionError:
        position = None
    return psd_number, position

def translate_trigger_id(hex_data): # not used
    return int(hex_data[2:4], 16), int(hex_data[4:6], 16), int(hex_data[6:8], 16)

def translate_instrument_time(hex_data): # time in seconds
    ii = 2**24*int(hex_data[2:4], 16) + 2**16*int(hex_data[4:6], 16) \
        + 2**8*int(hex_data[6:8], 16) + int(hex_data[8:10], 16)
    s = 2**-15*(2**7*int(hex_data[10:12], 16) + int(hex_data[12:14], 16) // 2**1)
    s1 = 25*10**-8*(2**8*(int(hex_data[12:14], 16) % 2**3) \
                    + int(hex_data[14:16], 16))
    return ii + s + s1
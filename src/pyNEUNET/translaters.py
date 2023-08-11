"""
translaters.py
Sabine Chu
08-01-2023

Translates data from detectors
Formulae from Canon documentation ("Communication Protocol of NeuNET system-revA2.pdf")
"""

from datetime import datetime, timedelta

EFFECT_LEN_MM = 150
ANODE_RES = 1.5 # kilo-ohms
PREAMP_RES = 1

def translate_neutron_data(bin_data):
    """
    Translates 8-byte neutron data

    Parameters
    -------
    bin_data: bytes
            8-byte binary data from detector
    
    Returns
    -------
    psd_number: int
            Detector number
    position: float
            Value ranging from 0 to 1 corresponding to position on detector
            See to_physical_position function to convert to physical position
    """
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

def translate_instrument_time(bin_data):
    """
    Translates 8-byte instrument time data

    Parameters
    -------
    bin_data: bytes
            8-byte binary data from detector

    Returns
    -------
    seconds: float
            Number of seconds since 1/1/2008 0:00:00
    """
    seconds1 = 2**24*bin_data[1] + 2**16*bin_data[2] + 2**8*bin_data[3] + bin_data[4]
    seconds2 = 2**-15*(2**7*bin_data[5] + bin_data[6] // 2**1)
    seconds3 = 25*10**-8*(2**8*(bin_data[6] % 2**3) + bin_data[7])
    seconds = seconds1 + seconds2 + seconds3
    return seconds

def instrument_time(input=None,mode='seconds'):
    '''
    Function to convert time from bytes to seconds and the reverse.
    Time is defined as seconds since 2008

    Parameters
    ---------
    input : 5 bytes representing time, optional
        If input is None, the current time will be output as 5 bytes
    mode : str
        'seconds' : output time in seconds
        'datetime' : output time in datetime

    '''
    if input is None:
        secondsSince2008 = (datetime.now() - datetime(2008,1,1,0,0)).total_seconds()
        secondsBytes = int(secondsSince2008).to_bytes(4,'big')
        subsecondsBytes = int(secondsSince2008 % 1 * 2**8).to_bytes(1,'big')
        return secondsBytes + subsecondsBytes
    else:
        intSeconds = int.from_bytes(input[:4],'big')
        intSubSeconds = input[-1]
        secondsSince2008 = intSeconds + (intSubSeconds / 2**8)
        if mode == 'seconds':
            return secondsSince2008
        elif mode == 'datetime':
            return datetime(2008,1,1) + timedelta(seconds=secondsSince2008)

def to_physical_position(decimal_pos):
    """
    Translates float position ranging from 0 to 1 to physical position along detector

    Parameters
    -------
    decimal_pos: float
            Position calculated from neutron data
    
    Returns
    -------
    physical_pos: float
            Physical position in mm
    """
    physical_pos = (decimal_pos - 0.5)*EFFECT_LEN_MM*(ANODE_RES + 2*PREAMP_RES)/ANODE_RES
    return physical_pos

# We don't use trigger data or TOF
def translate_trigger_id(bin_data):
    return bin_data[1], bin_data[2], bin_data[3:]
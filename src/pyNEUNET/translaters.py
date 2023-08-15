"""
translaters.py
Sabine Chu, Sean Fayfar
August 2023
"""

from datetime import datetime, timedelta

EFFECT_LEN_MM = 150
ANODE_RES = 1.5 # kilo-ohms
PREAMP_RES = 1

def translate_neutron_data(bin_data, type=14):
    """
    Translates 8-byte neutron data

    Parameters
    -------
    bin_data: bytes
            8-byte binary data from detector
    type: int (12 or 14)
            12-bit or 14-bit (resolution level) data
    
    Returns
    -------
    psd_number: int
            Detector number
    position: float
            Value ranging from 0 to 1 corresponding to position on detector
            See to_physical_position function to convert to physical position
    """
    if type == 12:
        nanoseconds = 25*10**-9*(2**16*bin_data[1] + 2**8*bin_data[2] + bin_data[3])
        psd_number = bin_data[4] % 2**3
        pl =2**4*bin_data[5] + bin_data[6] // 2**4
        pr = 2**8*(bin_data[6] % 2**4) + bin_data[7]
    elif type == 14:
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

def instrument_time(input=None,mode='seconds'):
    '''
    Function to convert time from bytes to seconds and the reverse.
    Time is defined as seconds since 2008 and stored in 5 bytes.
    4 bytes for seconds and 1 byte for subsections

    Parameters
    ---------
    input : Time input as 5 bytes, seconds, or datetime, optional
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
    elif isinstance(input,(bytes,bytearray)):
        intSeconds = int.from_bytes(input[:4],'big')
        intSubSeconds = input[4]
        secondsSince2008 = intSeconds + (intSubSeconds / 2**8)
        if mode == 'seconds':
            return secondsSince2008
        elif mode == 'datetime':
            return datetime(2008,1,1) + timedelta(seconds=secondsSince2008)
    elif isinstance(input,(int,float)):
        return datetime(2008,1,1,0,0) + timedelta(seconds=input)
    elif isinstance(input,datetime):
        return (input - datetime(2008,1,1,0,0)).total_seconds()

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

# NOT USED
def translate_trigger_id(bin_data):
    return bin_data[1], bin_data[2], bin_data[3:]

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
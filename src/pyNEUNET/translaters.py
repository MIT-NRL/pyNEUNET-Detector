"""
translaters.py
Sabine Chu, Sean Fayfar
August 2023
"""

from datetime import datetime, timedelta

EFFECT_LEN_MM = 150
ANODE_RES = 1.5 # kilo-ohms
PREAMP_RES = 1

def translate_neutron_data(bin_data, resolution_type=14):
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
    if resolution_type == 12:
        psd_number = bin_data[4] % 2**3
        pulse_left = 2**4*bin_data[5] + bin_data[6] // 2**4
        pulse_right = 2**8*(bin_data[6] % 2**4) + bin_data[7]
    elif resolution_type == 14:
        psd_number = (bin_data[4] // 2**4) % 2**3
        pulse_left = 2**10*(bin_data[4] % 2**4) + 2**2*bin_data[5] + bin_data[6] // 2**6
        pulse_right = 2**8*(bin_data[6] % 2**6) + bin_data[7]
    pulse_height = pulse_left + pulse_right
    try:
        position = pulse_left/pulse_height
    except ZeroDivisionError:
        position = None
    return psd_number, position

def translate_instrument_time(inp=None, mode='seconds'):
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
    if inp is None:
        seconds_since_2008 = (datetime.now() - datetime(2008,1,1,0,0)).total_seconds()
        seconds_bytes = int(seconds_since_2008).to_bytes(4,'big')
        subseconds_bytes = int(seconds_since_2008 % 1 * 2**8).to_bytes(1,'big')
        return seconds_bytes + subseconds_bytes
    if isinstance(inp,(int,float)):
        return datetime(2008,1,1,0,0) + timedelta(seconds=inp)
    if isinstance(inp,datetime):
        return (inp - datetime(2008,1,1,0,0)).total_seconds()
    if isinstance(inp,(bytes,bytearray)):
        int_seconds = int.from_bytes(inp[:4],'big')
        int_subseconds = inp[4]
        seconds_since_2008 = int_seconds + (int_subseconds / 2**8)
        if mode == 'seconds':
            return seconds_since_2008
        if mode == 'datetime':
            return datetime(2008,1,1) + timedelta(seconds=seconds_since_2008)

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

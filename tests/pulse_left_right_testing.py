import socket
from datetime import datetime, timedelta
from numpy.random import randint

IP_ADDRESS = "192.168.0.17"
UDP_PORT = 4660
TCP_PORT = 23
UDP_ADDR = {
    "time mode": 0x18A,
    "device time": 0x190,
    "read/write": 0x186,
    "resolution": 0x1B4,
    "handshake/one-way": 0x1B5,
}
TCP_START_BYTES = {
    "neutron event": 0x5F,
    "trigger id": 0x5B,
    "instrument time": 0x6C,
}
TIMEOUT = 5
TOTAL_TIME = 30
SMALL_ERROR = 0.001
LARGE_ERROR = 0.01

def register_readwrite(ip_address, port, address, data_id=None, length=1, data=None, verbose=False):
    '''
    Reads/writes to the register of the NEUNET board using UDP protocol.
    '''
    read_mode, write_mode = 0xc0, 0x80
    if data_id is None:
        data_id = randint(0,255)
    send_bytes = bytearray([0xff,0x00,data_id,length]) + address.to_bytes(4,'big')
    if verbose:
        print(f"initial message: {send_bytes}")
    if data is not None:
        if verbose:
            print(f"data to write: {data}")
        if not isinstance(data,(list,bytes,bytearray)):
            data = [data]
            if verbose:
                print(f"data as list: {data}")
        send_bytes += bytearray(data)
        if verbose:
            print(f"message with data: {send_bytes}")
        send_bytes[1] = write_mode
        send_bytes[3] = len(data) #Make the length match sent byte length automatically
        if verbose:
            print(f"final message: {send_bytes}")
    else:
        send_bytes[1] = read_mode

    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as udp_sock:
        udp_sock.sendto(send_bytes,(ip_address,port))
        recv_data = udp_sock.recv(1024)
        udp_sock.close()
    flag_byte = recv_data[1] % 2**4
    if flag_byte % 2**1:
        raise ConnectionRefusedError('Bus error! Check the format of the sent packet.',
                                     f"Send: {send_bytes.hex(':')}\n",
                                     f"Header : {recv_data[:8].hex(':')}\n",
                                     f"Data : {recv_data[8:].hex(':')}")        
    if verbose:
        print(f"Send: {send_bytes.hex(':')}\n",
              f"Header: {recv_data[:8].hex(':')}\n",
              f"Data: {recv_data[8:].hex(':')}")
    return recv_data

def translate_neutron_data(bin_data, resolution_type=14):
    if resolution_type == 12:
        psd_number = bin_data[4] % 2**3
        pulse_left = 2**4*bin_data[5] + bin_data[6] // 2**4
        pulse_right = 2**8*(bin_data[6] % 2**4) + bin_data[7]
    elif resolution_type == 14:
        psd_number = (bin_data[4] // 2**4) % 2**3
        pulse_left = 2**10*(bin_data[4] % 2**4) + 2**2*bin_data[5] + bin_data[6] // 2**6
        pulse_right = 2**8*(bin_data[6] % 2**6) + bin_data[7]
    return psd_number, pulse_left, pulse_right

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

def main():
    #Staging
    response_byte = register_readwrite(
            IP_ADDRESS, UDP_PORT, UDP_ADDR["time mode"], data=0x80
        )
    response_byte = register_readwrite(
            IP_ADDRESS,
            UDP_PORT,
            UDP_ADDR["device time"],
            data=translate_instrument_time() + bytes([0x00, 0x00]),
        )
    response_byte = register_readwrite(
            IP_ADDRESS, UDP_PORT, UDP_ADDR["read/write"], data=bytes(2)
        )
    response_byte = register_readwrite(
            IP_ADDRESS, UDP_PORT, UDP_ADDR["resolution"], data=[0x8A, 0x80]
        )
    print("Staged")
    
    # Connect to detector
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    tcp_sock.settimeout(TIMEOUT)
    tcp_sock.connect((IP_ADDRESS, TCP_PORT))
    print("Connected")

    # Start reading data
    recv_byte = tcp_sock.recv(1)
    while recv_byte[0] != TCP_START_BYTES["instrument time"]:
        recv_byte = tcp_sock.recv(1)
    bytes_data = recv_byte
    for i in range(7):
        bytes_data += tcp_sock.recv(1)
    start_time = translate_instrument_time(bytes_data[1:])
    current_time = start_time
    total_counts = {0:0, 7:0}
    close_counts = {0:0, 7:0}
    very_close_counts = {0:0, 7:0}
    greater_very_close = {0:0, 7:0}
    lesser_very_close = {0:0, 7:0}
    equal = {0:0, 7:0}
    while current_time - start_time < TOTAL_TIME:
        bytes_data = bytes()
        for i in range(8):
            bytes_data += tcp_sock.recv(1)
        if bytes_data[0] == TCP_START_BYTES["neutron event"]:
            psd_number, pulse_left, pulse_right = translate_neutron_data(bytes_data)
            pulse_height = pulse_left+pulse_right
            position = pulse_left/pulse_height
            # print("PSD number:", psd_number)
            # print("Left pulse:", pulse_left)
            # print("Right pulse:", pulse_right)
            # print("Pulse height:", pulse_height)
            # print("Position:", pulse_left/pulse_height)
            dist = abs(position-0.5)
            if dist < LARGE_ERROR:
                close_counts[psd_number] += 1
                if dist < SMALL_ERROR:
                    very_close_counts[psd_number] += 1
                    if position < 0.5:
                        lesser_very_close[psd_number] += 1
                    elif position == 0.5:
                        equal[psd_number] += 1
                        print("Position = 0.5")
                        print("Left pulse = right pulse = ", pulse_left)
                    else:
                        greater_very_close[psd_number] += 1
            total_counts[psd_number] += 1
        elif bytes_data[0] == TCP_START_BYTES["instrument time"]:
            current_time = translate_instrument_time(bytes_data[1:])
    elapsed_time = current_time - start_time
    tcp_sock.close()
    print("Elapsed time:", elapsed_time)
    print("Total counts:", total_counts)
    print(f"Counts with {0.5-LARGE_ERROR} < position < {0.5+LARGE_ERROR}: {close_counts}")
    print(f"Counts with {0.5-SMALL_ERROR} < position < {0.5+SMALL_ERROR}: {very_close_counts}")
    print(f"Counts with {0.5-SMALL_ERROR} < position < 0.5: {lesser_very_close}")
    print(f"Counts with position = 0.5: {equal}")
    print(f"Counts with 0.5 < position < {0.5+SMALL_ERROR}: {greater_very_close}")

main()
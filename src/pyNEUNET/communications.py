"""
communications.py
Sabine Chu, Sean Fayfar
August 2023
"""

import socket
from numpy.random import randint

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



def read_full_register(ip_address, port, output_file=None,verbose=True):
    '''
    Reads the entire writable section of the NEUNET register.
    Ranges from address 0x180 to 0x1b5
    '''
    udp_bytes = []
    udp_bytes.append('        '+'|'.join(['+'+str(x) for x in range(8)]))
    for address,length in zip([0x180,0x188,0x18b,0x190,0x198,0x1b0],[8,3,5,7,8,6]):
        udp_bytes.append(str(hex(address))+' = '+register_readwrite(
               ip_address, port, address, length=length)[8:].hex(':'))
    if verbose:
        print('\n'.join(udp_bytes))
    if output_file is not None:
        with open(output_file, 'w') as open_file:
            open_file.writelines('\n'.join(udp_bytes))

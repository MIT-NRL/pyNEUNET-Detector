# Useful TCP/UDP function for communicating with the NEUNET system
import socket
from numpy.random import randint


def register_readwrite(IP='192.168.0.17',
                  port=4660,ID=None,length=1,address=0x80,data=None,verbose=False):
        '''
        Reads/writes to the register of the NEUNET board using UDP protocol.
        '''
        modeRead,modeWrite = 0xc0, 0x80
        if ID is None:
                ID = randint(0,255)
        sendBytes = bytearray([0xff,0x00,ID,length]) + address.to_bytes(4,'big')
        if verbose:
                print(f"initial message: {sendBytes}")
        if data is not None:
                if verbose:
                       print(f"data to write: {data}")
                if not isinstance(data,(list,bytes,bytearray)):
                        data = [data]
                        if verbose:
                               print(f"data as list: {data}")
                sendBytes += bytearray(data)
                if verbose:
                        print(f"message with data: {sendBytes}")
                sendBytes[1] = modeWrite
                sendBytes[3] = len(data) #Make the length match sent byte length automatically
                if verbose:
                        print(f"final message: {sendBytes}")
        else:
                sendBytes[1] = modeRead
                
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sockUDP:
                sockUDP.sendto(sendBytes,(IP,port))
                recvData = sockUDP.recv(1024)
        flagByte = recvData[1] % 2**4
        if flagByte % 2**1:
                raise ConnectionRefusedError('Bus error! Check the format of the sent packet.',
                                             f"Send: {sendBytes.hex(':')}\n",
                                             f"Header : {recvData[:8].hex(':')}\n",
                                             f"Data : {recvData[8:].hex(':')}"
                                             )        
        if verbose:
                print(f"Send: {sendBytes.hex(':')}\n",
                      f"Header: {recvData[:8].hex(':')}\n",
                      f"Data: {recvData[8:].hex(':')}")
        return recvData



def read_full_register(outputFileStr=None,verbose=True):
    '''
    Reads the entire writable section of the NEUNET register.
    Ranges from address 0x180 to 0x1b5
    '''
    udpBytes = []
    udpBytes.append('        '+'|'.join(['+'+str(x) for x in range(8)]))
    for address,length in zip([0x180,0x188,0x18b,0x190,0x198,0x1b0],[8,3,5,7,8,6]):
        udpBytes.append(str(hex(address))+' = '+register_readwrite(length=length,address=address)[8:].hex(':'))
    if verbose:
        print('\n'.join(udpBytes))
    if outputFileStr is not None:
        with open(outputFileStr,'w') as openFile:
            openFile.writelines('\n'.join(udpBytes))
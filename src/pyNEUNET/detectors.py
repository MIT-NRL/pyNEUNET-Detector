"""
tcp_reader.py
Sabine Chu
08-01-2023

Implements basic packet reader
"""

import socket
import numpy as np
import matplotlib.pyplot as plt
from collections import OrderedDict
from .translaters import instrument_time, translate_neutron_data, to_physical_position

class Linear3HePSD:
    '''
    Linear 3He position sensitive neutron detector with a resolution of 5 mm
    built by Canon. The device is controlled with the NUENET system. 
    '''
    BINS = 1024
    SANITY_PINGS = 100
    NEUTRON_EVENT = 0x5f
    TRIGGER_ID = 0x5b
    INST_TIME = 0x6c
    START_BYTES = [NEUTRON_EVENT, TRIGGER_ID, INST_TIME]
    
    def __init__(self, ip_address="192.168.0.17", tcp_port=23, udp_port=4660):
        """
        Creates new socket object linked to detectors
        Default inputs given by Canon documentation for TCP connection

        Parameters
        -------
        ip_address: str, optional
                Remote address of detector
                Default is 192.168.0.17
        port: int, optional
                Port number for TCP connection
                Default is 23
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        self.sock.settimeout(5)
        self.ip = ip_address
        self.tcp_port = tcp_port
        self.udp_port = udp_port

    def stage():
        '''
        Sets up the NEUNET system register (mode, instrument time, etc) using UDP protocol.
        '''
        ...

    def unstage():
        '''
        Shuts down and clears the NEUNET system register.
        '''
        ...

    def collect_8bytes(self, offset=False, verbose=False):
        """
        Collect 8 bytes from already connected detector
        Bytes collected 1-by-1 due to socket's unpredictability re length of data

        Parameters
        -------
        offset: boolean, optional
                True if the data may not start with preferred byte values
                Default is False
        verbose: boolean, optional
                Whether to print out data as it comes in
        """
        if offset:
            recv_byte = self.sock.recv(1)
            if verbose:
                print(recv_byte)
            while recv_byte[0] not in self.START_BYTES:
                recv_byte = self.sock.recv(1)
                if verbose:
                    print(recv_byte.hex())
            self.bytes_data = recv_byte
            for i in range(7):
                self.bytes_data += self.sock.recv(1)
            if recv_byte[0] == self.INST_TIME:
                self.start_time = instrument_time(recv_byte)
        else:
            self.bytes_data = bytes()
            for i in range(8):
                self.bytes_data += self.sock.recv(1)
        if verbose:
            print("Data: " + self.bytes_data.hex(":"))

    def _count_neutron(self):
        """
        Counts the neutron event and adds it to the histogram
        """
        psd_number, position = translate_neutron_data(self.bytes_data)
        if position is not None:
            res = self.BINS-1 if position*self.BINS >= self.BINS else int(position*self.BINS)
            if psd_number == 0:
                self.arr0[0][res] += 1
                self.count0 += 1
            elif psd_number == 7:
                self.arr7[0][res] += 1
                self.count7 += 1

    def read(self, seconds, test_label, format=None, save=True, verbose=False, fldr=""):
        """"
        Connects to detector and reads data for given time length
        Creates histograms of neutron counts for binned physical positions on detectors
        
        Parameters
        -------
        seconds: float or int
                Time to collect data for
        test_label: str
                Name of files and graph
        format: str, optional
                Format of output
                If "bluesky", output is a bluesky-compatible OrderedDict
                Otherwise (default), output is a dictionary
        save: boolean, optional
                Whether to save histogram data and graph onto computer
                Default is True
        verbose: boolean, optional
                Whether to print indications that code is working
                Default is False
        fldr: str, optional
                Folder to save data to
                Only called if save is True
                Default is main directory

        Returns
        -------
        result: OrderedDict
                Stores histograms for each detector and start time for data collection
        """
        self.sock.connect((self.ip, self.tcp_port))
        if verbose:
            print("Connected")
        blank_array = np.array([[0 for i in range(self.BINS)],
                                [to_physical_position(i/self.BINS) for i in range(self.BINS)]])
        self.arr0, self.arr7 = np.copy(blank_array), np.copy(blank_array)
        self.count0 = 0
        self.count7 = 0
        self.start_time = 0
        self.current_time = 0

        self.collect_8bytes(offset=True)
        if verbose:
            print("Started collecting")
        while not self.start_time:
            self.collect_8bytes()
            # We probably don't want to count neutrons until time starts
            # if self.bytes_data[0] == NEUTRON_EVENT:
            #     self._count_neutron()
            if self.bytes_data[0] == self.INST_TIME:
                self.start_time = instrument_time(self.bytes_data[1:])
        if verbose:
            print("Reached first 'instrument time' data")
        while self.current_time - self.start_time < seconds:
            self.collect_8bytes()
            if self.bytes_data[0] == self.NEUTRON_EVENT:
                self._count_neutron()
            elif self.bytes_data[0] == self.INST_TIME:
                self.current_time = instrument_time(self.bytes_data[1:])
        self.elapsed_time = self.current_time - self.start_time
        if verbose:
            print(f"Completed collecting neutron counts.\n",
                  f"Total counts Det0: {self.count0}\n",
                  f"Total counts Det7: {self.count7}\n",
                  f"Exposure time: {self.elapsed_time} s")
        self.sock.close()

        if save:
            if fldr:
                if fldr[-1] != "/":
                    fldr += "/"
                test_label = fldr + test_label
            np.savetxt(f"{test_label}_detector0_histogram.txt", self.arr0,
                       header=f"detector 0, start: {self.start_time}; \
                        column 1 = decimal position, column 2 = physical position (mm).")
            np.savetxt(f"{test_label}_detector7_histogram.txt", self.arr7,
                       header=f"detector 7, start: {self.start_time}; \
                        column 1 = decimal position, column 2 = physical position (mm).")
            plt.plot(self.arr0, label="psd 0")
            plt.plot(self.arr7, label="psd 7")
            plt.legend()
            plt.xlabel("position")
            plt.ylabel("neutron count")
            plt.title(test_label)
            plt.savefig(f"{test_label}_graph.png")

        if format == "bluesky":
            # Timestamp is in the format of seconds since 1970
            result = OrderedDict()
            result["detector 0"] =  {"value": self.arr0, "timestamp": instrument_time(self.start_time).timestamp()}
            result["detector 7"] =  {"value": self.arr7, "timestamp": instrument_time(self.start_time).timestamp()}
            if verbose:
                print(result)
            return result
        
        return {"timestamp": instrument_time(self.start_time).timestamp(),
                "detector 0": self.arr0,
                "detector 7": self.arr7}

    def sanity_check(self, pings=SANITY_PINGS):
        """
        Prints out given number of packets

        Parameters
        -------
        pings: int, optional
                Number of packets to print
                Default is 100
        """
        self.sock.connect((self.ip, self.port))
        print("Connected")
        print(self.sock.recv(1))
        self.collect_8bytes(offset=False)
        print(self.bytes_data)
        print(self.bytes_data.hex(":"))
        for i in range(pings-1):
            self.collect_8bytes()
            print(self.bytes_data)
            print(self.bytes_data.hex(":"))
            print(self.bytes_data[0])
            if self.bytes_data[0] == self.NEUTRON_EVENT:
                print(translate_neutron_data(self.bytes_data))
            elif self.bytes_data[0] == self.INST_TIME:
                print(instrument_time(self.bytes_data[1:], mode="datetime"))
        self.sock.close()
    
    @property
    def exposure_time(self):
        return self.exposure_time
    
    @exposure_time.getter
    def exposure_time(self, input):
        self.exposure_time = input


def main():
    obj = Linear3HePSD()
    obj.sanity_check()
# obj.start(10, "test 2 columns", True, True)

if __name__ == '__main__':
    main()
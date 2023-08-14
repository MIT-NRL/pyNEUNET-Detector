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
from translaters import instrument_time, translate_neutron_data, to_physical_position
from communications import register_readwrite, read_full_register

class Linear3HePSD:
    '''
    Linear 3He position sensitive neutron detector with a resolution of 5 mm
    built by Canon. The device is controlled with the NUENET system. 
    '''
    BINS = 1024
    NEUTRON_EVENT = 0x5f
    TRIGGER_ID = 0x5b
    INST_TIME = 0x6c
    START_BYTES = [NEUTRON_EVENT, TRIGGER_ID, INST_TIME]
    EXPOSURE_TIME = 10
    
    def __init__(self, ip_address="192.168.0.17", tcp_port=23, udp_port=4660, psd_nums = [0, 7]):
        """
        Creates new socket object linked to detectors
        Default inputs given by Canon documentation for TCP connection

        Parameters
        -------
        ip_address: str, optional
                Remote address of detector
        tcp_port: int, optional
                Port number for TCP connection
        udp_port: int, optional
                Port number for UDP connection
        """
        self.ip = ip_address
        self.tcp_port = tcp_port
        self.udp_port = udp_port
        self.psd_nums = psd_nums
        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        self.tcp_sock.settimeout(5)
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.staged = False

    def stage(self, verbose=False):
        '''
        Sets up the NEUNET system register (mode, instrument time, etc) using UDP protocol.
        '''
        register_readwrite(IP=self.ip, port=self.udp_port, printOutput=verbose)
        self.staged = True
        # need more

    def unstage(self):
        '''
        Shuts down and clears the NEUNET system register.
        '''
        self.staged = False
        # need more

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
            recv_byte = self.tcp_sock.recv(1)
            if verbose:
                print(recv_byte)
            while recv_byte[0] not in self.START_BYTES:
                recv_byte = self.tcp_sock.recv(1)
                if verbose:
                    print(recv_byte.hex())
            self.bytes_data = recv_byte
            for i in range(7):
                self.bytes_data += self.tcp_sock.recv(1)
            if recv_byte[0] == self.INST_TIME:
                self.start_time = instrument_time(recv_byte)
        else:
            self.bytes_data = bytes()
            for i in range(8):
                self.bytes_data += self.tcp_sock.recv(1)
        if verbose:
            print("Data: " + self.bytes_data.hex(":"))

    def _count_neutron(self):
        """
        Counts the neutron event and adds it to the histogram
        """
        psd_number, position = translate_neutron_data(self.bytes_data)
        if position is not None:
            res = self.BINS-1 if position*self.BINS >= self.BINS else int(position*self.BINS)
            self.counts[f"detector {psd_number}"] += 1
            self.histograms[f"detector {psd_number}"][1][res] += 1

    def read(self, test_label, format=None, save=True, verbose=False, fldr=""):
        """"
        Connects to detector and reads data for given time length
        Creates histograms of neutron counts for binned physical positions on detectors
        
        Parameters
        -------
        test_label: str
                Name of files and graph
        format: str, optional
                Format of output
                If "bluesky", output is a bluesky-compatible OrderedDict
                Otherwise (default), output is a tuple containing start time and histograms
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
        result: OrderedDict or tuple
                Stores histograms for each detector and start time for data collection
        """
        self.tcp_sock.connect((self.ip, self.tcp_port))
        if verbose:
            print("Connected")
        blank_array = np.array([[to_physical_position(i/self.BINS) for i in range(self.BINS)],
                                [0 for i in range(self.BINS)]])
        self.counts = {}
        self.histograms = {}
        for i in self.psd_nums:
            self.counts[f"detector {i}"] = 0
            self.histograms[f"detector {i}"] = np.copy(blank_array)
        self.start_time = 0
        self.current_time = 0
        
        if not self.staged:
            self.stage(verbose)
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
        while self.current_time - self.start_time < self.exposure_time:
            self.collect_8bytes()
            if self.bytes_data[0] == self.NEUTRON_EVENT:
                self._count_neutron()
            elif self.bytes_data[0] == self.INST_TIME:
                self.current_time = instrument_time(self.bytes_data[1:])
        self.elapsed_time = self.current_time - self.start_time
        if verbose:
            print(f"Completed collecting neutron counts")
            for i in self.psd_nums:
                  print(f"Total counts from detector {i}: {self.counts[f'detector {i}']}")

            print(f"Exposure time: {self.elapsed_time} s")
        self.tcp_sock.close()

        fig, (ax0) = plt.subplots(1, 1)
        for i in self.psd_nums:
            ax0.plot(self.self.histograms[f"detector {i}"], label=f"detector {i}")
        ax0.legend()
        ax0.xlabel("position (mm)")
        ax0.ylabel("neutron count")
        fig.title(test_label)

        if save:
            if fldr:
                if fldr[-1] != "/":
                    fldr += "/"
                test_label = fldr + test_label
            for i in self.psd_nums:
                np.savetxt(f"{test_label}_detector{i}_histogram.txt", self.histograms[f"detector {i}"],
                           header=f"detector {i}, start: {self.start_time}; \
                            column 1 = physical position (mm), column 2 = counts per position.")
            fig.savefig(test_label+"_graph.png")
        fig.show()

        if format == "bluesky":
            # Timestamp is in the format of seconds since 1970
            result = OrderedDict()
            for i in self.psd_nums:
                result[f"detector {i}"] = {"value": self.histograms[f"detector {i}"],
                                           "timestamp": instrument_time(self.start_time).timestamp()}
            if verbose:
                print(result)
            return result
        
        return instrument_time(self.start_time).timestamp(), self.histograms

    def sanity_check(self, pings=100):
        """
        Prints out given number of packets

        Parameters
        -------
        pings: int, optional
                Number of packets to print
                Default is 100
        """
        print("Connected")
        if not self.staged:
            self.stage(True)
        print("Staged")
        print(self.tcp_sock.recv(1))
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
        self.tcp_sock.close()
    
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
"""
detectors.py
Sabine Chu, Sean Fayfar
August 2023
"""

import socket
import numpy as np
import matplotlib.pyplot as plt
from collections import OrderedDict
from .translaters import instrument_time, translate_neutron_data, to_physical_position
from .communications import register_readwrite

class Linear3HePSD:
    '''
    Linear 3He position sensitive neutron detector with a resolution of 5 mm
    built by Canon. The device is controlled with the NUENET system. 
    '''
    BINS = 1024
    UDP_ADDR = {"time mode": 0x18a, "device time": 0x190, "read/write": 0x186, "resolution": 0x1b4, "handshake/one-way": 0x1b5}
    TCP_START_BYTES = {"neutron event": 0x5f, "trigger id": 0x5b, "instrument time": 0x6c}
    TIMEOUT = 5
    
    def __init__(self, ip_address="192.168.0.17", tcp_port=23, udp_port=4660, psd_nums=[0, 7], exposure_time=10):
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
        self.name = "Linear3HePSD"
        self.parent = None
        self.__ip = ip_address
        self.__tcp_port = tcp_port
        self.__udp_port = udp_port
        self.__psd_nums = psd_nums
        self.__staged = False
        self.__exposure_time = exposure_time

    def stage(self, verbose=False):
        '''
        Sets up the NEUNET system register (mode, instrument time, etc) using UDP protocol.
        '''
        #Set time to 32-bit mode
        responseByte = register_readwrite(self.__ip, self.__udp_port, self.UDP_ADDR["time mode"], data=0x80)

        #First send the computer time to the instrument
        if verbose:
            print("Detector time before setting:",
                  instrument_time(register_readwrite(self.__ip, self.__udp_port, self.UDP_ADDR["device time"],
                                                     length=5)[8:], mode="datetime"))
        responseByte = register_readwrite(self.__ip, self.__udp_port, self.UDP_ADDR["device time"],
                                          data=instrument_time()+bytes([0x00,0x00]))
        if verbose:
            print("Detector time after setting:",
                  instrument_time(register_readwrite(self.__ip, self.__udp_port, self.UDP_ADDR["device time"],
                                                     length=5)[8:], mode='datetime'))

        #Set event memory read mode
        responseByte = register_readwrite(self.__ip, self.__udp_port, self.UDP_ADDR["read/write"], data=bytes(2))

        #Set 14-bit (high-resolution) mode and one-way mode
        responseByte = register_readwrite(self.__ip, self.__udp_port, self.UDP_ADDR["usage"], data=[0x8a, 0x80])

        self.__staged = True
        if verbose:
            print("Finished staging")

    def unstage(self):
        '''
        Shuts down and clears the NEUNET system register.
        '''
        #Set handshake mode
        responseByte = register_readwrite(self.__ip, self.__udp_port, self.UDP_ADDR["handshake/one-way"], data=[0x00])

        self.__staged = False

    def collect_8bytes(self, sock, offset=False, verbose=False):
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
            recv_byte = sock.recv(1)
            if verbose:
                print(recv_byte)
            while recv_byte[0] not in self.TCP_START_BYTES:
                recv_byte = sock.recv(1)
                if verbose:
                    print(recv_byte.hex())
            self.__bytes_data = recv_byte
            for i in range(7):
                self.__bytes_data += sock.recv(1)
            if recv_byte[0] == self.TCP_START_BYTES["instrument time"]:
                self.__start_time = instrument_time(recv_byte)
        else:
            self.__bytes_data = bytes()
            for i in range(8):
                self.__bytes_data += sock.recv(1)
        if verbose:
            print("Data: " + self.__bytes_data.hex(":"))

    def _count_neutron(self):
        """
        Counts the neutron event and adds it to the histogram
        """
        psd_number, position = translate_neutron_data(self.__bytes_data)
        if position is not None:
            res = self.BINS-1 if position*self.BINS >= self.BINS else int(position*self.BINS)
            self.__counts[f"detector {psd_number}"] += 1
            self.__histograms[f"detector {psd_number}"][1][res] += 1

    def read(self, test_label="", format="bluesky", graph=False, save=False, verbose=False, fldr=""):
        """"
        Connects to detector and reads data for given time length
        Creates histograms of neutron counts for binned physical positions on detectors
        
        Parameters
        -------
        test_label: str
                Name of files and graph
        format: str, optional
                Format of output
                If "bluesky" (default), output is a bluesky-compatible OrderedDict containing histograms and elapsed time
                Otherwise, output is a tuple containing start time, elapsed time, and histograms
        graph: boolean, optional
                Whether to graph histogram data
                Default is False
        save: boolean, optional
                Whether to save histogram data and graph onto computer
                Default is False
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
                Stores histograms for each detector, start time, elapsed time
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        sock.settimeout(self.TIMEOUT)
        sock.connect((self.__ip, self.__tcp_port))
        if verbose:
            print("Connected")
        blank_array = np.array([[to_physical_position(i/self.BINS) for i in range(self.BINS)],
                                [0 for i in range(self.BINS)]])
        self.__counts = {}
        self.__histograms = {}
        for i in self.__psd_nums:
            self.__counts[f"detector {i}"] = 0
            self.__histograms[f"detector {i}"] = np.copy(blank_array)
        self.__start_time = 0
        current_time = 0
        
        if not self.__staged:
            self.stage(verbose)
        self.collect_8bytes(sock, offset=True)
        if verbose:
            print("Started collecting")
        while not self.__start_time:
            self.collect_8bytes(sock)
            if self.__bytes_data[0] == self.TCP_START_BYTES["instrument time"]:
                self.__start_time = instrument_time(self.__bytes_data[1:])
        if verbose:
            print("Reached first 'instrument time' data")
        while current_time - self.__start_time < self.__exposure_time:
            self.collect_8bytes(sock)
            if self.__bytes_data[0] == self.TCP_START_BYTES["neutron event"]:
                self._count_neutron()
            elif self.__bytes_data[0] == self.TCP_START_BYTES["instrument time"]:
                current_time = instrument_time(self.__bytes_data[1:])
        elapsed_time = current_time - self.__start_time
        if verbose:
            print("Completed collecting neutron counts")
            for i in self.__psd_nums:
                  print(f"Total counts from detector {i}: {self.__counts[f'detector {i}']}")

            print(f"Exposure time: {elapsed_time} s")
        sock.close()

        if graph:
            fig, (ax0) = plt.subplots(1, 1)
            for i in self.__psd_nums:
                ax0.plot(self.__histograms[f"detector {i}"][0], self.__histograms[f"detector {i}"][1], label=f"detector {i}")
            ax0.legend()
            ax0.set_xlabel("position (mm)")
            ax0.set_ylabel("neutron count")
            ax0.set_title(f"Neutron counts v. position")

        if save:
            if fldr:
                if fldr[-1] != "/":
                    fldr += "/"
                test_label = fldr + test_label
            for i in self.__psd_nums:
                np.savetxt(f"{test_label}_detector{i}_histogram.txt", self.__histograms[f"detector {i}"],
                           header=f"detector {i}, start: {self.__start_time}; \
                            column 1 = physical position (mm), column 2 = counts per position.")
            if graph:
                fig.savefig(test_label+"_graph.png")
                fig.show()

        if format == "bluesky":
            # Timestamp is in the format of seconds since 1970
            start_timestamp = instrument_time(self.__start_time).timestamp()
            # TODO: The "value" field has to be JSON encodable (for our purposes, a number, string, or array)
            result = OrderedDict()
            for i in self.__psd_nums:
                result[f"detector {i}"] = {"value": self.__histograms[f"detector {i}"],
                                           "timestamp": start_timestamp}
            result["elapsed time"] = {"value": elapsed_time,
                                      "timestamp": start_timestamp}
            if verbose:
                print(result)
            return result
        
        return start_timestamp, elapsed_time, self.__histograms
    
    def describe(self):
        """
        Returns bluesky-compatible OrderedDict describing output data
        """
        description = OrderedDict()
        for i in self.__psd_nums:
            description[f"detector {i}"] = {"source": f"detector {i}",
                                            "dtype": "array",
                                            "shape": [self.BINS, 2]}
        description["elapsed time"] = {"source": "n/a",
                                       "dtype": "number",
                                       "shape": []}
        return description

    def sanity_check(self, pings=100):
        """
        Prints out given number of packets

        Parameters
        -------
        pings: int, optional
                Number of packets to print
                Default is 100
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        sock.settimeout(self.TIMEOUT)
        sock.connect((self.__ip, self.__tcp_port))
        print("Connected")
        if not self.__staged:
            self.stage(True)
        self.collect_8bytes(sock, offset=False)
        print("Bytes format:", self.__bytes_data)
        print("Hexadecimal:", self.__bytes_data.hex(':'))
        for i in range(pings-1):
            self.collect_8bytes(sock)
            print("Bytes format:", self.__bytes_data)
            print("Hexadecimal:", self.__bytes_data.hex(':'))
            if self.__bytes_data[0] == self.TCP_START_BYTES["neutron event"]:
                print("Neutron data:", translate_neutron_data(self.__bytes_data))
            elif self.__bytes_data[0] == self.TCP_START_BYTES["instrument time"]:
                print("Instrument time:", instrument_time(self.__bytes_data[1:], mode="datetime"))
        sock.close()
        print("Closed socket")
    
    @property
    def exposure_time(self):
        return self.__exposure_time
    
    @exposure_time.setter
    def exposure_time(self, input):
        self.__exposure_time = input


def main():
    obj = Linear3HePSD()
    obj.sanity_check()
    # obj.exposure_time = 15
    # output = obj.read()
    # print(output)
    # obj.exposure_time = 10
    # output_2 = obj.read()
    # print(output_2)
    # obj.exposure_time = 60
    # output = obj.read(test_label="8_14_2023_try", graph=True, save=True, fldr="c:/Users/4DH4/Desktop/pyneunet_output", verbose=True)
    # print(output)

if __name__ == '__main__':
    main()
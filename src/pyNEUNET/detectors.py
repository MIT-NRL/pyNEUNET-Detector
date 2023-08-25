"""
detectors.py
Sabine Chu, Sean Fayfar
August 2023
"""

import socket
from collections import OrderedDict
from datetime import datetime
from os.path import exists

import matplotlib.pyplot as plt
import numpy as np

from .communications import register_readwrite
from .translators import (
    to_physical_position,
    translate_instrument_time,
    translate_neutron_data,
)


class Linear3HePSD:
    """
    Linear 3He position sensitive neutron detector with a resolution of 5 mm
    built by Canon. The device is controlled with the NEUNET system.
    """

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

    def __init__(
        self,
        ip_address="192.168.0.17",
        tcp_port=23,
        udp_port=4660,
        psd_nums=(0, 7),
        exposure_time=10,
        bins=350
    ):
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
        psd_nums: list, tuple, or set, optional
                Numbers of the detectors we're using
                Must range from 0 to 7
        exposure_time: int or float, optional
                Exposure time for readings
        bins: int, optional
                Bin size for histograms
        """
        self.name = "Linear3HePSD"
        self.parent = None
        self.__ip = ip_address
        self.__tcp_port = tcp_port
        self.__udp_port = udp_port
        self.__psd_nums = psd_nums
        self.__staged = False
        self.__exposure_time = exposure_time
        self.__bins = bins

    def stage(self, verbose=False):
        """
        Sets up the NEUNET system register (mode, instrument time, etc) using UDP protocol.
        """
        # Set time to 32-bit mode
        response_byte = register_readwrite(
            self.__ip, self.__udp_port, self.UDP_ADDR["time mode"], data=0x80
        )

        # First send the computer time to the instrument
        if verbose:
            print("Detector time before setting:", self.get_instrument_time())
        response_byte = register_readwrite(
            self.__ip,
            self.__udp_port,
            self.UDP_ADDR["device time"],
            data=translate_instrument_time() + bytes([0x00, 0x00]),
        )
        if verbose:
            print("Detector time after setting:", self.get_instrument_time())

        # Set event memory read mode
        response_byte = register_readwrite(
            self.__ip, self.__udp_port, self.UDP_ADDR["read/write"], data=bytes(2)
        )

        # Set 14-bit (high-resolution) mode and one-way mode
        response_byte = register_readwrite(
            self.__ip, self.__udp_port, self.UDP_ADDR["resolution"], data=[0x8A, 0x80]
        )

        self.__staged = True
        if verbose:
            print("Finished staging")

    def unstage(self):
        """
        Shuts down and clears the NEUNET system register.
        """
        # Set handshake mode
        response_byte = register_readwrite(
            self.__ip, self.__udp_port, self.UDP_ADDR["handshake/one-way"], data=[0x00]
        )

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
            while recv_byte[0] not in self.TCP_START_BYTES.values():
                recv_byte = sock.recv(1)
                if verbose:
                    print(recv_byte.hex())
            self.__bytes_data = recv_byte
            for i in range(7):
                self.__bytes_data += sock.recv(1)
            if recv_byte[0] == self.TCP_START_BYTES["instrument time"]:
                self.__start_time = translate_instrument_time(recv_byte)
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
            res = int(position * (self.__bins - 1))

            self.__counts[f"detector {psd_number}"] += 1
            self.__histograms[f"detector {psd_number}"][res, 1] += 1

    def read(
        self,
        test_label="",
        output_format="bluesky",
        graph=False,
        save=False,
        verbose=False,
        fldr="",
        overwrite=True
    ):
        """ "
        Connects to detector and reads data for given time length
        Creates histograms of neutron counts for binned physical positions on detectors

        Parameters
        -------
        test_label: str
                Name of files and graph
        output_format: str, optional
                Format of output
                If "bluesky" (default), output is a bluesky-compatible
                    OrderedDict containing histograms and elapsed time
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
        overwrite: boolean, optional
                If a file with the same name already exists, whether to overwrite or create new file
                Only called if save is True
                Default is True

        Returns
        -------
        result: OrderedDict or tuple
                Stores histograms for each detector, start time, elapsed time
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0) as sock:
            sock.settimeout(self.TIMEOUT)
            sock.connect((self.__ip, self.__tcp_port))
            if verbose:
                print("Connected")

            blank_array = np.column_stack(
                (
                    to_physical_position(np.linspace(0, 1, self.__bins)),
                    np.zeros(self.__bins),
                )
            )

            self.__counts = {}
            self.__histograms = {}
            for i in self.__psd_nums:
                self.__counts[f"detector {i}"] = 0
                self.__histograms[f"detector {i}"] = np.copy(blank_array)
            self.__start_time = 0
            current_time = 0

            # if not self.__staged:
            self.stage(verbose)
            self.collect_8bytes(sock, offset=True)
            if verbose:
                print("Started collecting")
            while not self.__start_time:
                self.collect_8bytes(sock)
                if self.__bytes_data[0] == self.TCP_START_BYTES["instrument time"]:
                    self.__start_time = translate_instrument_time(self.__bytes_data[1:])
                    start_timestamp = translate_instrument_time(
                        self.__start_time
                    ).timestamp()
                    # computer_start_time = datetime.now()
            if verbose:
                print("Reached first 'instrument time' data")
            while current_time - self.__start_time < self.__exposure_time:
                self.collect_8bytes(sock)
                if self.__bytes_data[0] == self.TCP_START_BYTES["neutron event"]:
                    self._count_neutron()
                elif self.__bytes_data[0] == self.TCP_START_BYTES["instrument time"]:
                    current_time = translate_instrument_time(self.__bytes_data[1:])
            end_time = current_time
            # computer_end_time = datetime.now()
            elapsed_time = current_time - self.__start_time
            if verbose:
                print("Completed collecting neutron counts")
                for i in self.__psd_nums:
                    print(
                        f"Total counts from detector {i}: {self.__counts[f'detector {i}']}"
                    )

                print(f"Exposure time: {elapsed_time} s")
                # print(f"Computer elapsed time: {(computer_end_time - computer_start_time).total_seconds()}")
            # sock.close()

        if graph:
            fig, (ax0) = plt.subplots(1, 1)
            for i in self.__psd_nums:
                ax0.plot(
                    self.__histograms[f"detector {i}"][:, 0],
                    self.__histograms[f"detector {i}"][:, 1],
                    label=f"detector {i}",
                )
            ax0.legend()
            ax0.set_xlabel("position (mm)")
            ax0.set_ylabel("neutron count")
            ax0.set_title("Neutron counts v. position")
            if verbose:
                fig.show()

        if save:
            if fldr:
                if fldr[-1] != "/":
                    fldr += "/"
                test_label = fldr + test_label
            if (not overwrite) and exists(f"{test_label}_detector{list(self.__psd_nums)[0]}_histogram.txt"):
                test_label += "_1"
            for i in self.__psd_nums:
                np.savetxt(
                    f"{test_label}_detector{i}_histogram.txt",
                    self.__histograms[f"detector {i}"],
                    header=f"detector {i}\n"
                    + f"Start time: {(datetime.fromtimestamp(start_timestamp))}\n"
                    + f"End time: {translate_instrument_time(end_time)}\n"
                    + f"Exposure time (s): {elapsed_time}\n"
                    + "column 1 = physical position (mm), column 2 = counts per position.",
                )
            if graph:
                fig.savefig(test_label + "_graph.png")

        if output_format == "bluesky":
            # Timestamp is in the format of seconds since 1970
            result = OrderedDict()
            for i in self.__psd_nums:
                result[f"detector {i}"] = {
                    "value": self.__histograms[f"detector {i}"],
                    "timestamp": start_timestamp,
                }
            result["elapsed time"] = {
                "value": elapsed_time,
                "timestamp": start_timestamp,
            }
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
            description[f"detector {i}"] = {
                "source": f"detector {i}",
                "dtype": "array",
                "shape": [self.__bins, 2],
            }
        description["elapsed time"] = {"source": "n/a", "dtype": "number", "shape": []}
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
        # if not self.__staged:
        self.stage(True)
        self.collect_8bytes(sock, offset=False)
        print("Bytes:", self.__bytes_data)
        print("Hexadecimal:", self.__bytes_data.hex(":"))
        for i in range(pings - 1):
            self.collect_8bytes(sock)
            print("Bytes:", self.__bytes_data)
            print("Hexadecimal:", self.__bytes_data.hex(":"))
            if self.__bytes_data[0] == self.TCP_START_BYTES["neutron event"]:
                print("Neutron data:", translate_neutron_data(self.__bytes_data))
            elif self.__bytes_data[0] == self.TCP_START_BYTES["instrument time"]:
                print(
                    "Instrument time:",
                    translate_instrument_time(self.__bytes_data[1:], mode="datetime"),
                )
        sock.close()
        print("Closed socket")

    @property
    def exposure_time(self):
        return self.__exposure_time

    @exposure_time.setter
    def exposure_time(self, seconds):
        self.__exposure_time = seconds

    @property
    def bins(self):
        return self.__bins
    
    @bins.setter
    def bins(self, num):
        self.__bins = num

    def get_instrument_time(self):
        return translate_instrument_time(
            register_readwrite(
                self.__ip, self.__udp_port, self.UDP_ADDR["device time"], length=5
            )[8:],
            mode="datetime",
        )


def main():
    obj = Linear3HePSD()
    # obj.exposure_time = 300
    # obj.bins = 350
    # result = obj.read(save=True, graph=True, test_label="350_bins_preset_300seconds_test",
    #                   fldr="c:/Users/4DH4/Dropbox (MIT)/Experiments/MIT NRL/Stress Strain Diffractometer Data/2023-08/pyneunet_tests/",
    #                   verbose=True, overwrite=False)
    # # print(result)


if __name__ == "__main__":
    main()

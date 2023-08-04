"""
3he_detector_reader.py
Sabine Chu
08-01-2023

Implements basic packet reader
"""

import socket
import numpy as np
import matplotlib.pyplot as plt
from translaters import translate_instrument_time, translate_neutron_data

IP_ADDRESS = '192.168.0.17'
PORT = 23
BINS = 1024
SANITY_PINGS = 100
NEUTRON_EVENT = bytearray.fromhex("5f")
TRIGGER_ID = bytearray.fromhex("5b")
INST_TIME = bytearray.fromhex("6c")
HEADERS = [NEUTRON_EVENT, TRIGGER_ID, INST_TIME]

class detector_reader:
    def __init__(self, ip_address=IP_ADDRESS, port=PORT):
        """
        Creates new socket object linked to detectors
        Inputs: ip_address (string), port (int)
        Default inputs given by Canon documentation for TCP connection
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        self.ip = ip_address
        self.port = port

    def collect_8bytes(self, offset=False):
        # Collect bytes 1-by-1 due to socket's unpredictability re length of data
        if offset:
            recv_byte = self.sock.recv(1)
            while recv_byte not in HEADERS:
                recv_byte = self.sock.recv(1)
            self.bytes_data = recv_byte
            for i in range(7):
                self.bytes_data += self.sock.recv(1)
            if recv_byte == INST_TIME:
                self.start_time = translate_instrument_time(recv_byte)
        else:
            self.bytes_data = bytearray(b"")
            for i in range(8):
                self.bytes_data += self.sock.recv(1)

    def translate_5f(self):
        psd_number, position = translate_neutron_data(self.bytes_data)
        if position is not None:
            res = BINS-1 if position*BINS >= BINS else int(position*BINS)
            if psd_number == 0:
                self.arr0[res] += 1
                self.count0 += 1
            elif psd_number == 7:
                self.arr7[res] += 1
                self.count7 += 1

    def start(self, seconds, test_label, save=True, verbose=False, fldr=""):
        """"
        Connects to detector and reads data for given time
        Can save data (in folder if given)
        Inputs: seconds (float), test_label (string), save (bool), fldr (string)
        """
        self.sock.connect((self.ip, self.port))
        if verbose:
            print("Connected")
        self.arr0, self.arr7 = np.zeros(BINS), np.zeros(BINS)
        self.count0 = 0
        self.count7 = 0
        self.start_time = 0
        self.current_time = 0
        self.collect_8bytes(offset=True)
        if verbose:
            print("Started collecting")
        while not self.start_time:
            self.collect_8bytes()
            if self.bytes_data[0] == int.from_bytes(NEUTRON_EVENT, "big"):
                self.translate_5f()
            elif self.bytes_data[0] == int.from_bytes(INST_TIME, "big"):
                self.start_time = translate_instrument_time(self.bytes_data)
        if verbose:
            print("Exited first loop")
        while self.current_time - self.start_time < seconds:
            self.collect_8bytes()
            if self.bytes_data[0] == int.from_bytes(NEUTRON_EVENT, "big"):
                self.translate_5f()
            elif self.bytes_data[0] == int.from_bytes(INST_TIME, "big"):
                self.current_time = translate_instrument_time(self.bytes_data)
        if verbose:
            print("Exited second loop")
        self.sock.close()

        if save:
            if fldr and "/" != fldr[-1]:
                fldr += "/"
            np.savetxt(f"{fldr}{test_label}_detector0_histogram.txt", self.arr0)
            np.savetxt(f"{fldr}{test_label}_detector7_histogram.txt", self.arr7)
            plt.plot(self.arr0, label="psd 0")
            plt.plot(self.arr7, label="psd 7")
            plt.legend()
            plt.xlabel("position")
            plt.ylabel("neutron count")
            plt.title(test_label)
            plt.savefig(f"{fldr}/{test_label}_graph.png")

    def sanity_check(self, pings=SANITY_PINGS):
        """
        Prints out given number of packets
        """
        self.sock.connect((self.ip, self.port))
        print("Connected")
        self.collect_8bytes(offset=True)
        print(self.bytes_data)
        print(self.bytes_data.hex(" "))
        print(self.bytes_data[0])
        for i in range(pings-1):
            self.collect_8bytes()
            print(self.bytes_data)
            print(self.bytes_data.hex(" "))
            print(self.bytes_data[0])
            if self.bytes_data[0] == int.from_bytes(NEUTRON_EVENT, "big"):
                print(translate_neutron_data(self.bytes_data))
            elif self.bytes_data[0] == int.from_bytes(INST_TIME, "big"):
                print(translate_instrument_time(self.bytes_data))
        self.sock.close()
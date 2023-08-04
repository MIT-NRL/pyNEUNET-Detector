"""
3he_detector_reader.py
Sabine Chu
08-01-2023

Implements basic packet reader.
"""

import socket
import numpy as np
import matplotlib.pyplot as plt
from translaters import translate_instrument_time, translate_neutron_data

IP_ADDRESS = '192.168.0.17'
PORT = 23
BINS = 1024
SANITY_PINGS = 100
NEUTRON_EVENT = b"\x5f"
INST_TIME = b"\x6c"

class detector_reader:
    def __init__(self, ip_address=IP_ADDRESS, port=PORT):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        self.ip = ip_address
        self.port = port

    # def collect_8bytes(self):
    #     self.hex_data = ""
    #     for j in range(8):
    #         self.hex_data += self.sock.recv(1).hex()

    def collect_8bytes(self):
        self.bytes_data = bytearray(b"")
        for j in range(8):
            self.bytes_data += self.sock.recv(1)

    def translate_5f(self):
        # psd_number, position = translate_neutron_data(self.hex_data)
        psd_number, position = translate_neutron_data(self.bytes_data)
        if position:
            res = BINS-1 if position*BINS >= BINS else int(position*BINS)
            if psd_number == 0:
                self.arr0[res] += 1
                self.count0 += 1
            elif psd_number == 7:
                self.arr7[res] += 1
                self.count7 += 1

    def start(self, time_len, test_label, save=True):
        self.sock.connect((self.ip, self.port))
        self.arr0, self.arr7 = np.zeros(BINS), np.zeros(BINS)
        self.count0 = 0
        self.count7 = 0
        self.start_time = 0
        self.current_time = 0
        while not self.start_time:
            self.collect_8bytes()
            # if self.hex_data[:2] == "5f":
            if self.bytes_data[1] == NEUTRON_EVENT:
                self.translate_5f()
            # elif self.hex_data[:2] == "6c":
            #    self.start_time = translate_instrument_time(self.hex_data)
            elif self.bytes_data[1] == INST_TIME:
                self.start_time = translate_instrument_time(self.bytes_data)
        while self.current_time - self.start_time < time_len:
            self.collect_8bytes()
            # if self.hex_data[:2] == "5f":
            if self.bytes_data[1] == NEUTRON_EVENT:
                self.translate_5f()
            # elif self.hex_data[:2] == "6c":
            #     self.current_time = translate_instrument_time(self.hex_data)
            elif self.bytes_data[1] == INST_TIME:
                self.current_time = translate_instrument_time(self.bytes_data)
        self.sock.close()

        if save:
            np.savetxt(f"{test_label}_arr0.txt", self.arr0)
            np.savetxt(f"{test_label}_arr7.txt", self.arr7)
            plt.plot(self.arr0, label="psd 0")
            plt.plot(self.arr7, label="psd 7")
            plt.legend()
            plt.xlabel("position")
            plt.ylabel("neutron count")
            plt.title(test_label)
            plt.savefig(f"{test_label}_graph.png")

    def sanity_check(self, pings=SANITY_PINGS):
        self.sock.connect((self.ip, self.port))
        for i in range(pings):
            self.collect_8bytes()
            # if self.hex_data[:2] == "5f":
            #     print(translate_neutron_data(self.hex_data))
            # elif self.hex_data[:2] == "6c":
            #     print(translate_instrument_time(self.hex_data))
            if self.bytes_data[1] == NEUTRON_EVENT:
                print(translate_neutron_data(self.bytes_data))
            elif self.bytes_data[1] == INST_TIME:
                print(translate_instrument_time(self.bytes_data))
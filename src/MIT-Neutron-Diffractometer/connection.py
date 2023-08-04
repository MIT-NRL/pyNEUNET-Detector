import socket
with socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0) as s:
    s.connect(("192.168.0.17", 23))
#!/usr/bin/env python3
import socket, struct, sys

IFACE_IP = "172.16.42.1"
OFFER_IP = "172.16.42.2"
LEASE = 3600
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
s.bind(("0.0.0.0", 67))

def opt(code, data):
    return bytes([code, len(data)]) + data

def reply(req):
    if len(req) < 240 or req[0] != 1:
        return None
    xid = req[4:8]
    flags = req[10:12]
    chaddr = req[28:44]
    i = 240
    mtype = None
    while i < len(req):
        c = req[i]
        if c == 255: break
        if c == 0: i += 1; continue
        ln = req[i+1]; val = req[i+2:i+2+ln]
        if c == 53: mtype = val[0]
        i += 2 + ln
    if mtype not in (1, 3):
        return None
    yi = socket.inet_aton(OFFER_IP)
    si = socket.inet_aton(IFACE_IP)
    pkt = struct.pack("!BBBBIHH", 2, 1, 6, 0, struct.unpack("!I", xid)[0],
                      struct.unpack("!H", flags)[0], 0)
    pkt += socket.inet_aton("0.0.0.0") + yi + si + socket.inet_aton("0.0.0.0")
    pkt += chaddr + b"\x00"*64 + b"\x00"*128 + b"\x63\x82\x53\x63"
    if mtype == 1:
        pkt += opt(53, b"\x02")
    else:
        pkt += opt(53, b"\x05")
    pkt += opt(54, socket.inet_aton(IFACE_IP))
    pkt += opt(51, struct.pack("!I", LEASE))
    pkt += opt(1, socket.inet_aton("255.255.255.0"))
    pkt += opt(3, socket.inet_aton(IFACE_IP))
    pkt += opt(6, socket.inet_aton(IFACE_IP))
    pkt += b"\xff"
    return pkt

while True:
    data, addr = s.recvfrom(2048)
    r = reply(data)
    if r:
        s.sendto(r, ("255.255.255.255", 68))
        print("replied to", addr, flush=True)

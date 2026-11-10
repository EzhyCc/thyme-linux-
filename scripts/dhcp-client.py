#!/usr/bin/env python3
import random
import socket
import struct
import subprocess
import sys
import time

IFACE = "wlp1s0"
MAC = bytes.fromhex(open(f"/sys/class/net/{IFACE}/address").read().strip().replace(":", ""))

def build(t, xid, yi=b"\x00"*4, req=None):
    pkt = struct.pack("!BBBBIHH", 1 if t == "discover" else 1, 1, 6, 0,
                      xid, 0, 0x8000)
    pkt += b"\x00"*4 + yi + b"\x00"*4 + b"\x00"*4
    pkt += MAC + b"\x00"*10 + b"\x00"*64 + b"\x00"*128
    pkt += b"\x63\x82\x53\x63"
    pkt += bytes([53, 1, 1 if t == "discover" else 3])
    if req:
        pkt += bytes([50, 4]) + req
    pkt += bytes([55, 3, 1, 3, 6])
    pkt += b"\xff"
    return pkt

def parse(data):
    if len(data) < 240: return None
    yi = data[16:20]
    i = 240
    opts = {}
    while i < len(data):
        c = data[i]
        if c == 255: break
        if c == 0: i += 1; continue
        ln = data[i+1]; opts[c] = data[i+2:i+2+ln]; i += 2 + ln
    return yi, opts

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", 68))
xid = random.randint(1, 0xFFFFFFFF)
s.sendto(build("discover", xid), ("255.255.255.255", 67))
s.settimeout(8)
try:
    data, _ = s.recvfrom(2048)
except socket.timeout:
    print("NO_OFFER"); sys.exit(1)
yi, opts = parse(data)
print("offer", socket.inet_ntoa(yi))
s.sendto(build("request", xid, yi, yi), ("255.255.255.255", 67))
try:
    data, _ = s.recvfrom(2048)
except socket.timeout:
    print("NO_ACK"); sys.exit(1)
yi, opts = parse(data)
ip = socket.inet_ntoa(yi)
mask = socket.inet_ntoa(opts.get(1, b"\xff\xff\xff\x00"))
gw = socket.inet_ntoa(opts[3]) if 3 in opts else None
print("lease", ip, mask, gw)
subprocess.run(["ip", "addr", "flush", "dev", IFACE])
subprocess.run(["ip", "addr", "add", f"{ip}/24", "dev", IFACE])
if gw:
    subprocess.run(["ip", "route", "replace", "default", "via", gw, "dev", IFACE])
print("configured")

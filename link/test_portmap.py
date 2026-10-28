"""link/portmap.py against fake routers: NAT-PMP's two replies, and a UPnP router's SSDP answer,
description and SOAP control (design/M14-relay.md step 3, criterion 3).

    python link/test_portmap.py"""

import socket
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from link import portmap  # noqa: E402


class FakeSock:
    """A socket whose replies come from `answer(data, dst) -> bytes or None`."""

    def __init__(self, answer):
        self.answer, self.replies, self.sent = answer, [], []

    def __call__(self, *a):
        return self

    def settimeout(self, t):
        pass

    def sendto(self, data, dst):
        self.sent.append((data, dst))
        r = self.answer(data, dst)
        if r is not None:
            self.replies.append((r, dst))

    def recvfrom(self, n):
        if not self.replies:
            raise socket.timeout()
        return self.replies.pop(0)

    def close(self):
        pass


def natpmp_router(data, dst):
    if dst[1] != portmap.NATPMP_PORT:
        return None
    if data[1] == 0:  # public address
        return struct.pack(">BBHI4s", 0, 128, 0, 1, socket.inet_aton("198.51.100.7"))
    ver, op, _, inner, ext, lease = struct.unpack(">BBHHHI", data[:12])
    return struct.pack(">BBHIHHI", 0, 128 + op, 0, 1, inner, inner, lease)


DESC = """<root><device><serviceList><service>
<serviceType>urn:schemas-upnp-org:service:WANIPConnection:1</serviceType>
<controlURL>/ctl/IPConn</controlURL></service></serviceList></device></root>"""


def main():
    fails = []

    def check(ok, what):
        print(("ok   " if ok else "FAIL ") + what)
        if not ok:
            fails.append(what)

    got = portmap.natpmp_map(47811, "192.168.1.1", sock_factory=FakeSock(natpmp_router))
    check(got == ("198.51.100.7", 47811), f"NAT-PMP: mapped, public address known ({got})")
    got = portmap.natpmp_map(47811, "192.168.1.1", sock_factory=FakeSock(lambda d, a: None), wait=0.1)
    check(got is None, "NAT-PMP: a router that doesn't answer is skipped")

    calls = []

    def fetch(url, data=None, headers=None):
        calls.append((url, headers.get("SOAPAction") if headers else None, data))
        if data is None:
            return DESC
        if b"GetExternalIPAddress" in data:
            return "<NewExternalIPAddress>198.51.100.9</NewExternalIPAddress>"
        return "<ok/>"
    ssdp = lambda d, a: b"HTTP/1.1 200 OK\r\nLOCATION: http://192.168.1.1:5000/rootDesc.xml\r\n\r\n" if a == portmap.SSDP else None
    got = portmap.upnp_map(47811, "192.168.1.20", sock_factory=FakeSock(ssdp), fetch=fetch)
    add = next((c for c in calls if c[1] and "AddPortMapping" in c[1]), None)
    check(got == ("198.51.100.9", 47811) and add and add[0] == "http://192.168.1.1:5000/ctl/IPConn"
          and b"<NewInternalClient>192.168.1.20</NewInternalClient>" in add[2] and b"<NewProtocol>UDP" in add[2],
          f"UPnP: found by SSDP, the port mapped to this PC, public address known ({got})")
    got = portmap.upnp_map(47811, "192.168.1.20", sock_factory=FakeSock(lambda d, a: None), fetch=fetch, wait=0.1)
    check(got is None, "UPnP: no gateway answering is skipped")
    print(f"\n{'all passed' if not fails else f'{len(fails)} FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

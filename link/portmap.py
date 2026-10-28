"""Asking the home router to open the game's port (design/M14-relay.md, step 3): NAT-PMP (RFC 6886,
Apple's, and most routers' PCP ports answer it too) and UPnP IGD (the common one). With the port
open, the game is reachable from anywhere, so even a router that gives a new port per destination
("symmetric") lets the partner in, and a launcher can relay for others.

    m = map_port(port)   # -> (public ip, public port) or None, within about 2 s (it expires: LEASE_S)

Both are tried at once; whichever answers first wins. Nothing here is required: a router without
either is skipped quickly, and the other ways in (hole punching, the relay) still work."""

import logging
import re
import socket
import struct
import threading
import time
import urllib.request

log = logging.getLogger(__name__)
LEASE_S = 2 * 3600
NATPMP_PORT = 5351
SSDP = ("239.255.255.250", 1900)
WAIT_S = 2.0
DESCRIPTION = "SOTN Co-op"


def gateway_ip():
    """The default gateway (the home router), or None."""
    try:  # Linux and Android
        with open("/proc/net/route") as f:
            for line in f.readlines()[1:]:
                fields = line.split()
                if fields[1] == "00000000" and int(fields[3], 16) & 2:
                    return socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
    except OSError:
        pass
    try:  # Windows, macOS: the router is usually the LAN address's .1
        from .rendezvous import local_ip
        return local_ip().rsplit(".", 1)[0] + ".1"
    except Exception:  # noqa: BLE001
        return None


# --- NAT-PMP -------------------------------------------------------------------------------------
def natpmp_map(port, gateway, sock_factory=socket.socket, lease=LEASE_S, wait=WAIT_S):
    """Maps UDP `port` on the router: (public ip, public port) or None."""
    s = sock_factory(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(wait / 2)
        s.sendto(struct.pack(">BBH", 0, 0, 0), (gateway, NATPMP_PORT))  # the public address
        data, _ = s.recvfrom(64)
        if len(data) < 12 or struct.unpack(">BBH", data[:4])[2] != 0:
            return None
        ip = socket.inet_ntoa(data[8:12])
        s.sendto(struct.pack(">BBHHHI", 0, 1, 0, port, port, lease), (gateway, NATPMP_PORT))  # map UDP
        data, _ = s.recvfrom(64)
        if len(data) < 16:
            return None
        _, op, result, _, inner, public, _ = struct.unpack(">BBHIHHI", data[:16])
        return (ip, public) if op == 129 and result == 0 and inner == port else None
    except OSError:
        return None
    finally:
        s.close()


# --- UPnP IGD ------------------------------------------------------------------------------------
SEARCH = ("M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: \"ssdp:discover\"\r\nMX: 1\r\n"
          "ST: urn:schemas-upnp-org:device:InternetGatewayDevice:1\r\n\r\n")
SERVICES = ("urn:schemas-upnp-org:service:WANIPConnection:1", "urn:schemas-upnp-org:service:WANIPConnection:2",
            "urn:schemas-upnp-org:service:WANPPPConnection:1")


def _soap(url, service, action, args, fetch):
    body = "".join(f"<{k}>{v}</{k}>" for k, v in args)
    envelope = ('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
                's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body>'
                f'<u:{action} xmlns:u="{service}">{body}</u:{action}></s:Body></s:Envelope>')
    return fetch(url, envelope.encode(), {"Content-Type": 'text/xml; charset="utf-8"',
                                          "SOAPAction": f'"{service}#{action}"'})


def _http(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=WAIT_S) as r:
        return r.read().decode("utf-8", "replace")


def upnp_map(port, lan_ip, sock_factory=socket.socket, fetch=_http, lease=LEASE_S, wait=WAIT_S):
    """Maps UDP `port` to lan_ip:port through the router's UPnP IGD: (public ip, port) or None."""
    s = sock_factory(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(wait)
        s.sendto(SEARCH.encode(), SSDP)
        data, addr = s.recvfrom(4096)
        m = re.search(rb"(?im)^location:\s*(\S+)", data)
        if not m:
            return None
        location = m.group(1).decode()
        desc = fetch(location)
        base = re.match(r"(https?://[^/]+)", location).group(1)
        for service in SERVICES:
            block = re.search(re.escape(service) + r".*?<controlURL>(.*?)</controlURL>", desc, re.S)
            if not block:
                continue
            control = block.group(1)
            url = control if control.startswith("http") else base + ("" if control.startswith("/") else "/") + control
            _soap(url, service, "AddPortMapping", [
                ("NewRemoteHost", ""), ("NewExternalPort", port), ("NewProtocol", "UDP"),
                ("NewInternalPort", port), ("NewInternalClient", lan_ip), ("NewEnabled", 1),
                ("NewPortMappingDescription", DESCRIPTION), ("NewLeaseDuration", lease)], fetch)
            reply = _soap(url, service, "GetExternalIPAddress", [], fetch)
            ip = re.search(r"<NewExternalIPAddress>([\d.]+)</NewExternalIPAddress>", reply)
            return (ip.group(1), port) if ip else None
        return None
    except (OSError, AttributeError, ValueError):
        return None
    finally:
        s.close()


def map_port(port, lan_ip=None, gateway=None, **kw):
    """Both ways at once; the first answer. (public ip, public port) or None, within WAIT_S."""
    from .rendezvous import local_ip
    lan_ip = lan_ip or local_ip()
    gateway = gateway or gateway_ip()
    found = []
    tries = [threading.Thread(target=lambda: found.append(upnp_map(port, lan_ip, **kw)), daemon=True)]
    if gateway:
        tries.append(threading.Thread(target=lambda: found.append(natpmp_map(port, gateway, **kw)), daemon=True))
    for t in tries:
        t.start()
    deadline = time.monotonic() + WAIT_S + 0.5
    while time.monotonic() < deadline:
        hit = next((f for f in found if f), None)
        if hit or len(found) == len(tries):
            log.info("port %d on the router: %s", port, hit or "no UPnP or NAT-PMP")
            return hit
        time.sleep(0.02)
    return None

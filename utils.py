# // FILE: utils.py
import socket
import ctypes
import sys
import base64
import json
import binascii
from logger_config import logger

def encode_connection_code(ip):
    """
    # NOTE: Not encryption, just obfuscation so users don't freak out about sharing raw IPs.
    Simple Base64 encoding of the IP to create a shareable code.
    Format: GSP-[Base64]
    """
    try:
        # TODO: Add version byte? Overkill for now.
        b64 = base64.urlsafe_b64encode(ip.encode("utf-8")).decode("ascii").rstrip("=")
        return f"GSP-{b64}"
    except Exception:
        return "ERROR"

def decode_connection_code(code):
    """
    Decodes GSP-XXXX back to an IP address.
    """
    try:
        code = code.strip()
        if code.startswith("GSP-"):
            code = code[4:]
        
        # Add padding back if missing
        pad = len(code) % 4
        if pad > 0:
            code += "=" * (4 - pad)
            
        ip = base64.urlsafe_b64decode(code).decode("utf-8")
        # TODO: Regex validate 'ip' to ensure it's actually an IP address
        return ip
    except Exception:
        return None

def get_local_ip():
    """
    Attempts to retrieve the local IP address of the machine.
    # TODO: This UDP trick is clever but verify it works heavily restricted VPNs.
    Prioritizes the 'UDP Connect Trick'.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if not ip.startswith("127."):
            return ip
    except Exception:
        pass

    try:
        hostname = socket.gethostname()
        addrinfo = socket.getaddrinfo(hostname, None, family=socket.AF_INET)
        for _, _, _, _, sockaddr in addrinfo:
            ip = sockaddr[0]
            if ip.startswith("192.168.") or ip.startswith("10."):
                return ip
    except Exception:
        pass

    return "127.0.0.1"

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)

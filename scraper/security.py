import ipaddress
import re
import socket
import logging
from urllib.parse import urlparse
from typing import Optional

logger = logging.getLogger("zerodaily.security")

# Disallowed private, loopback, and cloud metadata networks
DISALLOWED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),          # Current network
    ipaddress.ip_network("10.0.0.0/8"),         # Private-Use (RFC 1918)
    ipaddress.ip_network("100.64.0.0/10"),      # Shared Address Space
    ipaddress.ip_network("127.0.0.0/8"),        # Loopback
    ipaddress.ip_network("169.254.0.0/16"),     # Link-Local (including AWS IMDS 169.254.169.254)
    ipaddress.ip_network("172.16.0.0/12"),      # Private-Use (RFC 1918)
    ipaddress.ip_network("192.0.0.0/24"),       # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),       # TEST-NET-1
    ipaddress.ip_network("192.88.99.0/24"),     # 6to4 Relay Anycast
    ipaddress.ip_network("192.168.0.0/16"),     # Private-Use (RFC 1918)
    ipaddress.ip_network("198.18.0.0/15"),      # Network Interconnect Benchmarking
    ipaddress.ip_network("198.51.100.0/24"),    # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),     # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),        # Multicast
    ipaddress.ip_network("240.0.0.0/4"),        # Reserved
    ipaddress.ip_network("255.255.255.255/32"), # Limited Broadcast
    ipaddress.ip_network("::1/128"),            # IPv6 Loopback
    ipaddress.ip_network("::/128"),             # IPv6 Unspecified
    ipaddress.ip_network("fc00::/7"),           # IPv6 Unique Local
    ipaddress.ip_network("fe80::/10"),          # IPv6 Link-Local
]


def is_ip_disallowed(ip_obj) -> bool:
    """Checks if an IPv4 or IPv6 address belongs to any disallowed/private network."""
    for network in DISALLOWED_NETWORKS:
        if ip_obj in network:
            return True
    return False


def is_safe_url(url: Optional[str], resolve_dns: bool = True) -> bool:
    """
    Validates URL to protect against SSRF, internal port scanning,
    cloud metadata exploitation (169.254.169.254), and malformed protocols.
    """
    if not url or not isinstance(url, str):
        return False

    url_str = url.strip()
    if len(url_str) > 2048:
        return False

    try:
        parsed = urlparse(url_str)
    except Exception:
        return False

    # 1. Enforce HTTP/HTTPS only
    if parsed.scheme.lower() not in ("http", "https"):
        return False

    # 2. Reject credentials in URL (e.g. http://user:pass@host)
    if parsed.username or parsed.password:
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    hostname = hostname.strip().lower()

    # 3. Check for obvious localhost / loopback aliases
    if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"):
        logger.warning(f"[SECURITY] Blocked SSRF attempt to forbidden hostname: {hostname}")
        return False

    # 4. Check if hostname is an IP literal
    try:
        ip_obj = ipaddress.ip_address(hostname)
        if is_ip_disallowed(ip_obj):
            logger.warning(f"[SECURITY] Blocked SSRF attempt to disallowed IP: {ip_obj}")
            return False
    except ValueError:
        # Not an IP literal, it's a domain name
        pass

    # 5. Resolve DNS if requested
    if resolve_dns:
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for family, _, _, _, sockaddr in addr_info:
                ip_str = sockaddr[0]
                ip_obj = ipaddress.ip_address(ip_str)
                if is_ip_disallowed(ip_obj):
                    logger.warning(
                        f"[SECURITY] Blocked SSRF DNS resolution to disallowed IP {ip_str} for host {hostname}"
                    )
                    return False
        except socket.gaierror:
            logger.warning(f"[SECURITY] DNS resolution failed for host: {hostname}")
            return False
        except Exception as e:
            logger.warning(f"[SECURITY] Error resolving DNS for {hostname}: {e}")
            return False

    return True


def sanitize_text(text: Optional[str], max_length: int = 10000) -> str:
    """
    Strips control characters, dangerous HTML tags, and truncates text.
    """
    if not text or not isinstance(text, str):
        return ""

    # Remove null bytes
    cleaned = text.replace("\x00", "")

    # Strip script, iframe, object, embed, style tags and content
    cleaned = re.sub(
        r"<\s*(script|iframe|object|embed|style)[^>]*>.*?<\s*/\s*\1\s*>",
        "",
        cleaned,
        flags=re.DOTALL | re.IGNORECASE
    )
    cleaned = re.sub(
        r"<\s*(script|iframe|object|embed|style)[^>]*>",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    # Strip javascript: pseudo-protocol
    cleaned = re.sub(r"javascript\s*:", "", cleaned, flags=re.IGNORECASE)

    return cleaned[:max_length].strip()

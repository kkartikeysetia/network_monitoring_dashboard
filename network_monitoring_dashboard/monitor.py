"""Lightweight HTTP/TCP service checks for the NOC demo."""
from __future__ import annotations

import socket
import time
from urllib.parse import urlparse

import requests


def check_service(service: dict, timeout: float = 4.0, force_down: bool = False) -> dict:
    """Check DNS, TCP connectivity and HTTP response for one service."""
    checked_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    url = service["url"]
    parsed = urlparse(url)
    host = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    started = time.perf_counter()
    resolved_ip = ""
    http_status = None
    diagnosis = ""
    status = "UP"

    if force_down:
        return {
            "service": service["name"], "url": url, "status": "DOWN",
            "latency_ms": 0, "http_status": None, "resolved_ip": "demo",
            "diagnosis": "Simulated outage for demonstration; no real service was changed.",
            "checked_at": checked_at, "is_simulated": 1,
        }

    try:
        resolved_ip = socket.gethostbyname(host)
    except socket.gaierror as exc:
        status = "DOWN"
        diagnosis = f"DNS lookup failed for {host}: {exc}"

    if status == "UP":
        try:
            # A TCP connection test helps distinguish reachability from HTTP failure.
            with socket.create_connection((host, port), timeout=timeout):
                pass
        except OSError as exc:
            status = "DOWN"
            diagnosis = f"TCP connection to {host}:{port} failed: {exc}"

    if status == "UP":
        try:
            response = requests.get(
                url, timeout=timeout, allow_redirects=True,
                headers={"User-Agent": "NOC-Monitor-Demo/1.0"},
            )
            http_status = response.status_code
            if response.status_code >= 500:
                status = "DOWN"
                diagnosis = f"Server returned HTTP {response.status_code}."
            elif response.status_code >= 400:
                status = "DEGRADED"
                diagnosis = f"Endpoint reachable but returned HTTP {response.status_code}."
            else:
                diagnosis = f"DNS resolved to {resolved_ip}; TCP and HTTP checks passed (HTTP {response.status_code})."
        except requests.RequestException as exc:
            status = "DOWN"
            diagnosis = f"HTTP request failed: {exc}"

    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    if status == "UP" and latency_ms >= 2500:
        status = "DEGRADED"
        diagnosis = f"Service reachable but response time is high ({latency_ms} ms)."

    return {
        "service": service["name"], "url": url, "status": status,
        "latency_ms": latency_ms, "http_status": http_status,
        "resolved_ip": resolved_ip, "diagnosis": diagnosis,
        "checked_at": checked_at, "is_simulated": 0,
    }

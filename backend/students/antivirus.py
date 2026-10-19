"""
EduSekai Antivirus / Anti-Malware Scanner Service

Provides pure-Python ClamAV daemon (clamd) TCP streaming client integration.
Does not require external C libraries or third-party wrappers (such as pyclamd).
Complies with fail-closed security policy: if ClamAV is enabled but unreachable
or times out, the upload fails closed and remains quarantined.
"""

import logging
import os
import socket
import struct
from django.conf import settings

logger = logging.getLogger(__name__)

CHUNK_SIZE = 64 * 1024  # 64KB chunks for streaming to clamd


def ping_clamav(host: str = None, port: int = None, timeout: float = 3.0) -> bool:
    """
    Sends a PING command to ClamAV daemon to verify connectivity.
    Returns True if PONG is received, False otherwise.
    """
    host = host or getattr(settings, "CLAMAV_HOST", "localhost")
    port = port or getattr(settings, "CLAMAV_PORT", 3310)

    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall(b"zPING\0")
            response = sock.recv(16)
            return b"PONG" in response
    except Exception as exc:
        logger.debug("ClamAV ping failed on %s:%s: %s", host, port, exc)
        return False


def scan_file_for_malware(file_obj, filename: str = "") -> tuple[bool, str, str]:
    """
    Streams a file or file-like object to ClamAV daemon (clamd) via TCP INSTREAM.

    Returns:
        (is_clean: bool, scan_status: str, scan_details: str)
        where scan_status is one of: 'clean', 'infected', 'error'
    """
    enabled = getattr(settings, "CLAMAV_ENABLED", False)
    fail_closed = getattr(settings, "CLAMAV_FAIL_CLOSED", True)
    host = getattr(settings, "CLAMAV_HOST", "localhost")
    port = getattr(settings, "CLAMAV_PORT", 3310)
    timeout = getattr(settings, "CLAMAV_TIMEOUT_SECONDS", 10)

    # In dev or test environments when ClamAV is disabled:
    if not enabled:
        if getattr(settings, "CLAMAV_FORCE_FAIL_CLOSED", False):
            return (
                False,
                "error",
                "Antivirus scanning is disabled while CLAMAV_FORCE_FAIL_CLOSED is active. Failing closed.",
            )
        return (
            True,
            "clean",
            "Antivirus scan bypassed (CLAMAV_ENABLED=False in current environment).",
        )

    # Save and restore file read position
    orig_pos = 0
    if hasattr(file_obj, "tell"):
        try:
            orig_pos = file_obj.tell()
        except (OSError, AttributeError):
            orig_pos = 0

    if hasattr(file_obj, "seek"):
        try:
            file_obj.seek(0)
        except (OSError, AttributeError):
            pass

    safe_name = os.path.basename(filename or getattr(file_obj, "name", "document"))

    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            # Send zINSTREAM (null-terminated command)
            sock.sendall(b"zINSTREAM\0")

            while True:
                chunk = file_obj.read(CHUNK_SIZE)
                if not chunk:
                    break

                # Protocol: 4-byte big-endian unsigned integer length, followed by chunk bytes
                length_prefix = struct.pack("!I", len(chunk))
                sock.sendall(length_prefix + chunk)

            # Protocol: 4-byte zero length indicates end of stream
            sock.sendall(b"\x00\x00\x00\x00")

            # Receive result
            response_chunks = []
            while True:
                data = sock.recv(1024)
                if not data:
                    break
                response_chunks.append(data)

            raw_response = b"".join(response_chunks).decode("utf-8", errors="replace").strip("\x00\r\n ")

        # Interpret clamd INSTREAM response:
        # Format 1: "stream: OK"
        # Format 2: "stream: <SignatureName> FOUND"
        # Format 3: "stream: ... ERROR"
        if raw_response.endswith("OK"):
            logger.info("ClamAV scan passed for document '%s'", safe_name)
            return (True, "clean", "Passed ClamAV antivirus inspection.")

        if "FOUND" in raw_response:
            # Extract virus signature name (e.g., 'stream: Eicar-Signature FOUND')
            parts = raw_response.split(":")
            sig_name = parts[1].replace("FOUND", "").strip() if len(parts) > 1 else "Malware Signature Detected"
            logger.warning(
                "SECURITY ALERT: Malware detected in uploaded document '%s'. Signature: %s",
                safe_name,
                sig_name,
            )
            return (False, "infected", f"Malware signature detected: {sig_name}")

        logger.error("ClamAV unexpected response for document '%s': %s", safe_name, raw_response)
        return (False, "error", f"ClamAV scan error: {raw_response[:100]}")

    except (socket.timeout, TimeoutError) as err:
        logger.error("ClamAV scan timed out for document '%s' after %ss: %s", safe_name, timeout, err)
        return (
            False,
            "error",
            f"Antivirus scan timed out ({timeout}s). Quarantined in fail-closed state.",
        )

    except (ConnectionRefusedError, socket.gaierror, OSError) as err:
        logger.error("ClamAV scanner connection failed on %s:%s for '%s': %s", host, port, safe_name, err)
        if fail_closed:
            return (
                False,
                "error",
                "Antivirus scanner unreachable or connection refused. Quarantined in fail-closed state.",
            )
        return (True, "clean", "Antivirus scanner unavailable; fail-open override active.")

    finally:
        if hasattr(file_obj, "seek"):
            try:
                file_obj.seek(orig_pos)
            except (OSError, AttributeError):
                pass


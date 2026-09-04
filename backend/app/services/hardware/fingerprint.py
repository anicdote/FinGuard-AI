"""Backend-only adapter for the Arduino fingerprint controller.

Fingerprint images and templates never leave the sensor.  The only value sent
to the controller is the server-selected template slot for the current user.
"""

import asyncio
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

try:
    import serial
    from serial import SerialException
except ImportError:  # makes disabled-hardware development/test environments usable
    serial = None
    SerialException = OSError

from app.core.config import settings

logger = logging.getLogger("finguard.hardware.fingerprint")


class HardwareUnavailableError(RuntimeError):
    pass


class HardwareBusyError(RuntimeError):
    pass


@dataclass
class VerificationResult:
    status: str
    success: bool
    detail: str
    fingerprint_id: Optional[int] = None


class ArduinoFingerprintService:
    """One complete serial operation owns the shared Arduino connection."""

    def __init__(self) -> None:
        self._operation_lock = asyncio.Lock()
        self._active_request_id: Optional[str] = None
        self._last_error: Optional[str] = None

    async def status(self) -> dict:
        if not settings.HARDWARE_ENABLED:
            return self._status(False, "disabled", "Hardware integration is disabled by configuration.")
        if self._active_request_id:
            return self._status(True, "busy", "Fingerprint verification is in progress.")
        try:
            async with self._operation_lock:
                await asyncio.to_thread(self._probe_blocking)
            return self._status(True, "ready", "Arduino biometric controller is ready.")
        except HardwareUnavailableError as exc:
            return self._status(False, "unavailable", str(exc))

    async def reserve(self, request_id: str) -> None:
        if not settings.HARDWARE_ENABLED:
            raise HardwareUnavailableError("Biometric hardware is disabled by server configuration.")
        if self._operation_lock.locked() or self._active_request_id:
            raise HardwareBusyError("Another fingerprint verification is already in progress.")
        await self._operation_lock.acquire()
        self._active_request_id = request_id

    async def release(self, request_id: str) -> None:
        if self._active_request_id != request_id:
            return
        self._active_request_id = None
        if self._operation_lock.locked():
            self._operation_lock.release()

    async def verify(
        self, request_id: str, expected_fingerprint_id: int, purpose: str,
        progress_callback: Optional[Callable[[str], Awaitable[None]]] = None,
        reserved: bool = False,
    ) -> VerificationResult:
        if not settings.HARDWARE_ENABLED:
            raise HardwareUnavailableError("Biometric hardware is disabled by server configuration.")
        if reserved:
            if self._active_request_id != request_id:
                raise HardwareBusyError("Fingerprint reservation was lost.")
        else:
            await self.reserve(request_id)
        loop = asyncio.get_running_loop()

        def report_progress(state: str) -> None:
            if progress_callback is not None:
                asyncio.run_coroutine_threadsafe(progress_callback(state), loop).result(timeout=5)

        try:
            # Long opaque HTTP challenge ids can overflow sketch serial buffers.
            wire_id = secrets.token_hex(4)
            operation = asyncio.create_task(asyncio.to_thread(
                self._verify_blocking, wire_id, expected_fingerprint_id, purpose.upper(), report_progress))
            try:
                return await asyncio.shield(operation)
            except asyncio.CancelledError:
                # Do not unlock the port while its worker thread still owns it.
                await asyncio.shield(operation)
                raise
        finally:
            await self.release(request_id)

    async def enroll(self, request_id: str, fingerprint_id: int) -> VerificationResult:
        if not settings.HARDWARE_ENABLED:
            raise HardwareUnavailableError("Biometric hardware is disabled by server configuration.")
        async with self._operation_lock:
            if self._active_request_id:
                raise HardwareBusyError("Another fingerprint operation is already in progress.")
            self._active_request_id = request_id
            try:
                return await asyncio.to_thread(self._enroll_blocking, secrets.token_hex(4), fingerprint_id)
            finally:
                self._active_request_id = None

    async def push_display(self, line1: str, line2: str, color: str = "") -> VerificationResult:
        """Use the teammate DISPLAY protocol without interleaving a scan."""
        if not settings.HARDWARE_ENABLED:
            raise HardwareUnavailableError("Biometric hardware is disabled by server configuration.")
        if self._operation_lock.locked() or self._active_request_id:
            raise HardwareBusyError("Fingerprint controller is busy; display push skipped.")
        async with self._operation_lock:
            return await asyncio.to_thread(self._display_blocking, secrets.token_hex(4), line1, line2, color)

    def _status(self, available: bool, state: str, detail: str) -> dict:
        return {"available": available, "state": state, "detail": detail,
                "port": settings.ARDUINO_SERIAL_PORT, "baud_rate": settings.ARDUINO_BAUD_RATE,
                "active_request_id": self._active_request_id, "last_error": self._last_error}

    def _connect_blocking(self):
        if serial is None:
            raise HardwareUnavailableError("pyserial is not installed on the backend host.")
        try:
            port = serial.Serial(port=settings.ARDUINO_SERIAL_PORT,
                                 baudrate=settings.ARDUINO_BAUD_RATE,
                                 timeout=0.25,
                                 write_timeout=settings.ARDUINO_CONNECT_TIMEOUT_SEC)
            # Opening an Uno commonly resets it; do not send commands until setup completed.
            time.sleep(settings.ARDUINO_RESET_DELAY_SEC)
            port.reset_input_buffer()
            return port
        except (SerialException, OSError) as exc:
            self._last_error = str(exc)
            raise HardwareUnavailableError(
                f"Arduino unavailable on {settings.ARDUINO_SERIAL_PORT}: {exc}") from exc

    @staticmethod
    def _close(port) -> None:
        if port is not None:
            try:
                port.close()
            except Exception:
                pass

    @staticmethod
    def _write(port, message: str) -> None:
        port.write(f"{message}\n".encode("ascii"))
        port.flush()

    @staticmethod
    def _read(port) -> str:
        raw = port.readline()
        return raw.decode("ascii", errors="ignore").strip() if raw else ""

    def _probe_blocking(self) -> None:
        port = None
        try:
            port = self._connect_blocking()
            self._write(port, "PING")
            deadline = time.monotonic() + settings.ARDUINO_CONNECT_TIMEOUT_SEC
            while time.monotonic() < deadline:
                if self._read(port) == "PONG":
                    return
            raise HardwareUnavailableError("Arduino did not answer the PING health check.")
        finally:
            self._close(port)

    def _verify_blocking(self, wire_id: str, expected_id: int, purpose: str,
                         progress: Callable[[str], None]) -> VerificationResult:
        port = None
        try:
            port = self._connect_blocking()
            port.reset_input_buffer()
            self._write(port, f"VERIFY {wire_id} {expected_id} {purpose}")
            deadline = time.monotonic() + settings.FINGERPRINT_VERIFY_TIMEOUT_SEC + 5
            while time.monotonic() < deadline:
                response = self._read(port)
                if not response:
                    continue
                parts = response.split()
                if len(parts) < 2 or parts[1] != wire_id:
                    continue
                event = parts[0]
                if event == "FINGER_REQUIRED":
                    progress("finger_required")
                elif event == "VERIFYING":
                    progress("verifying")
                elif event == "FINGER_SUCCESS" and len(parts) >= 3:
                    try:
                        matched = int(parts[2])
                    except ValueError:
                        return VerificationResult("hardware_error", False, "Arduino returned an invalid fingerprint ID.")
                    if matched == expected_id:
                        return VerificationResult("success", True, "Registered fingerprint verified.", matched)
                    return VerificationResult("failed", False, "Fingerprint does not belong to the requested user.", matched)
                elif event == "FINGER_FAILED":
                    return VerificationResult("failed", False, "Fingerprint was not recognized.")
                elif event == "TIMEOUT":
                    return VerificationResult("timeout", False, "Fingerprint verification timed out.")
                elif event == "HARDWARE_ERROR":
                    return VerificationResult("hardware_error", False, "Fingerprint sensor reported an error.")
            return VerificationResult("timeout", False, "Fingerprint controller did not return a result before timeout.")
        except (SerialException, OSError, ValueError) as exc:
            self._last_error = str(exc)
            logger.exception("Arduino fingerprint verification failed")
            return VerificationResult("hardware_error", False, "USB serial communication failed.")
        finally:
            self._close(port)

    def _enroll_blocking(self, wire_id: str, fingerprint_id: int) -> VerificationResult:
        port = None
        try:
            port = self._connect_blocking()
            port.reset_input_buffer()
            self._write(port, f"ENROLL {wire_id} {fingerprint_id}")
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                parts = self._read(port).split()
                if len(parts) < 2 or parts[1] != wire_id:
                    continue
                if parts[0] == "ENROLL_SUCCESS":
                    return VerificationResult("success", True, "Fingerprint template enrolled.", fingerprint_id)
                if parts[0] == "ENROLL_FAILED":
                    return VerificationResult("failed", False, "Fingerprint enrollment failed.")
                if parts[0] == "TIMEOUT":
                    return VerificationResult("timeout", False, "Fingerprint enrollment timed out.")
                if parts[0] == "HARDWARE_ERROR":
                    return VerificationResult("hardware_error", False, "Fingerprint sensor reported an error.")
            return VerificationResult("timeout", False, "Fingerprint enrollment timed out.")
        except (SerialException, OSError) as exc:
            self._last_error = str(exc)
            return VerificationResult("hardware_error", False, "USB serial communication failed.")
        finally:
            self._close(port)

    def _display_blocking(self, wire_id: str, line1: str, line2: str, color: str) -> VerificationResult:
        port = None
        try:
            port = self._connect_blocking()
            # BOOT_READY is emitted by the sketch after its SoftwareSerial setup.
            boot_deadline = time.monotonic() + settings.ARDUINO_RESET_DELAY_SEC
            while time.monotonic() < boot_deadline:
                if self._read(port) == "BOOT_READY":
                    break
            port.reset_input_buffer()
            self._write(port, f"DISPLAY {wire_id} {line1.replace('|', '/')}|{line2.replace('|', '/')}|{color}")
            deadline = time.monotonic() + settings.LCD_DISPLAY_TIMEOUT_SEC
            while time.monotonic() < deadline:
                parts = self._read(port).split()
                if len(parts) >= 2 and parts[1] == wire_id:
                    if parts[0] == "DISPLAY_OK":
                        return VerificationResult("success", True, "Display updated.")
                    if parts[0] == "HARDWARE_ERROR":
                        return VerificationResult("hardware_error", False, "Arduino reported a display error.")
            return VerificationResult("timeout", False, "No acknowledgement from Arduino for display update.")
        except (SerialException, OSError) as exc:
            self._last_error = str(exc)
            return VerificationResult("hardware_error", False, "USB serial communication failed.")
        finally:
            self._close(port)


fingerprint_service = ArduinoFingerprintService()

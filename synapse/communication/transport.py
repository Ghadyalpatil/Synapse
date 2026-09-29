"""
SYNAPSE — TCP Transport Layer
Provides reliable point-to-point length-prefixed TCP client and server
with connection lifecycle management, timeouts, and delivery ACKs.
"""

import asyncio
import logging
import time
from typing import Any, Callable, Dict, Optional, Tuple

from .protocol import frame_message, read_framed_message

logger = logging.getLogger("synapse.transport")


class TcpTransportClient:
    """Async TCP client for sending framed SYNAPSE messages and awaiting ACKs."""

    def __init__(self, timeout: float = 4.0):
        self.timeout = timeout

    async def send_message(self, ip: str, port: int, message_dict: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Sends a framed message to ip:port and awaits framed ACK.
        Returns: (success: bool, ack_response: Optional[dict], error_msg: Optional[str])
        """
        writer = None
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=self.timeout
            )

            # Send framed payload
            data = frame_message(message_dict)
            writer.write(data)
            await writer.drain()

            # Read framed ACK response
            ack = await read_framed_message(reader, timeout=self.timeout)

            if ack and ack.get("status") in ("ACK", "DELIVERED"):
                return True, ack, None
            elif ack:
                return False, ack, f"Non-ACK response: {ack.get('status')}"
            else:
                return False, None, "No ACK received from peer (connection closed)"

        except asyncio.TimeoutError:
            return False, None, f"Connection/read timed out after {self.timeout}s to {ip}:{port}"
        except ConnectionRefusedError:
            return False, None, f"Connection refused by {ip}:{port}"
        except Exception as e:
            return False, None, f"TCP send error: {str(e)}"
        finally:
            if writer:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

    async def ping_probe(self, ip: str, port: int, timeout: float = 2.0) -> Tuple[bool, Optional[float]]:
        """
        Lightweight connection liveness check.
        Returns: (is_alive, latency_ms)
        """
        writer = None
        start = time.monotonic()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=timeout
            )
            latency = (time.monotonic() - start) * 1000.0
            return True, round(latency, 2)
        except Exception:
            return False, None
        finally:
            if writer:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass


class TcpTransportServer:
    """Async TCP server listening for framed messages, invoking callback, and sending ACKs."""

    def __init__(self, host: str, port: int, message_handler: Callable[[Dict[str, Any]], Any]):
        self.host = host
        self.port = port
        self.message_handler = message_handler
        self._server: Optional[asyncio.AbstractServer] = None
        self._is_running = False

    async def start(self):
        """Starts the TCP server."""
        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port
        )
        self._is_running = True
        logger.info(f"TCP Transport Server active on {self.host}:{self.port}")

    async def stop(self):
        """Stops the TCP server and closes active listeners."""
        self._is_running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("TCP Transport Server stopped.")

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handles an incoming TCP client connection."""
        peer_addr = writer.get_extra_info("peername")
        try:
            # Read framed message
            msg = await read_framed_message(reader, timeout=10.0)
            if not msg:
                return

            # Invoke application message handler
            response = await self.message_handler(msg)

            # Reply with framed ACK
            if not response:
                response = {
                    "status": "ACK",
                    "message_id": msg.get("message_id"),
                    "timestamp": time.time()
                }

            ack_data = frame_message(response)
            writer.write(ack_data)
            await writer.drain()

        except Exception as e:
            logger.warning(f"Error handling connection from {peer_addr}: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

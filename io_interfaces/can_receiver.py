"""
can_receiver.py - Receptor de Hardware CAN Físico para a Telemetria
Formula ITA - Formula SAE Electric (2025-2026)
Compatível com CANable, Peak PCAN, Kvaser, SLCAN e SocketCAN via python-can.
"""

import threading
import time
from typing import Optional
import can
from core.can_decoder import CANDecoder
from core.telemetry_state import TelemetryState


class CANHardwareReceiver:
    def __init__(self, decoder: CANDecoder, state: TelemetryState):
        self.decoder = decoder
        self.state = state
        self.bus: Optional[can.BusABC] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def connect(self, interface: str = "slcan", channel: str = "COM3", bitrate: int = 500000) -> bool:
        """
        Conecta a uma interface CAN física.
        Exemplos de interface: 'slcan', 'pcan', 'kvaser', 'socketcan', 'virtual'
        """
        try:
            self.bus = can.Bus(interface=interface, channel=channel, bitrate=bitrate)
            self._running = True
            self.state.connection_status = f"CAN Conectada ({interface}:{channel} @ {bitrate//1000}k)"
            self._thread = threading.Thread(target=self._recv_loop, daemon=True)
            self._thread.start()
            return True
        except Exception as e:
            self.state.connection_status = f"Erro de Conexão: {str(e)}"
            return False

    def disconnect(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self.bus:
            try:
                self.bus.shutdown()
            except Exception:
                pass
            self.bus = None
        self.state.connection_status = "Desconectado"

    def is_connected(self) -> bool:
        return self._running and self.bus is not None

    def _recv_loop(self):
        while self._running and self.bus:
            try:
                msg = self.bus.recv(timeout=0.05)
                if msg is None:
                    continue

                msg_name = self.decoder.get_message_name(msg.arbitration_id) or f"RAW_0x{msg.arbitration_id:03X}"
                self.state.record_raw_frame(msg.arbitration_id, msg_name, bytes(msg.data))

                decoded = self.decoder.decode(msg.arbitration_id, msg.data)
                if decoded is not None:
                    self.state.update_from_decoded_frame(msg_name, decoded)
                    self.state.notify_listeners()
            except Exception:
                if not self._running:
                    break
                time.sleep(0.01)

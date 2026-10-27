"""
hm_trp_serial.py - Driver Serial RF (HM-TRP-915S), Protocolo Binário FITA-TELEM v1 e Injetor HIL
Formula ITA - Formula SAE Electric (2025-2026)

Implementa:
1. FitaTelemProtocol: Empacotamento determinístico de frames CAN em pacotes de 15 bytes com CRC-8
   para transmissão robusta sobre link FSK 915 MHz (HopeRF HM-TRP-915S).
2. StreamParser: Máquina de estados tolerante a ruído de RF e desalinhamento de bytes,
   com cálculo de Packet Loss (%) via contador sequencial SEQ e rejeição de erros CRC-8.
3. HMTRPSerialReceiver: Receptor assíncrono em thread dedicada para a estação de pista (Notebook).
4. HMTRPSerialTransmitter: Transmissor HIL para testes de bancada em loopback sem fio (Notebook TX -> RF -> Notebook RX).
5. HMTRPConfigTool: Gerador dos comandos de configuração nativa HopeRF (0xAA 0xFA ...) com pino CONFIG em GND.
"""

import struct
import threading
import time
from typing import List, Tuple, Optional, Dict, Any
import serial
import serial.tools.list_ports

from core.can_decoder import CANDecoder
from core.telemetry_state import TelemetryState


class FitaTelemProtocol:
    """
    Protocolo Binário FITA-TELEM v1 (15 bytes fixos por frame CAN):
    [0]    0xAA       (SOF_1)
    [1]    0x55       (SOF_2)
    [2]    SEQ        (uint8: 0..255)
    [3..4] CAN_ID     (uint16 Little-Endian)
    [5]    DLC        (uint8: 0..8)
    [6..13] DATA[8]   (8 bytes de payload CAN preenchidos com zero se DLC < 8)
    [14]   CRC8       (Polinômio 0x07 calculado sobre os bytes [2..13])
    """
    SOF_1 = 0xAA
    SOF_2 = 0x55
    PACKET_SIZE = 15
    CRC_POLY = 0x07

    @staticmethod
    def calculate_crc8(data: bytes) -> int:
        crc = 0x00
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = ((crc << 1) ^ 0x07) & 0xFF
                else:
                    crc = (crc << 1) & 0xFF
        return crc

    @classmethod
    def encode_can_frame(cls, seq: int, can_id: int, data: bytes) -> bytes:
        dlc = min(8, len(data))
        padded_data = (bytes(data) + b"\x00" * 8)[:8]
        body = struct.pack("<BHB8s", seq & 0xFF, can_id & 0xFFFF, dlc, padded_data)
        crc = cls.calculate_crc8(body)
        return bytes([cls.SOF_1, cls.SOF_2]) + body + bytes([crc])


class StreamParser:
    """
    Analisador de fluxo byte-a-byte resiliente a ruído eletromagnético no link 915 MHz.
    Extrai pacotes válidos, contabiliza erros de CRC-8 e mede perda de pacotes pelo SEQ.
    """
    def __init__(self):
        self._buffer = bytearray()
        self.packets_ok: int = 0
        self.crc_errors: int = 0
        self.packets_lost: int = 0
        self.last_seq: Optional[int] = None

    def reset(self):
        self._buffer.clear()
        self.packets_ok = 0
        self.crc_errors = 0
        self.packets_lost = 0
        self.last_seq = None

    def feed(self, chunk: bytes) -> List[Tuple[int, int, bytes]]:
        """
        Alimenta novos bytes recebidos da serial e retorna uma lista de tuplas:
        [(seq, can_id, payload_bytes), ...]
        """
        if not chunk:
            return []

        self._buffer.extend(chunk)
        valid_frames: List[Tuple[int, int, bytes]] = []
        n = len(self._buffer)
        idx = 0

        while idx <= n - FitaTelemProtocol.PACKET_SIZE:
            if self._buffer[idx] == FitaTelemProtocol.SOF_1 and self._buffer[idx + 1] == FitaTelemProtocol.SOF_2:
                body = bytes(self._buffer[idx + 2 : idx + 14])
                expected_crc = self._buffer[idx + 14]
                calc_crc = FitaTelemProtocol.calculate_crc8(body)

                if calc_crc == expected_crc:
                    seq, can_id, dlc, raw8 = struct.unpack("<BHB8s", body)
                    dlc = min(8, max(0, dlc))
                    payload = raw8[:dlc]

                    # Verificar continuidade do contador sequencial SEQ (0..255)
                    if self.last_seq is not None:
                        expected_seq = (self.last_seq + 1) & 0xFF
                        if seq != expected_seq:
                            missed = (seq - expected_seq) & 0xFF
                            # Se o salto for razoável (< 128), soma como pacotes perdidos no ar
                            if missed < 128:
                                self.packets_lost += missed
                    self.last_seq = seq
                    self.packets_ok += 1

                    valid_frames.append((seq, can_id, payload))
                    idx += FitaTelemProtocol.PACKET_SIZE
                else:
                    # Erro de CRC ou falso cabeçalho 0xAA 0x55 em meio a ruído: avança 2 bytes
                    self.crc_errors += 1
                    idx += 2
            else:
                idx += 1

        # Remover bytes já processados mantendo apenas o resíduo final (< 15 bytes)
        if idx > 0:
            del self._buffer[:idx]

        # Proteção contra crescimento indefinido se houver apenas lixo
        if len(self._buffer) > 4096:
            del self._buffer[:-FitaTelemProtocol.PACKET_SIZE]

        return valid_frames

    @property
    def packet_loss_pct(self) -> float:
        total = self.packets_ok + self.packets_lost
        if total <= 0:
            return 0.0
        return (self.packets_lost / total) * 100.0


class HMTRPConfigTool:
    """
    Utilitário de comandos de configuração do módulo HopeRF HM-TRP-915S.
    NOTA DE HARDWARE: Para que o módulo responda a estes comandos, o pino CONFIG
    do HM-TRP-915S deve estar conectado ao GND (LOW) e a UART em 9600 bps (padrão de modo config).
    """
    @staticmethod
    def cmd_reset_factory() -> bytes:
        """Restaura parâmetros de fábrica (0xAA 0xFA 0xF0)."""
        return b"\xAA\xFA\xF0"

    @staticmethod
    def cmd_read_parameters() -> bytes:
        """Lê a configuração atual gravada no HM-TRP-915S (0xAA 0xFA 0xE1)."""
        return b"\xAA\xFA\xE1"

    @staticmethod
    def cmd_set_frequency(freq_hz: int = 915_000_000) -> bytes:
        """Define a frequência portadora em Hz (Padrão: 915.000.000 Hz = 0x3689CA00)."""
        return b"\xAA\xFA\xD2" + struct.pack(">I", int(freq_hz))

    @staticmethod
    def cmd_set_air_datarate(rate_bps: int = 57600) -> bytes:
        """Define a velocidade de modulação FSK no ar (1200 a 115200 bps)."""
        return b"\xAA\xFA\xC3" + struct.pack(">I", int(rate_bps))

    @staticmethod
    def cmd_set_uart_baudrate(baud_bps: int = 57600) -> bytes:
        """Define o baudrate da porta serial UART do HM-TRP (1200 a 115200 bps)."""
        return b"\xAA\xFA\x1E" + struct.pack(">I", int(baud_bps))

    @staticmethod
    def cmd_set_tx_power(level: int = 7) -> bytes:
        """
        Define o nível de potência de transmissão (0 a 7):
        Nível 7 = +20 dBm (100 mW - Máximo alcance na pista)
        Nível 6 = +17 dBm
        Nível 5 = +14 dBm
        """
        lvl = max(0, min(7, int(level)))
        return b"\xAA\xFA\x96" + struct.pack(">B", lvl)

    @classmethod
    def build_recommended_pit_profile(cls, baud_bps: int = 57600) -> List[Tuple[str, bytes]]:
        """Retorna a sequência completa de comandos para configurar um módulo HM-TRP-915S para a equipe."""
        return [
            ("Frequência 915.0 MHz", cls.cmd_set_frequency(915_000_000)),
            (f"Taxa de Ar FSK {baud_bps} bps", cls.cmd_set_air_datarate(baud_bps)),
            (f"Baudrate UART {baud_bps} bps", cls.cmd_set_uart_baudrate(baud_bps)),
            ("Potência TX Máxima (+20 dBm / 100 mW)", cls.cmd_set_tx_power(7)),
        ]


class HMTRPSerialReceiver:
    """
    Receptor Serial para o módulo HM-TRP-915S conectado via USB-TTL ao Notebook da Pista.
    """
    def __init__(self, decoder: CANDecoder, state: TelemetryState):
        self.decoder = decoder
        self.state = state
        self.parser = StreamParser()
        self.serial_port: Optional[serial.Serial] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    @staticmethod
    def list_available_ports() -> List[Dict[str, str]]:
        """Lista todas as portas COM disponíveis no sistema com descrição do chip USB-TTL."""
        ports_info = []
        for p in serial.tools.list_ports.comports():
            ports_info.append({
                "device": p.device,
                "description": f"{p.device} — {p.description}"
            })
        return ports_info

    def connect(self, port: str = "COM3", baudrate: int = 57600) -> bool:
        self.disconnect()
        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.02,
                write_timeout=0.2
            )
            self.parser.reset()
            self.state.reset_rf_stats()
            self._running = True
            self.state.connection_status = f"RF HM-TRP-915S ({port} @ {baudrate} bps)"
            self._thread = threading.Thread(target=self._recv_loop, daemon=True)
            self._thread.start()
            return True
        except Exception as e:
            self.state.connection_status = f"Erro Serial ({port}): {e}"
            self.serial_port = None
            return False

    def disconnect(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        with self._lock:
            if self.serial_port and self.serial_port.is_open:
                try:
                    self.serial_port.close()
                except Exception:
                    pass
            self.serial_port = None
        self.state.connection_status = "Desconectado"

    def is_connected(self) -> bool:
        return self._running and self.serial_port is not None and self.serial_port.is_open

    def send_raw_bytes(self, data: bytes) -> bool:
        """Envia bytes pela porta serial (ex: comandos de injeção de falha ou config 0xAA 0xFA)."""
        with self._lock:
            if self.serial_port and self.serial_port.is_open:
                try:
                    self.serial_port.write(data)
                    self.serial_port.flush()
                    return True
                except Exception:
                    return False
        return False

    def _recv_loop(self):
        window_start = time.perf_counter()
        bytes_in_window = 0
        frames_in_window = 0

        while self._running and self.serial_port:
            try:
                chunk = self.serial_port.read(256)
                now = time.perf_counter()

                if chunk:
                    bytes_in_window += len(chunk)
                    frames = self.parser.feed(chunk)
                    frames_in_window += len(frames)

                    for seq, can_id, payload in frames:
                        msg_name = self.decoder.get_message_name(can_id) or f"RAW_0x{can_id:03X}"
                        self.state.record_raw_frame(can_id, msg_name, payload)
                        decoded = self.decoder.decode(can_id, payload)
                        if decoded is not None:
                            self.state.update_from_decoded_frame(msg_name, decoded)

                    # Atualizar estatísticas de qualidade do link RF no estado global
                    self.state.rf_packets_ok = self.parser.packets_ok
                    self.state.rf_crc_errors = self.parser.crc_errors
                    self.state.rf_packets_lost = self.parser.packets_lost
                    self.state.rf_packet_loss_pct = self.parser.packet_loss_pct
                    self.state.last_seq_id = self.parser.last_seq

                    if frames:
                        self.state.notify_listeners()

                # Atualizar cálculo de taxa de bits (kbps) e frames por segundo a cada 0.5s
                dt = now - window_start
                if dt >= 0.5:
                    self.state.rf_bitrate_kbps = (bytes_in_window * 10.0) / (dt * 1000.0)  # 10 bits/byte em 8N1
                    self.state.rf_fps = frames_in_window / dt
                    window_start = now
                    bytes_in_window = 0
                    frames_in_window = 0

            except Exception:
                if not self._running:
                    break
                time.sleep(0.01)


class HMTRPSerialTransmitter:
    """
    Transmissor Serial HIL de Bancada:
    Codifica frames CAN no protocolo FITA-TELEM v1 (15 bytes) e envia para uma porta COM
    onde está conectado o segundo módulo HM-TRP-915S (TX), permitindo testar os dois rádios
    diretamente pelo notebook antes mesmo de ligar as MCUs!
    """
    def __init__(self):
        self.serial_port: Optional[serial.Serial] = None
        self._seq: int = 0
        self._lock = threading.Lock()
        self.frames_sent: int = 0

    def connect(self, port: str, baudrate: int = 57600) -> bool:
        self.disconnect()
        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.05,
                write_timeout=0.1
            )
            self._seq = 0
            self.frames_sent = 0
            return True
        except Exception:
            self.serial_port = None
            return False

    def disconnect(self):
        with self._lock:
            if self.serial_port and self.serial_port.is_open:
                try:
                    self.serial_port.close()
                except Exception:
                    pass
            self.serial_port = None

    def is_connected(self) -> bool:
        return self.serial_port is not None and self.serial_port.is_open

    def send_can_frame(self, can_id: int, data: bytes) -> bool:
        """Empacota um frame CAN em 15 bytes FITA-TELEM v1 e transmite pela serial."""
        with self._lock:
            if not self.serial_port or not self.serial_port.is_open:
                return False
            try:
                pkt = FitaTelemProtocol.encode_can_frame(self._seq, can_id, data)
                self._seq = (self._seq + 1) & 0xFF
                self.serial_port.write(pkt)
                self.frames_sent += 1
                return True
            except Exception:
                return False

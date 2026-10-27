"""
telemetry_state.py - Estrutura de Dados e Estado Global Thread-Safe da Telemetria
Formula ITA - Formula SAE Electric (2025-2026)
"""

import threading
import time
from collections import deque
from typing import Dict, List, Any, Optional, Callable


class TelemetryState:
    def __init__(self, history_length: int = 300):
        self._lock = threading.Lock()
        self.history_length = history_length

        # 1. Status Geral e Segurança
        self.fsm_state: str = "BOOT"  # BOOT, STANDBY, PRECHARGE, DRIVE, CHARGING, FAULT
        self.sdc_armed: bool = False
        self.air_plus: bool = False
        self.air_minus: bool = False
        self.precharge_active: bool = False
        self.error_code: int = 0
        self.alive_counter: int = 0

        # Flags de Falha
        self.faults: Dict[str, bool] = {
            "undervoltage": False,
            "overvoltage": False,
            "overtemp": False,
            "undertemp": False,
            "overcurrent": False,
            "isospi_drop": False,
            "hardware_trip": False,
            "fuse_suspect": False,
        }

        # 2. Métricas Globais do Acumulador (20s18p)
        self.pack_voltage: float = 72.0      # Volts
        self.pack_current: float = 0.0       # Amperes
        self.pack_soc: float = 100.0         # 0.0 a 100.0 %
        self.pack_soh: float = 100.0         # %
        self.dclink_voltage: float = 0.0     # Volts
        self.dcl: float = 250.0              # Discharge Current Limit (A)
        self.ccl: float = 50.0               # Charge Current Limit (A)
        self.derating_active: bool = False

        # 3. Tensões Individuais das Células (20 blocos) em mV
        self.cell_voltages: List[int] = [3600] * 20
        self.cell_volt_min: int = 3600
        self.cell_volt_min_id: int = 1
        self.cell_volt_max: int = 3600
        self.cell_volt_max_id: int = 1
        self.cell_delta_mv: int = 0

        # 4. Temperaturas dos 4 Módulos Escravos (°C)
        self.module_temperatures: List[float] = [25.0] * 4
        self.temp_min: float = 25.0
        self.temp_max: float = 25.0

        # 5. Diagnóstico de Fusível RLS & Z-score
        self.fuse_blown: bool = False
        self.blown_block_index: int = 0
        self.estimated_r0_uohm: int = 833    # ~0.833 mOhm para 18p
        self.average_r_uohm: int = 833
        self.z_score: float = 0.0

        # 6. Históricos Temporais para Gráficos
        self.time_history = deque(maxlen=history_length)
        self.current_history = deque(maxlen=history_length)
        self.voltage_history = deque(maxlen=history_length)
        self.soc_history = deque(maxlen=history_length)
        self.r0_history = deque(maxlen=history_length)

        # Estatísticas de Conexão e Link RF (HM-TRP-915S)
        self.frames_received: int = 0
        self.last_update_timestamp: float = time.time()
        self.connection_status: str = "Desconectado"

        self.rf_packets_ok: int = 0
        self.rf_crc_errors: int = 0
        self.rf_packets_lost: int = 0
        self.rf_packet_loss_pct: float = 0.0
        self.rf_bitrate_kbps: float = 0.0
        self.rf_fps: float = 0.0
        self.last_seq_id: Optional[int] = None

        # 7. Inspetor de Barramento CAN Bruto (Sniffer DBC em tempo real)
        # Chave: can_id (int) -> {"name": str, "hex": str, "count": int, "period_ms": float, "last_ts": float}
        self.can_bus_inspector: Dict[int, Dict[str, Any]] = {}

        # 8. Sensores Veiculares de Expansão (VCU & Inversor)
        self.apps1_pct: float = 0.0
        self.apps2_pct: float = 0.0
        self.brake_pressure_bar: float = 0.0
        self.vehicle_speed_kmh: float = 0.0
        self.apps_plausible: bool = True
        self.steering_angle_deg: float = 0.0

        self.motor_rpm: int = 0
        self.torque_cmd_nm: float = 0.0
        self.motor_temp_c: float = 28.0
        self.inverter_temp_c: float = 26.0

        # Callbacks para interface gráfica
        self._listeners: List[Callable[['TelemetryState'], None]] = []

    def reset_rf_stats(self):
        with self._lock:
            self.rf_packets_ok = 0
            self.rf_crc_errors = 0
            self.rf_packets_lost = 0
            self.rf_packet_loss_pct = 0.0
            self.rf_bitrate_kbps = 0.0
            self.rf_fps = 0.0
            self.last_seq_id = None

    def record_raw_frame(self, can_id: int, msg_name: str, data: bytes):
        """Registra o frame CAN bruto no inspetor em tempo real."""
        now = time.perf_counter()
        hex_str = " ".join(f"{b:02X}" for b in data)
        with self._lock:
            entry = self.can_bus_inspector.get(can_id)
            if entry is None:
                self.can_bus_inspector[can_id] = {
                    "name": msg_name or f"UNKNOWN_0x{can_id:03X}",
                    "hex": hex_str,
                    "count": 1,
                    "period_ms": 0.0,
                    "last_ts": now,
                }
            else:
                dt_ms = (now - entry["last_ts"]) * 1000.0
                # Filtro exponencial suave para leitura estável do período em ms
                if entry["period_ms"] == 0.0:
                    entry["period_ms"] = dt_ms
                else:
                    entry["period_ms"] = 0.8 * entry["period_ms"] + 0.2 * dt_ms
                entry["hex"] = hex_str
                entry["count"] += 1
                entry["last_ts"] = now
                if msg_name:
                    entry["name"] = msg_name

    def register_listener(self, callback: Callable[['TelemetryState'], None]):
        self._listeners.append(callback)

    def notify_listeners(self):
        for listener in self._listeners:
            try:
                listener(self)
            except Exception:
                pass

    def update_from_decoded_frame(self, frame_name: str, signals: Dict[str, Any]):
        """Atualiza o estado global com base na mensagem CAN decodificada."""
        with self._lock:
            now = time.time()
            self.last_update_timestamp = now
            self.frames_received += 1

            if frame_name == "BMS_Heartbeat_Status":
                fsm_val = signals.get("BMS_FSM_State", 0)
                fsm_map = {0: "BOOT", 1: "STANDBY", 2: "PRECHARGE", 3: "DRIVE", 4: "CHARGING", 5: "FAULT"}
                self.fsm_state = fsm_map.get(fsm_val, "UNKNOWN")
                
                self.sdc_armed = bool(signals.get("BMS_SDC_Armed", 0))
                self.air_plus = bool(signals.get("BMS_AIR_Plus_Closed", 0))
                self.air_minus = bool(signals.get("BMS_AIR_Minus_Closed", 0))
                self.precharge_active = bool(signals.get("BMS_Precharge_Active", 0))
                
                self.faults["undervoltage"] = bool(signals.get("BMS_Fault_Undervoltage", 0))
                self.faults["overvoltage"] = bool(signals.get("BMS_Fault_Overvoltage", 0))
                self.faults["overtemp"] = bool(signals.get("BMS_Fault_Overtemp", 0))
                self.faults["undertemp"] = bool(signals.get("BMS_Fault_Undertemp", 0))
                self.faults["overcurrent"] = bool(signals.get("BMS_Fault_Overcurrent", 0))
                self.faults["isospi_drop"] = bool(signals.get("BMS_Fault_IsoSPI_Drop", 0))
                self.faults["hardware_trip"] = bool(signals.get("BMS_Fault_Hardware_Trip", 0))
                self.faults["fuse_suspect"] = bool(signals.get("BMS_Warning_Fuse_Suspect", 0))
                self.alive_counter = signals.get("BMS_Rolling_Counter", 0)
                self.error_code = signals.get("BMS_Error_Code", 0)

            elif frame_name == "BMS_Pack_Metrics":
                self.pack_voltage = float(signals.get("BMS_Pack_Voltage", self.pack_voltage))
                self.pack_current = float(signals.get("BMS_Pack_Current", self.pack_current))
                self.pack_soc = float(signals.get("BMS_Pack_SOC", self.pack_soc))
                self.pack_soh = float(signals.get("BMS_Pack_SOH", self.pack_soh))

                # Registrar ponto no histórico
                self.time_history.append(now)
                self.current_history.append(self.pack_current)
                self.voltage_history.append(self.pack_voltage)
                self.soc_history.append(self.pack_soc)

            elif frame_name == "BMS_Dynamic_Limits":
                self.dcl = float(signals.get("BMS_Discharge_Limit_DCL", self.dcl))
                self.ccl = float(signals.get("BMS_Charge_Limit_CCL", self.ccl))
                self.dclink_voltage = float(signals.get("BMS_DCLink_Voltage", self.dclink_voltage))
                self.derating_active = bool(signals.get("BMS_Derating_Active", 0))

            elif frame_name == "BMS_Extremes_MinMax":
                self.cell_volt_min = int(signals.get("BMS_Cell_Volt_Min", self.cell_volt_min))
                self.cell_volt_min_id = int(signals.get("BMS_Cell_Volt_Min_ID", self.cell_volt_min_id))
                self.cell_volt_max = int(signals.get("BMS_Cell_Volt_Max", self.cell_volt_max))
                self.cell_volt_max_id = int(signals.get("BMS_Cell_Volt_Max_ID", self.cell_volt_max_id))
                self.cell_delta_mv = max(0, self.cell_volt_max - self.cell_volt_min)
                self.temp_min = float(signals.get("BMS_Cell_Temp_Min", self.temp_min))
                self.temp_max = float(signals.get("BMS_Cell_Temp_Max", self.temp_max))

            elif frame_name == "BMS_CellVoltages_Group1":
                self.cell_voltages[0] = int(signals.get("BMS_Cell_Volt_01", self.cell_voltages[0]))
                self.cell_voltages[1] = int(signals.get("BMS_Cell_Volt_02", self.cell_voltages[1]))
                self.cell_voltages[2] = int(signals.get("BMS_Cell_Volt_03", self.cell_voltages[2]))
                self.cell_voltages[3] = int(signals.get("BMS_Cell_Volt_04", self.cell_voltages[3]))

            elif frame_name == "BMS_CellVoltages_Group2":
                self.cell_voltages[4] = int(signals.get("BMS_Cell_Volt_05", self.cell_voltages[4]))
                self.cell_voltages[5] = int(signals.get("BMS_Cell_Volt_06", self.cell_voltages[5]))
                self.cell_voltages[6] = int(signals.get("BMS_Cell_Volt_07", self.cell_voltages[6]))
                self.cell_voltages[7] = int(signals.get("BMS_Cell_Volt_08", self.cell_voltages[7]))

            elif frame_name == "BMS_CellVoltages_Group3":
                self.cell_voltages[8] = int(signals.get("BMS_Cell_Volt_09", self.cell_voltages[8]))
                self.cell_voltages[9] = int(signals.get("BMS_Cell_Volt_10", self.cell_voltages[9]))
                self.cell_voltages[10] = int(signals.get("BMS_Cell_Volt_11", self.cell_voltages[10]))
                self.cell_voltages[11] = int(signals.get("BMS_Cell_Volt_12", self.cell_voltages[11]))

            elif frame_name == "BMS_CellVoltages_Group4":
                self.cell_voltages[12] = int(signals.get("BMS_Cell_Volt_13", self.cell_voltages[12]))
                self.cell_voltages[13] = int(signals.get("BMS_Cell_Volt_14", self.cell_voltages[13]))
                self.cell_voltages[14] = int(signals.get("BMS_Cell_Volt_15", self.cell_voltages[14]))
                self.cell_voltages[15] = int(signals.get("BMS_Cell_Volt_16", self.cell_voltages[15]))

            elif frame_name == "BMS_CellVoltages_Group5":
                self.cell_voltages[16] = int(signals.get("BMS_Cell_Volt_17", self.cell_voltages[16]))
                self.cell_voltages[17] = int(signals.get("BMS_Cell_Volt_18", self.cell_voltages[17]))
                self.cell_voltages[18] = int(signals.get("BMS_Cell_Volt_19", self.cell_voltages[18]))
                self.cell_voltages[19] = int(signals.get("BMS_Cell_Volt_20", self.cell_voltages[19]))

            elif frame_name == "BMS_Temperatures":
                self.module_temperatures[0] = float(signals.get("BMS_Slave1_Temperature", self.module_temperatures[0]))
                self.module_temperatures[1] = float(signals.get("BMS_Slave2_Temperature", self.module_temperatures[1]))
                self.module_temperatures[2] = float(signals.get("BMS_Slave3_Temperature", self.module_temperatures[2]))
                self.module_temperatures[3] = float(signals.get("BMS_Slave4_Temperature", self.module_temperatures[3]))

            elif frame_name == "BMS_Diagnostics_Fuse":
                self.fuse_blown = bool(signals.get("BMS_Fuse_Blown_Detected", 0))
                self.blown_block_index = int(signals.get("BMS_Blown_Block_Index", 0))
                self.estimated_r0_uohm = int(signals.get("BMS_Estimated_R0_uOhm", self.estimated_r0_uohm))
                self.average_r_uohm = int(signals.get("BMS_Average_R_uOhm", self.average_r_uohm))
                self.z_score = float(signals.get("BMS_Z_Score", self.z_score))
                self.r0_history.append(self.estimated_r0_uohm)

            elif frame_name == "VCU_Driver_Sensors":
                self.apps1_pct = float(signals.get("VCU_APPS1_Pct", self.apps1_pct))
                self.apps2_pct = float(signals.get("VCU_APPS2_Pct", self.apps2_pct))
                self.brake_pressure_bar = float(signals.get("VCU_Brake_Pressure_Bar", self.brake_pressure_bar))
                self.vehicle_speed_kmh = float(signals.get("VCU_Vehicle_Speed_Kmh", self.vehicle_speed_kmh))
                self.apps_plausible = bool(signals.get("VCU_APPS_BSE_Plausible", 1))
                self.steering_angle_deg = float(signals.get("VCU_Steering_Angle_Deg", self.steering_angle_deg))

            elif frame_name == "INV_Motor_Telemetry":
                self.motor_rpm = int(signals.get("INV_Motor_RPM", self.motor_rpm))
                self.torque_cmd_nm = float(signals.get("INV_Torque_Command_Nm", self.torque_cmd_nm))
                self.motor_temp_c = float(signals.get("INV_Motor_Temp_C", self.motor_temp_c))
                self.inverter_temp_c = float(signals.get("INV_IGBT_Temp_C", self.inverter_temp_c))

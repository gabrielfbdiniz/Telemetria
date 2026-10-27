"""
virtual_battery.py - Emulador de Alta Fidelidade do BMS Master e Acumulador 20s18p
Formula ITA - Formula SAE Electric (2025-2026)
"""

import math
import random
import threading
import time
from typing import Optional, Callable
from core.can_decoder import CANDecoder
from core.telemetry_state import TelemetryState


class VehicleSimulator:
    def __init__(self, decoder: CANDecoder, state: TelemetryState):
        self.decoder = decoder
        self.state = state
        self._running = False
        self._thread: Optional[threading.Thread] = None
        # Callback opcional (can_id: int, data: bytes) -> None para espelhar frames em porta Serial/HIL
        self.frame_sink: Optional[Callable[[int, bytes], None]] = None

        # Parâmetros Eletroquímicos Nominais (Samsung 21700 - 20s18p)
        self.capacity_ah = 54.0   # 18 * 3.0 Ah
        self.soc = 92.5           # % inicial
        self.fsm_state_code = 3   # 3 = DRIVE
        self.sdc_armed = 1
        self.air_plus = 1
        self.air_minus = 1
        self.precharge_active = 0
        self.rolling_counter = 0

        # Dispersão inicial de R0 dos 20 blocos (~833 uOhm com variância de fabricação)
        self.r0_blocks = [833 + int(random.gauss(0, 8)) for _ in range(20)]
        self.capacitances = [self.capacity_ah * (1.0 + random.gauss(0, 0.005)) for _ in range(20)]

        # Temperaturas dos 4 módulos
        self.temperatures = [28.0, 28.5, 29.0, 28.2]

        # Flags de Injeção de Falhas Programadas
        self.fault_fuse_blown = False
        self.fault_blown_index = 6
        self.fault_undervoltage = False
        self.fault_uv_index = 2
        self.fault_overtemperature = False
        self.fault_overcurrent = False

        # Variáveis dinâmicas de ciclo de condução
        self.sim_time = 0.0
        self.current_a = 0.0

    def start(self):
        if not self._running:
            self._running = True
            self.state.connection_status = "Emulador Virtual Ativo (100 Hz)"
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self.state.connection_status = "Desconectado"

    def is_running(self) -> bool:
        return self._running

    # Injetores de Falhas Interativas para Demonstração
    def trigger_fuse_blow(self, block_index: int = 6):
        self.fault_fuse_blown = True
        self.fault_blown_index = block_index
        # Eleva a resistência ôhmica do bloco (de ~833 uOhm para ~882 uOhm)
        self.r0_blocks[block_index] = 882

    def trigger_undervoltage(self, block_index: int = 2):
        self.fault_undervoltage = True
        self.fault_uv_index = block_index

    def trigger_overtemp(self):
        self.fault_overtemperature = True

    def reset_all_faults(self):
        self.fault_fuse_blown = False
        self.fault_undervoltage = False
        self.fault_overtemperature = False
        self.fault_overcurrent = False
        self.fsm_state_code = 3  # DRIVE
        self.sdc_armed = 1
        self.air_plus = 1
        self.air_minus = 1
        self.r0_blocks = [833 + int(random.gauss(0, 8)) for _ in range(20)]
        self.temperatures = [28.0, 28.5, 29.0, 28.2]

    def _calculate_ocv(self, soc_pct: float) -> float:
        """Curva OCV empírica típica de NMC 21700."""
        soc_norm = max(0.0, min(1.0, soc_pct / 100.0))
        # Polinômio ajustado: 3.0V (0%) a 4.2V (100%)
        return 3.00 + 0.85 * soc_norm + 0.35 * (soc_norm ** 2)

    def _drive_cycle_current(self, t: float) -> float:
        """Gera perfil de corrida FSAE dinâmico (acelerações, curvas, frenagens)."""
        phase = t % 15.0  # Ciclo periódico de 15 segundos de volta
        if phase < 3.0:
            # Reta principal: aceleração forte (80 A a 160 A)
            return 80.0 + 80.0 * math.sin((phase / 3.0) * (math.pi / 2.0))
        elif phase < 5.0:
            # Frenagem forte antes da curva (-35 A regeneração)
            return -35.0
        elif phase < 8.0:
            # Contorno de curva rápida (30 A)
            return 30.0 + 10.0 * math.sin(phase * 4.0)
        elif phase < 11.0:
            # Curva lenta / aceleração intermediária (60 A)
            return 60.0 + 15.0 * math.sin(phase * 2.0)
        else:
            # Retomada curta antes da reta (110 A)
            return 110.0

    def _run_loop(self):
        dt = 0.02  # 50 Hz base (20 ms por iteração)
        tick_count = 0

        while self._running:
            t_start = time.perf_counter()
            self.sim_time += dt
            tick_count += 1
            self.rolling_counter = (self.rolling_counter + 1) % 16

            # 1. Atualizar Corrente e Dinâmica de Corrida
            if self.fsm_state_code == 3:  # DRIVE
                raw_current = self._drive_cycle_current(self.sim_time)
                # Adiciona ruído de medição
                self.current_a = raw_current + random.gauss(0, 0.8)
                # Integrar Coulomb Counting (Descarga reduz SOC)
                self.soc -= (self.current_a * dt) / (self.capacity_ah * 3600.0) * 100.0
                self.soc = max(5.0, min(100.0, self.soc))
            else:
                self.current_a = 0.0

            # 2. Calcular Tensões dos 20 Blocos (mV)
            ocv_nominal = self._calculate_ocv(self.soc)
            cell_mv_list = []
            for i in range(20):
                # Efeito queda de tensão deltaV = I * R0
                r_ohm = self.r0_blocks[i] * 1e-6
                v_drop = self.current_a * r_ohm
                v_cell = ocv_nominal - v_drop + random.gauss(0, 0.0008)

                if self.fault_undervoltage and i == self.fault_uv_index:
                    v_cell = 2.68  # Força subtensão crítica (< 2.80V)

                cell_mv_list.append(int(max(2000, min(4300, v_cell * 1000.0))))

            pack_voltage = sum(cell_mv_list) / 1000.0

            # 3. Atualizar Aquecimento Joule dos Módulos (°C)
            joule_heat = (self.current_a ** 2) * (0.833e-3) * 5.0  # calor por módulo de 5 blocos
            for m in range(4):
                cooling = (self.temperatures[m] - 25.0) * 0.015
                self.temperatures[m] += (joule_heat * 0.001 - cooling) * dt
                if self.fault_overtemperature and m == 2:
                    self.temperatures[m] += 0.8 * dt  # Elevação rápida até ultrapassar 60°C

            # 4. Avaliar Regras de Falhas e FSM
            v_min = min(cell_mv_list)
            v_max = max(cell_mv_list)
            t_max = max(self.temperatures)

            fault_uv = v_min < 2800
            fault_ov = v_max > 4250
            fault_ot = t_max > 60.0

            if fault_uv or fault_ov or fault_ot:
                self.fsm_state_code = 5  # FAULT
                self.sdc_armed = 0       # SDC disparado!
                self.air_plus = 0
                self.air_minus = 0

            # 5. Emitir Mensagens CAN conforme Períodos do DBC
            # (a) BMS_Pack_Metrics (cada 20 ms = a cada iteração)
            self._emit_frame("BMS_Pack_Metrics", {
                "BMS_Pack_Voltage": round(pack_voltage, 2),
                "BMS_Pack_Current": round(self.current_a, 1),
                "BMS_Pack_SOC": round(self.soc, 1),
                "BMS_Pack_SOH": 99.2
            })

            # (b) BMS_Heartbeat_Status, BMS_Dynamic_Limits, BMS_Extremes_MinMax, VCU e INV (cada 50 ms)
            if tick_count % 2 == 0:
                self._emit_frame("BMS_Heartbeat_Status", {
                    "BMS_FSM_State": self.fsm_state_code,
                    "BMS_SDC_Armed": self.sdc_armed,
                    "BMS_AIR_Plus_Closed": self.air_plus,
                    "BMS_AIR_Minus_Closed": self.air_minus,
                    "BMS_Precharge_Active": self.precharge_active,
                    "BMS_Fault_Undervoltage": 1 if fault_uv else 0,
                    "BMS_Fault_Overvoltage": 1 if fault_ov else 0,
                    "BMS_Fault_Overtemp": 1 if fault_ot else 0,
                    "BMS_Fault_Undertemp": 0,
                    "BMS_Fault_Overcurrent": 0,
                    "BMS_Fault_IsoSPI_Drop": 0,
                    "BMS_Fault_Hardware_Trip": 1 if self.sdc_armed == 0 else 0,
                    "BMS_Warning_Fuse_Suspect": 1 if self.fault_fuse_blown else 0,
                    "BMS_Rolling_Counter": self.rolling_counter,
                    "BMS_Checksum": 0,
                    "BMS_Error_Code": 0x42 if fault_uv else (0x81 if fault_ot else 0),
                    "BMS_Reserved_HBeat": 0
                })

                dcl_val = 250.0 if not self.fault_fuse_blown else 235.0  # Derating aplicado se fusível rompido!
                self._emit_frame("BMS_Dynamic_Limits", {
                    "BMS_Discharge_Limit_DCL": dcl_val,
                    "BMS_Charge_Limit_CCL": 45.0,
                    "BMS_DCLink_Voltage": round(pack_voltage if self.air_plus else 0.0, 2),
                    "BMS_Max_Allowable_Temp": 60,
                    "BMS_Derating_Active": 1 if self.fault_fuse_blown else 0
                })

                min_id = cell_mv_list.index(v_min) + 1
                max_id = cell_mv_list.index(v_max) + 1
                self._emit_frame("BMS_Extremes_MinMax", {
                    "BMS_Cell_Volt_Min": v_min,
                    "BMS_Cell_Volt_Min_ID": min_id,
                    "BMS_Cell_Volt_Max": v_max,
                    "BMS_Cell_Volt_Max_ID": max_id,
                    "BMS_Cell_Temp_Min": int(round(min(self.temperatures))),
                    "BMS_Cell_Temp_Max": int(round(max(self.temperatures)))
                })

                # Sensores Veiculares coerentes com o perfil de corrente FSAE
                apps_pct = max(0.0, min(100.0, (self.current_a / 160.0) * 100.0)) if self.current_a > 0 else 0.0
                brake_bar = max(0.0, min(65.0, (-self.current_a / 35.0) * 42.0)) if self.current_a < 0 else 0.0
                speed_kmh = int(max(0.0, min(118.0, 35.0 + 45.0 * math.sin(self.sim_time * 0.4) + apps_pct * 0.35))) if self.fsm_state_code == 3 else 0
                steer_deg = int(round(28.0 * math.sin(self.sim_time * 0.8) / 2.0) * 2)

                self._emit_frame("VCU_Driver_Sensors", {
                    "VCU_APPS1_Pct": round(apps_pct, 1),
                    "VCU_APPS2_Pct": round(max(0.0, apps_pct - 0.3), 1),
                    "VCU_Brake_Pressure_Bar": round(brake_bar, 1),
                    "VCU_Vehicle_Speed_Kmh": speed_kmh,
                    "VCU_APPS_BSE_Plausible": 1,
                    "VCU_Steering_Angle_Deg": steer_deg,
                })

                rpm_val = int(speed_kmh * 48.5)
                torque_nm = round((self.current_a / 160.0) * 210.0, 1)
                self._emit_frame("INV_Motor_Telemetry", {
                    "INV_Motor_RPM": max(0, min(20000, rpm_val)),
                    "INV_Torque_Command_Nm": max(-100.0, min(250.0, torque_nm)),
                    "INV_Motor_Temp_C": round(42.0 + 4.0 * math.sin(self.sim_time * 0.1), 1),
                    "INV_IGBT_Temp_C": round(38.5 + 5.5 * (abs(self.current_a) / 160.0), 1),
                })

            # (c) BMS_CellVoltages (Grupos 1 a 5) & Temperaturas (cada 100 ms = a cada 5 iterações)
            if tick_count % 5 == 0:
                self._emit_frame("BMS_CellVoltages_Group1", {
                    f"BMS_Cell_Volt_0{k}": cell_mv_list[k - 1] for k in range(1, 5)
                })
                self._emit_frame("BMS_CellVoltages_Group2", {
                    f"BMS_Cell_Volt_0{k}" if k < 10 else f"BMS_Cell_Volt_{k}": cell_mv_list[k - 1] for k in range(5, 9)
                })
                self._emit_frame("BMS_CellVoltages_Group3", {
                    f"BMS_Cell_Volt_0{k}" if k < 10 else f"BMS_Cell_Volt_{k}": cell_mv_list[k - 1] for k in range(9, 13)
                })
                self._emit_frame("BMS_CellVoltages_Group4", {
                    f"BMS_Cell_Volt_{k}": cell_mv_list[k - 1] for k in range(13, 17)
                })
                self._emit_frame("BMS_CellVoltages_Group5", {
                    f"BMS_Cell_Volt_{k}": cell_mv_list[k - 1] for k in range(17, 21)
                })

                # BMS_Temperatures
                self._emit_frame("BMS_Temperatures", {
                    f"BMS_Slave{k}_Temperature": round(self.temperatures[k - 1], 1) for k in range(1, 5)
                })

            # (d) BMS_Diagnostics_Fuse (cada 200 ms = a cada 10 iterações)
            if tick_count % 10 == 0:
                mean_r = sum(self.r0_blocks) / 20.0
                variance = sum((r - mean_r) ** 2 for r in self.r0_blocks) / 20.0
                std_r = max(1.0, math.sqrt(variance))
                target_r = self.r0_blocks[self.fault_blown_index]
                z_score = max(0.0, (target_r - mean_r) / std_r)

                self._emit_frame("BMS_Diagnostics_Fuse", {
                    "BMS_Fuse_Blown_Detected": 1 if self.fault_fuse_blown else 0,
                    "BMS_Blown_Block_Index": self.fault_blown_index,
                    "BMS_Estimated_R0_uOhm": int(target_r),
                    "BMS_Average_R_uOhm": int(mean_r),
                    "BMS_Z_Score": round(z_score, 2),
                    "BMS_Fuse_Diag_Reserved": 0
                })

            # Notificar listeners da UI
            self.state.notify_listeners()

            # Compensar tempo de espera para manter exatos 50 Hz
            elapsed = time.perf_counter() - t_start
            sleep_time = max(0.001, dt - elapsed)
            time.sleep(sleep_time)

    def _emit_frame(self, msg_name: str, signals: dict):
        can_id, payload = self.decoder.encode(msg_name, signals)
        self.state.record_raw_frame(can_id, msg_name, payload)
        decoded = self.decoder.decode(can_id, payload)
        if decoded is not None:
            self.state.update_from_decoded_frame(msg_name, decoded)
        if self.frame_sink is not None:
            try:
                self.frame_sink(can_id, payload)
            except Exception:
                pass


# Alias de compatibilidade retroativa
VirtualBatteryEmulator = VehicleSimulator


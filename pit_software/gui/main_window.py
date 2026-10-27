"""
main_window.py - Janela Principal do Dashboard de Telemetria Veicular
Formula ITA - Formula SAE Electric (2025-2026)
Opção 2: Stealth Glass & Cyber-Chassis (Preto, Laranja, Vermelho e Verde Funcional)
"""

import csv
import os
import time
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QMessageBox, QTabWidget, QInputDialog
)

from core.can_decoder import CANDecoder
from core.telemetry_state import TelemetryState
from simulator import VehicleSimulator
from io_interfaces.can_receiver import CANHardwareReceiver
from io_interfaces.hm_trp_serial import HMTRPSerialReceiver, HMTRPSerialTransmitter

from .widgets.car_top_down_view import CarTopDownHUDPanel
from .widgets.battery_pack_thermal_view import BatteryPackThermalPanel
from .widgets.rf_and_sensors_panel import RFAndSensorsPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Formula ITA — Telemetria Veicular FSAE (Stealth HUD & BMS 20s18p)")
        self.resize(1420, 910)
        self.setMinimumSize(1160, 750)

        # Tema Global Stealth Glass & Cyber-Chassis (Preto, Laranja #FF6B00, Vermelho #FF1744)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0A0B0E;
                color: #E2E8F0;
            }
            QWidget {
                color: #E2E8F0;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QPushButton {
                background-color: #141720;
                color: #FFFFFF;
                border: 1px solid #232936;
                border-radius: 5px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1E2330;
                border-color: #FF6B00;
                color: #FF8800;
            }
            QPushButton:pressed {
                background-color: #0D0F14;
            }
            QComboBox {
                background-color: #141720;
                color: #FFFFFF;
                border: 1px solid #232936;
                border-radius: 5px;
                padding: 4px 10px;
                font-size: 11px;
            }
            QComboBox:focus {
                border-color: #FF6B00;
            }
            QTabWidget::pane {
                border: 1px solid #1F2430;
                border-radius: 6px;
                background-color: #0A0B0E;
            }
            QTabBar::tab {
                background-color: #10131A;
                color: #8C9BAE;
                border: 1px solid #1F2430;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 8px 22px;
                margin-right: 4px;
                font-size: 11px;
                font-weight: 900;
                letter-spacing: 0.5px;
            }
            QTabBar::tab:selected {
                background-color: #161A22;
                color: #FF8800;
                border-color: #FF6B00;
                border-bottom: 2px solid #FF6B00;
            }
            QTabBar::tab:hover:!selected {
                color: #E2E8F0;
                background-color: #141720;
            }
        """)

        # 1. Componentes de Negócio e Conectividade
        self.decoder = CANDecoder()
        self.state = TelemetryState()
        self.emulator = VehicleSimulator(self.decoder, self.state)
        self.can_receiver = CANHardwareReceiver(self.decoder, self.state)
        self.rf_receiver = HMTRPSerialReceiver(self.decoder, self.state)
        self.rf_transmitter = HMTRPSerialTransmitter()

        # Gravação de Log CSV
        self.logging_active = False
        self.log_file = None
        self.log_writer = None
        self.logged_rows = 0

        # 2. Layout da Interface
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(8)

        # Barra Superior de Operação & Conexões
        main_layout.addLayout(self._create_top_toolbar())

        # Abas de Alta Performance Visual
        self.tabs = QTabWidget()

        # TELA 1: Chassi Top-Down Vetorial & HUD de Pista
        self.car_panel = CarTopDownHUDPanel(self.state)
        self.tabs.addTab(self.car_panel, "🏎️ Chassi & Sensores HUD (Vista Superior)")

        # TELA 2: Pack Térmico 20s18p & Módulos Expansíveis
        self.pack_thermal_panel = BatteryPackThermalPanel(self.state)
        self.tabs.addTab(self.pack_thermal_panel, "🔋 Pack Térmico & Módulos Expansíveis (20s18p)")

        # TELA 3: Link RF 915 MHz (HM-TRP-915S) & Inspetor CAN Bruto
        self.rf_sensors_panel = RFAndSensorsPanel(
            self.state,
            send_serial_cb=self.rf_receiver.send_raw_bytes
        )
        self.tabs.addTab(self.rf_sensors_panel, "📡 Link RF (HM-TRP-915S) & Inspetor CAN")

        main_layout.addWidget(self.tabs, 1)

        # Barra Inferior Compacta de Injeção de Falhas e Status
        main_layout.addLayout(self._create_fault_injector_bar())

        # 3. Timer de Renderização a 30 FPS
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_render_tick)
        self.timer.start(33)

        self._refresh_serial_ports()
        self._toggle_simulation()

    def _create_top_toolbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(8)

        title = QLabel("FORMULA ITA")
        title.setStyleSheet("font-size: 15px; font-weight: 900; color: #FF6B00; letter-spacing: 2px;")
        bar.addWidget(title)

        subtitle = QLabel("PIT TELEMETRY")
        subtitle.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748B; margin-right: 10px;")
        bar.addWidget(subtitle)

        self.btn_sim = QPushButton("▶ Simulação Virtual")
        self.btn_sim.clicked.connect(self._toggle_simulation)
        bar.addWidget(self.btn_sim)

        div = QLabel("|")
        div.setStyleSheet("color: #2D3748;")
        bar.addWidget(div)

        lbl_iface = QLabel("Entrada:")
        lbl_iface.setStyleSheet("font-size: 11px; color: #8C9BAE;")
        bar.addWidget(lbl_iface)

        self.combo_interface = QComboBox()
        self.combo_interface.addItems([
            "Rádio 915MHz (HM-TRP Serial)",
            "slcan (USB-CAN / CANable)",
            "pcan (PEAK)",
            "kvaser",
            "socketcan"
        ])
        bar.addWidget(self.combo_interface)

        lbl_com = QLabel("Porta:")
        lbl_com.setStyleSheet("font-size: 11px; color: #8C9BAE;")
        bar.addWidget(lbl_com)

        self.combo_port = QComboBox()
        self.combo_port.setEditable(True)
        self.combo_port.setMinimumWidth(110)
        bar.addWidget(self.combo_port)

        btn_refresh = QPushButton("↻")
        btn_refresh.setToolTip("Atualizar portas COM detectadas")
        btn_refresh.setFixedWidth(30)
        btn_refresh.clicked.connect(self._refresh_serial_ports)
        bar.addWidget(btn_refresh)

        lbl_baud = QLabel("Baud:")
        lbl_baud.setStyleSheet("font-size: 11px; color: #8C9BAE;")
        bar.addWidget(lbl_baud)

        self.combo_baud = QComboBox()
        self.combo_baud.addItems(["57600", "115200", "38400", "19200", "9600"])
        bar.addWidget(self.combo_baud)

        self.btn_connect_hw = QPushButton("📡 Conectar Hardware")
        self.btn_connect_hw.clicked.connect(self._toggle_hardware_connection)
        bar.addWidget(self.btn_connect_hw)

        self.btn_hil_tx = QPushButton("📤 HIL TX Serial")
        self.btn_hil_tx.setToolTip("Transmite a simulação em um HM-TRP TX para testar o rádio RX no box")
        self.btn_hil_tx.clicked.connect(self._toggle_hil_transmitter)
        bar.addWidget(self.btn_hil_tx)

        bar.addStretch()

        self.btn_log = QPushButton("⏺ Gravar CSV")
        self.btn_log.clicked.connect(self._toggle_logging)
        bar.addWidget(self.btn_log)

        self.lbl_conn_status = QLabel("● Inicializando...")
        self.lbl_conn_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #00E676;")
        bar.addWidget(self.lbl_conn_status)

        return bar

    def _create_fault_injector_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(6)

        lbl_demo = QLabel("TESTE DE BANCADA / INJEÇÃO DE FALHAS:")
        lbl_demo.setStyleSheet("font-size: 10px; font-weight: 900; color: #FF8800;")
        bar.addWidget(lbl_demo)

        btn_fuse = QPushButton("⚡ Romper Fusível Bloco 7 (RLS)")
        btn_fuse.clicked.connect(self._inject_fuse_blow)
        bar.addWidget(btn_fuse)

        btn_uv = QPushButton("🔻 Subtensão (<2.80V)")
        btn_uv.clicked.connect(self._inject_undervoltage)
        bar.addWidget(btn_uv)

        btn_ot = QPushButton("🔥 Sobretemperatura (>60°C)")
        btn_ot.clicked.connect(self._inject_overtemp)
        bar.addWidget(btn_ot)

        btn_reset = QPushButton("↺ Restaurar Normal (DRIVE)")
        btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #064E3B;
                border: 1px solid #00E676;
                color: #FFFFFF;
            }
            QPushButton:hover {
                background-color: #047857;
            }
        """)
        btn_reset.clicked.connect(self._reset_faults)
        bar.addWidget(btn_reset)

        bar.addStretch()

        self.lbl_footer_info = QLabel("Formula ITA — Formula SAE Electric (2025-2026)")
        self.lbl_footer_info.setStyleSheet("font-size: 10px; color: #64748B;")
        bar.addWidget(self.lbl_footer_info)

        return bar

    def _inject_fuse_blow(self):
        self.emulator.trigger_fuse_blow(6)
        self.rf_receiver.send_raw_bytes(b"f")

    def _inject_undervoltage(self):
        self.emulator.trigger_undervoltage(2)
        self.rf_receiver.send_raw_bytes(b"u")

    def _inject_overtemp(self):
        self.emulator.trigger_overtemp()
        self.rf_receiver.send_raw_bytes(b"t")

    def _reset_faults(self):
        self.emulator.reset_all_faults()
        self.rf_receiver.send_raw_bytes(b"r")

    def _refresh_serial_ports(self):
        current = self.combo_port.currentText().strip()
        self.combo_port.clear()
        detected = HMTRPSerialReceiver.list_available_ports()
        if detected:
            for item in detected:
                self.combo_port.addItem(item["device"])
                idx = self.combo_port.count() - 1
                self.combo_port.setItemData(idx, item["description"], Qt.ToolTipRole)
        else:
            self.combo_port.addItems(["COM3", "COM4", "COM5", "COM6", "COM7", "can0"])
        if current:
            self.combo_port.setCurrentText(current)

    def _toggle_simulation(self):
        if self.emulator.is_running():
            self.emulator.stop()
            self.btn_sim.setText("▶ Simulação Virtual")
            self.btn_sim.setStyleSheet("")
            if not self.rf_receiver.is_connected() and not self.can_receiver.is_connected():
                self.lbl_conn_status.setText("● Parado")
                self.lbl_conn_status.setStyleSheet("color: #64748B;")
        else:
            if not self.rf_transmitter.is_connected():
                if self.can_receiver.is_connected():
                    self.can_receiver.disconnect()
                if self.rf_receiver.is_connected():
                    self.rf_receiver.disconnect()
                self.btn_connect_hw.setText("📡 Conectar Hardware")
                self.btn_connect_hw.setStyleSheet("")

            self.emulator.start()
            self.btn_sim.setText("■ Parar Simulação")
            self.btn_sim.setStyleSheet("background-color: #C2410C; border-color: #FF6B00; color: #FFFFFF;")
            self.lbl_conn_status.setText("● Modo Simulação (50 Hz)")
            self.lbl_conn_status.setStyleSheet("color: #FF8800; font-weight: bold;")

    def _toggle_hardware_connection(self):
        if self.rf_receiver.is_connected() or self.can_receiver.is_connected():
            self.rf_receiver.disconnect()
            self.can_receiver.disconnect()
            self.btn_connect_hw.setText("📡 Conectar Hardware")
            self.btn_connect_hw.setStyleSheet("")
            self.lbl_conn_status.setText("● Desconectado")
            self.lbl_conn_status.setStyleSheet("color: #64748B;")
            return

        if self.emulator.is_running() and not self.rf_transmitter.is_connected():
            self.emulator.stop()
            self.btn_sim.setText("▶ Simulação Virtual")
            self.btn_sim.setStyleSheet("")

        mode_txt = self.combo_interface.currentText()
        port = self.combo_port.currentText().strip()
        baud = int(self.combo_baud.currentText())

        if "HM-TRP" in mode_txt:
            success = self.rf_receiver.connect(port=port, baudrate=baud)
            if success:
                self.btn_connect_hw.setText("⏹ Desconectar RF")
                self.btn_connect_hw.setStyleSheet("background-color: #991B1B; border-color: #FF1744; color: #FFF;")
                self.lbl_conn_status.setText(f"● RF 915MHz ({port} @ {baud})")
                self.lbl_conn_status.setStyleSheet("color: #00E676; font-weight: bold;")
            else:
                QMessageBox.critical(self, "Falha Serial", f"Não foi possível abrir {port} a {baud} bps.")
        else:
            interface_map = {
                "slcan (USB-CAN / CANable)": "slcan",
                "pcan (PEAK)": "pcan",
                "kvaser": "kvaser",
                "socketcan": "socketcan"
            }
            iface = interface_map.get(mode_txt, "slcan")
            success = self.can_receiver.connect(interface=iface, channel=port, bitrate=500000)
            if success:
                self.btn_connect_hw.setText("⏹ Desconectar CAN")
                self.btn_connect_hw.setStyleSheet("background-color: #991B1B; border-color: #FF1744; color: #FFF;")
                self.lbl_conn_status.setText(f"● CAN ({iface}:{port})")
                self.lbl_conn_status.setStyleSheet("color: #00E676; font-weight: bold;")
            else:
                QMessageBox.critical(self, "Falha CAN", f"Não foi possível abrir {iface}:{port}.")

    def _toggle_hil_transmitter(self):
        if self.rf_transmitter.is_connected():
            self.emulator.frame_sink = None
            self.rf_transmitter.disconnect()
            self.btn_hil_tx.setText("📤 HIL TX Serial")
            self.btn_hil_tx.setStyleSheet("")
            return

        ports = [p["device"] for p in HMTRPSerialReceiver.list_available_ports()]
        if not ports:
            ports = ["COM4", "COM5", "COM6", "COM3"]

        port, ok = QInputDialog.getItem(
            self,
            "Loopback HIL Serial (HM-TRP-915S TX)",
            "Selecione a porta COM do módulo HM-TRP-915S Transmissor (TX):",
            ports, 0, True
        )
        if not ok or not port.strip():
            return

        baud = int(self.combo_baud.currentText())
        if self.rf_transmitter.connect(port.strip(), baudrate=baud):
            self.emulator.frame_sink = self.rf_transmitter.send_can_frame
            if not self.emulator.is_running():
                self.emulator.start()
                self.btn_sim.setText("■ Parar Simulação")
                self.btn_sim.setStyleSheet("background-color: #C2410C; border-color: #FF6B00; color: #FFFFFF;")
            self.btn_hil_tx.setText(f"📤 TX ({port.strip()})")
            self.btn_hil_tx.setStyleSheet("background-color: #7E22CE; border-color: #C084FC; color: #FFFFFF;")
        else:
            QMessageBox.warning(self, "Erro TX", f"Não foi possível abrir {port.strip()} para TX.")

    def _toggle_logging(self):
        if self.logging_active:
            self.logging_active = False
            if self.log_file:
                self.log_file.close()
                self.log_file = None
            self.btn_log.setText("⏺ Gravar CSV")
            self.btn_log.setStyleSheet("")
            QMessageBox.information(self, "Log Salvo", f"Gravação concluída!\nTotal de amostras: {self.logged_rows}")
        else:
            logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
            os.makedirs(logs_dir, exist_ok=True)
            filename = os.path.join(logs_dir, f"telemetria_{time.strftime('%Y%m%d_%H%M%S')}.csv")
            try:
                self.log_file = open(filename, "w", newline="", encoding="utf-8")
                self.log_writer = csv.writer(self.log_file)
                header = [
                    "Timestamp", "FSM_State", "Pack_Voltage_V", "Pack_Current_A", "SOC_pct", "DCL_A", "CCL_A",
                    "Cell_Min_mV", "Cell_Max_mV", "Delta_mV", "Fuse_Blown", "Z_Score",
                    "APPS1_pct", "Brake_bar", "Speed_kmh", "Motor_RPM", "Torque_Nm", "Motor_Temp_C", "IGBT_Temp_C"
                ]
                header += [f"Cell_{i:02d}_mV" for i in range(1, 21)]
                header += [f"Module_{m}_degC" for m in range(1, 5)]
                self.log_writer.writerow(header)
                self.logging_active = True
                self.logged_rows = 0
                self.btn_log.setText("⏹ Parar CSV")
                self.btn_log.setStyleSheet("background-color: #991B1B; color: #FFF; font-weight: bold;")
            except Exception as e:
                QMessageBox.critical(self, "Erro Log", f"Erro ao criar log:\n{e}")

    def _on_render_tick(self):
        current_tab = self.tabs.currentIndex()
        if current_tab == 0:
            self.car_panel.update_view()
        elif current_tab == 1:
            self.pack_thermal_panel.update_view()
        elif current_tab == 2:
            self.rf_sensors_panel.update_view()

        frames = self.state.frames_received
        status_txt = self.state.connection_status
        self.lbl_footer_info.setText(
            f"Status: {status_txt}  |  Frames DBC: {frames:,}  |  RF OK: {self.state.rf_packets_ok}  |  Logs CSV: {self.logged_rows}"
        )

        if self.logging_active and self.log_writer:
            now_iso = time.strftime("%Y-%m-%d %H:%M:%S") + f".{int((time.time()%1)*1000):03d}"
            row = [
                now_iso, self.state.fsm_state, f"{self.state.pack_voltage:.2f}", f"{self.state.pack_current:.1f}",
                f"{self.state.pack_soc:.1f}", f"{self.state.dcl:.1f}", f"{self.state.ccl:.1f}",
                self.state.cell_volt_min, self.state.cell_volt_max, self.state.cell_delta_mv,
                1 if self.state.fuse_blown else 0, f"{self.state.z_score:.2f}",
                f"{self.state.apps1_pct:.1f}", f"{self.state.brake_pressure_bar:.1f}",
                f"{self.state.vehicle_speed_kmh:.0f}", self.state.motor_rpm,
                f"{self.state.torque_cmd_nm:.1f}", f"{self.state.motor_temp_c:.1f}", f"{self.state.inverter_temp_c:.1f}"
            ]
            row += self.state.cell_voltages
            row += [f"{t:.1f}" for t in self.state.module_temperatures]
            self.log_writer.writerow(row)
            self.logged_rows += 1

    def closeEvent(self, event):
        self.emulator.stop()
        self.can_receiver.disconnect()
        self.rf_receiver.disconnect()
        self.rf_transmitter.disconnect()
        if self.logging_active and self.log_file:
            self.log_file.close()
        event.accept()

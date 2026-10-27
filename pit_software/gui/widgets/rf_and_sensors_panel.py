"""
rf_and_sensors_panel.py - Painel de Diagnóstico RF (HM-TRP-915S), Inspetor CAN Bruto e Sensores Veiculares
Formula ITA - Formula SAE Electric (2025-2026)
"""

from typing import Callable, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QDialog, QComboBox, QMessageBox
)

from core.telemetry_state import TelemetryState
from io_interfaces.hm_trp_serial import HMTRPConfigTool


class RFAndSensorsPanel(QFrame):
    def __init__(self, state: TelemetryState, send_serial_cb: Optional[Callable[[bytes], bool]] = None, parent=None):
        super().__init__(parent)
        self.state = state
        self.send_serial_cb = send_serial_cb

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        # 1. Linha Superior: Diagnóstico Link RF HM-TRP-915S + Sensores Veiculares (VCU & Inversor)
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        top_row.addWidget(self._build_rf_diag_card(), 48)
        top_row.addWidget(self._build_vehicle_sensors_card(), 52)
        main_layout.addLayout(top_row, 45)

        # 2. Linha Inferior: Inspetor de Barramento CAN (Live Sniffer DBC)
        main_layout.addWidget(self._build_can_inspector_card(), 55)

    def _build_rf_diag_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #1a1e24;
                border: 1px solid #2d3540;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("ENLACE DE RÁDIO 915 MHz (HM-TRP-915S — PROTOCOLO FITA-TELEM v1)")
        title.setStyleSheet("font-size: 12px; font-weight: bold; color: #00e5ff; border: none;")
        header.addWidget(title)
        header.addStretch()

        btn_cfg = QPushButton("⚙ Programar HM-TRP-915S (0xAA 0xFA)")
        btn_cfg.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #00e5ff;
                border: 1px solid #00e5ff;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0f3460;
            }
        """)
        btn_cfg.clicked.connect(self._open_hmtrp_config_dialog)
        header.addWidget(btn_cfg)
        layout.addLayout(header)

        # Grid de Métricas RF
        grid = QGridLayout()
        grid.setSpacing(8)

        def make_box(label_txt: str, init_val: str, color: str):
            f = QFrame()
            f.setStyleSheet("background-color: #14171c; border: 1px solid #262c36; border-radius: 6px;")
            v = QVBoxLayout(f)
            v.setContentsMargins(10, 6, 10, 6)
            lbl_t = QLabel(label_txt)
            lbl_t.setStyleSheet("font-size: 10px; color: #999; font-weight: bold; border: none;")
            lbl_v = QLabel(init_val)
            lbl_v.setStyleSheet(f"font-size: 16px; color: {color}; font-weight: bold; border: none;")
            v.addWidget(lbl_t)
            v.addWidget(lbl_v)
            return f, lbl_v

        b1, self.lbl_rf_ok = make_box("PACOTES VÁLIDOS (RX)", "0 (SEQ: --)", "#00e676")
        b2, self.lbl_rf_crc = make_box("ERROS DE CRC-8 (RUÍDO)", "0", "#ffd600")
        b3, self.lbl_rf_loss = make_box("PERDA DE PACOTES NO AR", "0.0 % (0 perdidos)", "#00e5ff")
        b4, self.lbl_rf_rate = make_box("TAXA DE DADOS (THROUGHPUT)", "0.0 kbps | 0 msg/s", "#ffffff")

        grid.addWidget(b1, 0, 0)
        grid.addWidget(b2, 0, 1)
        grid.addWidget(b3, 1, 0)
        grid.addWidget(b4, 1, 1)
        layout.addLayout(grid)

        info = QLabel(
            " Quadro FITA-TELEM v1: [0xAA 0x55] + [SEQ 1B] + [CAN_ID 2B] + [DLC 1B] + [DATA 8B] + [CRC8 1B] = 15 bytes/frame"
        )
        info.setStyleSheet("font-size: 10px; color: #888; border: none;")
        layout.addWidget(info)

        return card

    def _build_vehicle_sensors_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #1a1e24;
                border: 1px solid #2d3540;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("SENSORES VEICULARES DE EXPANSÃO (VCU 0x200 & INVERSOR 0x201)")
        title.setStyleSheet("font-size: 12px; font-weight: bold; color: #00e5ff; border: none;")
        header.addWidget(title)
        header.addStretch()

        self.lbl_plausibility = QLabel("PEDAL PLAUSÍVEL (EV2.3 OK)")
        self.lbl_plausibility.setStyleSheet("""
            background-color: rgba(0, 230, 118, 0.18);
            color: #00e676;
            border: 1px solid #00e676;
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 10px;
            font-weight: bold;
        """)
        header.addWidget(self.lbl_plausibility)
        layout.addLayout(header)

        # Barras de Pedais APPS e Freio
        bars_grid = QGridLayout()
        bars_grid.setSpacing(6)

        lbl_apps = QLabel("Acelerador (APPS 1/2):")
        lbl_apps.setStyleSheet("font-size: 11px; color: #ccc; border: none;")
        bars_grid.addWidget(lbl_apps, 0, 0)

        self.bar_apps = QProgressBar()
        self.bar_apps.setRange(0, 100)
        self.bar_apps.setValue(0)
        self.bar_apps.setTextVisible(False)
        self.bar_apps.setFixedHeight(14)
        self.bar_apps.setStyleSheet("""
            QProgressBar { background-color: #14171c; border: 1px solid #333; border-radius: 4px; }
            QProgressBar::chunk { background-color: #00e676; border-radius: 3px; }
        """)
        bars_grid.addWidget(self.bar_apps, 0, 1)

        self.lbl_apps_val = QLabel("0.0% / 0.0%")
        self.lbl_apps_val.setStyleSheet("font-size: 11px; font-weight: bold; color: #00e676; border: none;")
        bars_grid.addWidget(self.lbl_apps_val, 0, 2)

        lbl_brk = QLabel("Pressão Freio (BSE):")
        lbl_brk.setStyleSheet("font-size: 11px; color: #ccc; border: none;")
        bars_grid.addWidget(lbl_brk, 1, 0)

        self.bar_brake = QProgressBar()
        self.bar_brake.setRange(0, 70)
        self.bar_brake.setValue(0)
        self.bar_brake.setTextVisible(False)
        self.bar_brake.setFixedHeight(14)
        self.bar_brake.setStyleSheet("""
            QProgressBar { background-color: #14171c; border: 1px solid #333; border-radius: 4px; }
            QProgressBar::chunk { background-color: #ff1744; border-radius: 3px; }
        """)
        bars_grid.addWidget(self.bar_brake, 1, 1)

        self.lbl_brake_val = QLabel("0.0 bar")
        self.lbl_brake_val.setStyleSheet("font-size: 11px; font-weight: bold; color: #ff5252; border: none;")
        bars_grid.addWidget(self.lbl_brake_val, 1, 2)

        layout.addLayout(bars_grid)

        # Cards de Dinâmica e Motor
        dyn_grid = QGridLayout()
        dyn_grid.setSpacing(6)

        def make_mini_stat(title_s: str, val_s: str):
            f = QFrame()
            f.setStyleSheet("background-color: #14171c; border: 1px solid #262c36; border-radius: 5px;")
            l = QVBoxLayout(f)
            l.setContentsMargins(8, 4, 8, 4)
            t = QLabel(title_s)
            t.setStyleSheet("font-size: 9px; color: #888; font-weight: bold; border: none;")
            v = QLabel(val_s)
            v.setStyleSheet("font-size: 13px; color: #fff; font-weight: bold; border: none;")
            l.addWidget(t)
            l.addWidget(v)
            return f, v

        f_spd, self.lbl_speed = make_mini_stat("VELOCIDADE / DIREÇÃO", "0 km/h | 0°")
        f_rpm, self.lbl_rpm = make_mini_stat("ROTAÇÃO MOTOR", "0 RPM")
        f_trq, self.lbl_torque = make_mini_stat("COMANDO TORQUE", "0.0 Nm")
        f_tmp, self.lbl_inv_temp = make_mini_stat("TEMP MOTOR / IGBT", "28.0 °C / 26.0 °C")

        dyn_grid.addWidget(f_spd, 0, 0)
        dyn_grid.addWidget(f_rpm, 0, 1)
        dyn_grid.addWidget(f_trq, 0, 2)
        dyn_grid.addWidget(f_tmp, 0, 3)
        layout.addLayout(dyn_grid)

        return card

    def _build_can_inspector_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #1a1e24;
                border: 1px solid #2d3540;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("INSPETOR DE BARRAMENTO CAN EM TEMPO REAL (SN65HVD230 / HM-TRP-915S SNIFFER)")
        title.setStyleSheet("font-size: 12px; font-weight: bold; color: #00e5ff; border: none;")
        header.addWidget(title)
        header.addStretch()

        lbl_hint = QLabel("Exibe qualquer ID CAN recebido (BMS 0x100..0x130, VCU 0x200, Inversor 0x201 e futuros sensores)")
        lbl_hint.setStyleSheet("font-size: 10px; color: #999; border: none;")
        header.addWidget(lbl_hint)
        layout.addLayout(header)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "CAN ID (Hex / Dec)",
            "Mensagem DBC",
            "Payload Bruto (8 Bytes Hex)",
            "Frames Recebidos",
            "Período Médio (ms)",
            "Taxa Estimada (Hz)"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #14171c;
                color: #e0e0e0;
                border: 1px solid #262c36;
                gridline-color: #262c36;
                font-family: Consolas, monospace;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: #1f242d;
                color: #00e5ff;
                font-weight: bold;
                font-size: 11px;
                border: 1px solid #2d3540;
                padding: 4px;
            }
        """)
        layout.addWidget(self.table)
        return card

    def _open_hmtrp_config_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Programador HopeRF HM-TRP-915S (Comandos Hex 0xAA 0xFA)")
        dlg.resize(520, 320)
        dlg.setStyleSheet("background-color: #14171c; color: #e0e0e0;")

        vbox = QVBoxLayout(dlg)
        info = QLabel(
            "<b>Como colocar o HM-TRP-915S em Modo de Configuração:</b><br>"
            "1. Conecte o pino <b>CONFIG</b> ao <b>GND (LOW)</b> e o pino <b>ENABLE</b> ao <b>GND (LOW)</b>.<br>"
            "2. Em modo CONFIG, o HM-TRP-915S escuta comandos sempre a <b>9600 bps (8N1)</b>.<br>"
            "3. Após gravar os parâmetros abaixo, desconecte o pino <b>CONFIG</b> do GND (deixe em 3.3V ou flutuante) "
            "para voltar ao modo transparente de telemetria!"
        )
        info.setWordWrap(True)
        info.setStyleSheet("background-color: #1a1e24; padding: 10px; border-radius: 6px; border: 1px solid #2d3540;")
        vbox.addWidget(info)

        row_baud = QHBoxLayout()
        row_baud.addWidget(QLabel("Velocidade Desejada (Ar & UART):"))
        combo_rate = QComboBox()
        combo_rate.addItems(["57600", "115200", "38400", "19200", "9600"])
        row_baud.addWidget(combo_rate)
        vbox.addLayout(row_baud)

        lbl_hex_preview = QLabel()
        lbl_hex_preview.setStyleSheet("font-family: Consolas, monospace; font-size: 11px; color: #00e676; padding: 6px;")
        vbox.addWidget(lbl_hex_preview)

        def update_preview():
            rate = int(combo_rate.currentText())
            cmds = HMTRPConfigTool.build_recommended_pit_profile(rate)
            lines = [f"• {desc}: {' '.join(f'{b:02X}' for b in raw)}" for desc, raw in cmds]
            lbl_hex_preview.setText("\n".join(lines))

        combo_rate.currentTextChanged.connect(update_preview)
        update_preview()

        btn_send = QPushButton("Transmitir Comandos 0xAA 0xFA na Porta Serial Conectada")
        btn_send.setStyleSheet("background-color: #00838f; color: #fff; font-weight: bold; padding: 8px; border-radius: 5px;")

        def on_send():
            if not self.send_serial_cb:
                QMessageBox.warning(dlg, "Porta Serial", "Conecte primeiro a porta COM do HM-TRP-915S na barra superior.")
                return
            rate = int(combo_rate.currentText())
            cmds = HMTRPConfigTool.build_recommended_pit_profile(rate)
            ok_all = True
            for _, raw in cmds:
                if not self.send_serial_cb(raw):
                    ok_all = False
            if ok_all:
                QMessageBox.information(
                    dlg,
                    "Comandos Enviados",
                    f"Perfil de 915.0 MHz @ {rate} bps (+20 dBm) enviado com sucesso!\n"
                    "Lembre-se de soltar o pino CONFIG do GND para operar."
                )
            else:
                QMessageBox.warning(
                    dlg,
                    "Porta Serial Desconectada",
                    "Conecte o receptor HM-TRP-915S na porta COM correspondente (a 9600 bps) antes de enviar."
                )

        btn_send.clicked.connect(on_send)
        vbox.addWidget(btn_send)
        dlg.exec()

    def update_view(self):
        # 1. Atualizar estatísticas RF
        seq_str = str(self.state.last_seq_id) if self.state.last_seq_id is not None else "--"
        self.lbl_rf_ok.setText(f"{self.state.rf_packets_ok:,} (SEQ: {seq_str})")
        self.lbl_rf_crc.setText(f"{self.state.rf_crc_errors:,}")

        loss_pct = self.state.rf_packet_loss_pct
        loss_color = "#00e676" if loss_pct < 1.0 else ("#ffd600" if loss_pct < 5.0 else "#ff1744")
        self.lbl_rf_loss.setStyleSheet(f"font-size: 16px; color: {loss_color}; font-weight: bold; border: none;")
        self.lbl_rf_loss.setText(f"{loss_pct:.1f} % ({self.state.rf_packets_lost} perdidos)")

        self.lbl_rf_rate.setText(f"{self.state.rf_bitrate_kbps:.1f} kbps | {self.state.rf_fps:.0f} msg/s")

        # 2. Atualizar Sensores Veiculares (VCU & Inversor)
        a1 = self.state.apps1_pct
        a2 = self.state.apps2_pct
        brk = self.state.brake_pressure_bar
        self.bar_apps.setValue(int(max(0, min(100, a1))))
        self.lbl_apps_val.setText(f"{a1:.1f}% / {a2:.1f}%")
        self.bar_brake.setValue(int(max(0, min(70, brk))))
        self.lbl_brake_val.setText(f"{brk:.1f} bar")

        if self.state.apps_plausible:
            self.lbl_plausibility.setText("PEDAL PLAUSÍVEL (EV2.3 OK)")
            self.lbl_plausibility.setStyleSheet("""
                background-color: rgba(0, 230, 118, 0.18); color: #00e676;
                border: 1px solid #00e676; border-radius: 4px; padding: 2px 8px; font-size: 10px; font-weight: bold;
            """)
        else:
            self.lbl_plausibility.setText("IMPLAUSIBILIDADE APPS/BSE!")
            self.lbl_plausibility.setStyleSheet("""
                background-color: rgba(255, 23, 68, 0.28); color: #ff1744;
                border: 1px solid #ff1744; border-radius: 4px; padding: 2px 8px; font-size: 10px; font-weight: bold;
            """)

        self.lbl_speed.setText(f"{self.state.vehicle_speed_kmh:.0f} km/h | {self.state.steering_angle_deg:+.0f}°")
        self.lbl_rpm.setText(f"{self.state.motor_rpm:,} RPM")
        self.lbl_torque.setText(f"{self.state.torque_cmd_nm:+.1f} Nm")
        self.lbl_inv_temp.setText(f"{self.state.motor_temp_c:.1f} °C / {self.state.inverter_temp_c:.1f} °C")

        # 3. Atualizar Tabela do Inspetor CAN
        inspector_snapshot = dict(sorted(self.state.can_bus_inspector.items()))
        if self.table.rowCount() != len(inspector_snapshot):
            self.table.setRowCount(len(inspector_snapshot))

        for row_idx, (can_id, info) in enumerate(inspector_snapshot.items()):
            period_ms = info["period_ms"]
            freq_hz = (1000.0 / period_ms) if period_ms > 0.5 else 0.0

            cols = [
                f"0x{can_id:03X} ({can_id})",
                info["name"],
                info["hex"],
                f"{info['count']:,}",
                f"{period_ms:.1f} ms" if period_ms > 0 else "--",
                f"{freq_hz:.1f} Hz" if freq_hz > 0 else "--"
            ]
            for col_idx, text in enumerate(cols):
                item = self.table.item(row_idx, col_idx)
                if item is None:
                    item = QTableWidgetItem(text)
                    item.setTextAlignment(Qt.AlignCenter if col_idx != 1 else (Qt.AlignLeft | Qt.AlignVCenter))
                    self.table.setItem(row_idx, col_idx, item)
                else:
                    item.setText(text)

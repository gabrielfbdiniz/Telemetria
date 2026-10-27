"""
pack_metrics.py - Painel Superior de Indicadores Globais e FSM
Formula ITA - Formula SAE Electric (2025-2026)
"""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel, QGridLayout
from PySide6.QtCore import Qt
from core.telemetry_state import TelemetryState


class PackMetricsWidget(QFrame):
    def __init__(self, state: TelemetryState, parent=None):
        super().__init__(parent)
        self.state = state
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                background-color: #1a1e24;
                border: 1px solid #2d3540;
                border-radius: 8px;
            }
        """)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(14, 10, 14, 10)
        main_layout.setSpacing(14)

        # 1. Cartão FSM e Circuito SDC
        fsm_frame = QFrame()
        fsm_frame.setStyleSheet("background-color: #14171c; border-radius: 6px; padding: 6px;")
        fsm_layout = QVBoxLayout(fsm_frame)
        fsm_layout.setContentsMargins(8, 6, 8, 6)

        lbl_fsm_title = QLabel("ESTADO DO BMS (FSM)")
        lbl_fsm_title.setStyleSheet("font-size: 10px; color: #a0a0a0; font-weight: bold;")
        fsm_layout.addWidget(lbl_fsm_title)

        self.lbl_fsm_badge = QLabel("DRIVE")
        self.lbl_fsm_badge.setAlignment(Qt.AlignCenter)
        self.lbl_fsm_badge.setStyleSheet("""
            background-color: #00e676;
            color: #000000;
            font-size: 14px;
            font-weight: 900;
            padding: 4px 12px;
            border-radius: 4px;
        """)
        fsm_layout.addWidget(self.lbl_fsm_badge)

        self.lbl_sdc_status = QLabel("SDC: ARMADO  |  AIRs: FECHADOS")
        self.lbl_sdc_status.setAlignment(Qt.AlignCenter)
        self.lbl_sdc_status.setStyleSheet("font-size: 11px; color: #00e676; font-weight: bold;")
        fsm_layout.addWidget(self.lbl_sdc_status)
        main_layout.addWidget(fsm_frame)

        # Função auxiliar para criar cards métricos grandes
        def create_metric_card(title_str, val_str, unit_str, color_str="#00e5ff"):
            frame = QFrame()
            frame.setStyleSheet("background-color: #14171c; border-radius: 6px; padding: 4px;")
            l = QVBoxLayout(frame)
            l.setContentsMargins(10, 4, 10, 4)
            l.setSpacing(2)

            t = QLabel(title_str)
            t.setStyleSheet("font-size: 10px; color: #a0a0a0; font-weight: bold;")
            l.addWidget(t)

            val = QLabel(f"{val_str} <span style='font-size: 12px; color: #a0a0a0;'>{unit_str}</span>")
            val.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {color_str};")
            l.addWidget(val)
            return frame, val

        # 2. Cartão: Tensão do Pack
        c_volt, self.lbl_voltage = create_metric_card("TENSÃO TOTAL", "72.00", "V", "#00e5ff")
        main_layout.addWidget(c_volt)

        # 3. Cartão: Corrente do Pack
        c_curr, self.lbl_current = create_metric_card("CORRENTE PACK", "0.0", "A", "#ff9100")
        main_layout.addWidget(c_curr)

        # 4. Cartão: Potência Instantânea
        c_pwr, self.lbl_power = create_metric_card("POTÊNCIA ATIVA", "0.0", "kW", "#ffffff")
        main_layout.addWidget(c_pwr)

        # 5. Cartão: SOC e SOH
        c_soc, self.lbl_soc = create_metric_card("ESTADO DE CARGA", "92.5", "%", "#00e676")
        main_layout.addWidget(c_soc)

        # 6. Cartão: Limites Dinâmicos (DCL / CCL)
        c_limits, self.lbl_limits = create_metric_card("LIMITES DINÂMICOS", "250 / 45", "A (DCL/CCL)", "#ffd600")
        main_layout.addWidget(c_limits)

    def update_view(self):
        fsm = self.state.fsm_state
        self.lbl_fsm_badge.setText(fsm)

        # Cores de estado da FSM
        fsm_styles = {
            "DRIVE": "background-color: #00e676; color: #000000;",
            "PRECHARGE": "background-color: #ffd600; color: #000000;",
            "STANDBY": "background-color: #2979ff; color: #ffffff;",
            "BOOT": "background-color: #651fff; color: #ffffff;",
            "CHARGING": "background-color: #00b0ff; color: #000000;",
            "FAULT": "background-color: #ff1744; color: #ffffff;"
        }
        self.lbl_fsm_badge.setStyleSheet(f"""
            {fsm_styles.get(fsm, 'background-color: #757575; color: #ffffff;')}
            font-size: 14px;
            font-weight: 900;
            padding: 4px 12px;
            border-radius: 4px;
        """)

        # Status SDC e AIRs
        sdc_txt = "ARMADO" if self.state.sdc_armed else "<span style='color:#ff1744;'>TRIPPED</span>"
        airs_txt = "FECHADOS" if self.state.air_plus else "ABERTOS"
        self.lbl_sdc_status.setText(f"SDC: {sdc_txt}  |  AIRs: {airs_txt}")

        # Valores
        v_pack = self.state.pack_voltage
        i_pack = self.state.pack_current
        power_kw = (v_pack * i_pack) / 1000.0
        soc = self.state.pack_soc

        self.lbl_voltage.setText(f"{v_pack:.2f} <span style='font-size: 12px; color: #a0a0a0;'>V</span>")
        
        curr_color = "#ff9100" if i_pack >= 0 else "#00e676"  # Laranja para descarga, Verde para recarga
        self.lbl_current.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {curr_color};")
        self.lbl_current.setText(f"{i_pack:+.1f} <span style='font-size: 12px; color: #a0a0a0;'>A</span>")

        self.lbl_power.setText(f"{power_kw:+.2f} <span style='font-size: 12px; color: #a0a0a0;'>kW</span>")
        self.lbl_soc.setText(f"{soc:.1f} <span style='font-size: 12px; color: #a0a0a0;'>%</span>")

        dcl = self.state.dcl
        ccl = self.state.ccl
        self.lbl_limits.setText(f"{dcl:.0f} / {ccl:.0f} <span style='font-size: 12px; color: #a0a0a0;'>A (DCL/CCL)</span>")

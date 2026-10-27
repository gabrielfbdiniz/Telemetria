"""
car_top_down_view.py - Vista Superior Técnica Vetorial do Protótipo FSAE com Sensores HUD
Formula ITA - Formula SAE Electric (2025-2026)
Opção 2: Stealth Glass & Cyber-Chassis (Preto, Laranja, Vermelho e Verde Funcional)
"""

import math
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QLinearGradient
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame, QGridLayout

from core.telemetry_state import TelemetryState


class CarChassisWidget(QWidget):
    """
    Desenho vetorial estilizado em tempo real da vista superior do chassi FSAE,
    com nós de sensores posicionados e coloridos dinamicamente (Verde OK / Vermelho Alarme).
    """
    def __init__(self, state: TelemetryState, parent=None):
        super().__init__(parent)
        self.state = state
        self.setMinimumSize(420, 520)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # Fundo Stealth Carbon
        painter.fillRect(0, 0, w, h, QColor("#0A0B0E"))

        # Grade sutil de engenharia
        grid_pen = QPen(QColor("#161A22"), 1, Qt.DotLine)
        painter.setPen(grid_pen)
        for x in range(0, w, 40):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, 40):
            painter.drawLine(0, y, w, y)

        cx = w / 2.0
        cy = h / 2.0
        scale = min(w / 460.0, h / 560.0)

        painter.save()
        painter.translate(cx, cy)
        painter.scale(scale, scale)

        # 1. Pneus (Dianteiros e Traseiros)
        tire_pen = QPen(QColor("#242A35"), 2)
        tire_brush = QBrush(QColor("#14171E"))

        # Esterçamento dos Pneus Dianteiros baseado no sensor do volante
        steer_rad = math.radians(max(-35.0, min(35.0, self.state.steering_angle_deg * 0.4)))

        # Pneu Dianteiro Esquerdo
        painter.save()
        painter.translate(-115, -165)
        painter.rotate(math.degrees(steer_rad))
        painter.setPen(tire_pen)
        painter.setBrush(tire_brush)
        painter.drawRoundedRect(-16, -34, 32, 68, 6, 6)
        painter.restore()

        # Pneu Dianteiro Direito
        painter.save()
        painter.translate(115, -165)
        painter.rotate(math.degrees(steer_rad))
        painter.setPen(tire_pen)
        painter.setBrush(tire_brush)
        painter.drawRoundedRect(-16, -34, 32, 68, 6, 6)
        painter.restore()

        # Pneus Traseiros (Fixos)
        painter.setPen(tire_pen)
        painter.setBrush(tire_brush)
        painter.drawRoundedRect(-135, 120, 36, 76, 6, 6) # Traseiro Esquerdo
        painter.drawRoundedRect(99, 120, 36, 76, 6, 6)   # Traseiro Direito

        # 2. Silhueta Aerodinâmica FSAE (Asas e Chassi)
        chassis_path = QPainterPath()
        chassis_path.moveTo(0, -225)      # Bico dianteiro
        chassis_path.lineTo(32, -140)     # Monocoque dianteiro
        chassis_path.lineTo(58, -40)      # Abertura Sidepod
        chassis_path.lineTo(65, 90)       # Sidepod traseiro
        chassis_path.lineTo(38, 175)      # Coifa motor
        chassis_path.lineTo(-38, 175)
        chassis_path.lineTo(-65, 90)
        chassis_path.lineTo(-58, -40)
        chassis_path.lineTo(-32, -140)
        chassis_path.closeSubpath()

        # Preenchimento em gradiente preto/grafite fosco
        grad_chassis = QLinearGradient(0, -220, 0, 180)
        grad_chassis.setColorAt(0.0, QColor("#181C24"))
        grad_chassis.setColorAt(0.5, QColor("#101318"))
        grad_chassis.setColorAt(1.0, QColor("#14171E"))

        painter.setPen(QPen(QColor("#FF6B00"), 1.8)) # Contorno Laranja Técnico
        painter.setBrush(grad_chassis)
        painter.drawPath(chassis_path)

        # Asa Dianteira
        painter.setPen(QPen(QColor("#2E3544"), 1.5))
        painter.setBrush(QColor("#0F1116"))
        painter.drawRoundedRect(-125, -232, 250, 18, 3, 3)

        # Asa Traseira
        painter.drawRoundedRect(-120, 178, 240, 24, 4, 4)

        # Cockpit & Volante
        painter.setPen(QPen(QColor("#384152"), 1))
        painter.setBrush(QColor("#090A0D"))
        painter.drawEllipse(-24, -95, 48, 65)

        # 3. Representação Espacial do Acumulador de Tração (Centro do Chassi)
        pack_pen = QPen(QColor("#FF6B00" if not self.state.fuse_blown else "#FF1744"), 1.5)
        painter.setPen(pack_pen)
        painter.setBrush(QColor(255, 107, 0, 22) if not self.state.fuse_blown else QColor(255, 23, 68, 35))
        painter.drawRoundedRect(-42, -25, 84, 105, 5, 5)

        # Linhas dos 4 módulos escravos 5S dentro do pack
        painter.setPen(QPen(QColor("#FF6B00"), 0.8, Qt.DashLine))
        for m_idx in range(1, 4):
            y_div = -25 + m_idx * (105 / 4.0)
            painter.drawLine(-38, y_div, 38, y_div)

        # 4. Representação do Motor & Inversor (Traseira)
        painter.setPen(QPen(QColor("#455268"), 1.2))
        painter.setBrush(QColor("#1A1F29"))
        painter.drawRoundedRect(-28, 95, 56, 42, 4, 4) # Inversor
        painter.drawEllipse(-20, 140, 40, 30)          # Motor elétrico

        # 5. Nós de Sensores Interativos com Callouts Visuais
        # Sensor A: Pedais Dianteiros (APPS & Freio)
        apps_ok = self.state.apps_plausible and (self.state.cell_volt_min >= 2800)
        self._draw_sensor_node(painter, 0, -185, "PEDAIS APPS / FREIO", 
                               f"APPS: {self.state.apps1_pct:.0f}% | Freio: {self.state.brake_pressure_bar:.1f} bar",
                               is_ok=apps_ok, callout_dir="right", offset_x=45, offset_y=-20)

        # Sensor B: Acumulador Central (Tensão, Corrente, SDC)
        bms_ok = (self.state.fsm_state != "FAULT") and self.state.sdc_armed and not self.state.fuse_blown
        self._draw_sensor_node(painter, 0, 26, "ACUMULADOR 20s18p",
                               f"{self.state.pack_voltage:.1f}V | {self.state.pack_current:+.0f}A | {self.state.pack_soc:.0f}% SOC",
                               is_ok=bms_ok, callout_dir="left", offset_x=-55, offset_y=0)

        # Sensor C: Inversor & Motor Traseiro
        inv_ok = (self.state.inverter_temp_c < 65.0) and (self.state.motor_temp_c < 80.0)
        self._draw_sensor_node(painter, 0, 115, "INVERSOR & MOTOR",
                               f"{self.state.motor_rpm} RPM | {self.state.motor_temp_c:.0f}°C | {self.state.inverter_temp_c:.0f}°C",
                               is_ok=inv_ok, callout_dir="right", offset_x=45, offset_y=15)

        painter.restore()

    def _draw_sensor_node(self, painter: QPainter, x: float, y: float, title: str, subtitle: str, 
                          is_ok: bool, callout_dir: str = "right", offset_x: float = 40, offset_y: float = 0):
        color_node = QColor("#00E676") if is_ok else QColor("#FF1744")
        bg_card = QColor("#12151D")
        border_card = QColor("#00E676") if is_ok else QColor("#FF1744")

        # Ponto / Nó central no chassi com halo pulsante suave
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(color_node.red(), color_node.green(), color_node.blue(), 60))
        painter.drawEllipse(QPointF(x, y), 9, 9)
        painter.setBrush(color_node)
        painter.drawEllipse(QPointF(x, y), 4.5, 4.5)

        # Linha líder até o callout
        card_w = 175
        card_h = 38
        if callout_dir == "right":
            tx = x + offset_x
            ty = y + offset_y
            painter.setPen(QPen(border_card, 1.2, Qt.SolidLine))
            painter.drawLine(x, y, tx, ty + card_h / 2)
            card_rect = QRectF(tx, ty, card_w, card_h)
        else:
            tx = x + offset_x - card_w
            ty = y + offset_y
            painter.setPen(QPen(border_card, 1.2, Qt.SolidLine))
            painter.drawLine(x, y, tx + card_w, ty + card_h / 2)
            card_rect = QRectF(tx, ty, card_w, card_h)

        # Caixa do Callout Stealth Glass
        painter.setPen(QPen(border_card, 1))
        painter.setBrush(bg_card)
        painter.drawRoundedRect(card_rect, 5, 5)

        # Tag de status (Verde OK ou Vermelho ALERTA)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color_node)
        painter.drawRect(QRectF(card_rect.left(), card_rect.top() + 4, 3, card_h - 8))

        # Textos
        painter.setPen(QColor("#E2E8F0"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.drawText(QRectF(card_rect.left() + 9, card_rect.top() + 4, card_w - 12, 14), Qt.AlignLeft, title)

        painter.setPen(color_node)
        painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
        painter.drawText(QRectF(card_rect.left() + 9, card_rect.top() + 18, card_w - 12, 16), Qt.AlignLeft, subtitle)


class CarTopDownHUDPanel(QFrame):
    """
    Painel Completo Tela 1:
    - Lado Esquerdo: Race Telemetry Rail (Métricas vitais de pista em números grandes)
    - Lado Direito: Chassi Vetorial com Nós de Sensores Interativos
    """
    def __init__(self, state: TelemetryState, parent=None):
        super().__init__(parent)
        self.state = state
        self.setStyleSheet("""
            QFrame {
                background-color: #0A0B0E;
                border: none;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(12)

        # 1. Coluna Esquerda: Vital Metrics Rail (Preto + Laranja + Vermelho)
        rail = self._build_telemetry_rail()
        layout.addWidget(rail, 38)

        # 2. Coluna Direita: Chassi do Veículo com Sensores
        chassis_frame = QFrame()
        chassis_frame.setStyleSheet("""
            QFrame {
                background-color: #0F1218;
                border: 1px solid #1F2430;
                border-radius: 8px;
            }
        """)
        c_layout = QVBoxLayout(chassis_frame)
        c_layout.setContentsMargins(6, 8, 6, 8)

        header = QHBoxLayout()
        t = QLabel("VISTA SUPERIOR DO VEÍCULO & LOCALIZAÇÃO ESPACIAL DE SENSORES")
        t.setStyleSheet("font-size: 11px; font-weight: 900; color: #FF6B00; letter-spacing: 1px;")
        header.addWidget(t)
        header.addStretch()

        legend = QLabel("● VERDE: Nominal  |  ● VERMELHO: Violação / Alarme")
        legend.setStyleSheet("font-size: 10px; font-weight: bold; color: #A0AEC0;")
        header.addWidget(legend)
        c_layout.addLayout(header)

        self.chassis_widget = CarChassisWidget(self.state)
        c_layout.addWidget(self.chassis_widget, 1)

        layout.addWidget(chassis_frame, 62)

    def _build_telemetry_rail(self) -> QFrame:
        rail = QFrame()
        rail.setStyleSheet("""
            QFrame {
                background-color: #0F1218;
                border: 1px solid #1F2430;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Header do Painel
        lbl_head = QLabel("TELEMETRIA DE PISTA — PARÂMETROS GERAIS")
        lbl_head.setStyleSheet("font-size: 11px; font-weight: 900; color: #FF6B00; letter-spacing: 1px;")
        layout.addWidget(lbl_head)

        # Velocidade em Destaque Gigante
        speed_box = QFrame()
        speed_box.setStyleSheet("background-color: #141720; border: 1px solid #232936; border-radius: 6px; padding: 6px;")
        sb_layout = QVBoxLayout(speed_box)
        sb_layout.setContentsMargins(10, 6, 10, 6)
        sb_title = QLabel("VELOCIDADE ESTIMADA")
        sb_title.setStyleSheet("font-size: 10px; color: #8C9BAE; font-weight: bold;")
        sb_layout.addWidget(sb_title)

        self.lbl_speed_val = QLabel("0 <span style='font-size: 16px; color: #8C9BAE;'>km/h</span>")
        self.lbl_speed_val.setStyleSheet("font-size: 38px; font-weight: 900; color: #FFFFFF;")
        sb_layout.addWidget(self.lbl_speed_val)
        layout.addWidget(speed_box)

        # Grid de Métricas Principais
        grid = QGridLayout()
        grid.setSpacing(8)

        def make_rail_card(title: str, val_init: str, color: str = "#FF8800"):
            f = QFrame()
            f.setStyleSheet("background-color: #141720; border: 1px solid #232936; border-radius: 6px;")
            l = QVBoxLayout(f)
            l.setContentsMargins(10, 8, 10, 8)
            l.setSpacing(2)
            t = QLabel(title)
            t.setStyleSheet("font-size: 9px; color: #8C9BAE; font-weight: bold;")
            v = QLabel(val_init)
            v.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {color};")
            l.addWidget(t)
            l.addWidget(v)
            return f, v

        c1, self.lbl_power_val = make_rail_card("POTÊNCIA ATIVA", "0.0 kW", "#FFFFFF")
        c2, self.lbl_energy_val = make_rail_card("ENERGIA CONSUMIDA", "0.00 kWh", "#FF8800")
        c3, self.lbl_current_val = make_rail_card("CORRENTE PACK", "0.0 A", "#FF6B00")
        c4, self.lbl_delta_val = make_rail_card("DESBALANCEAMENTO (ΔV)", "0 mV", "#00E676")

        grid.addWidget(c1, 0, 0)
        grid.addWidget(c2, 0, 1)
        grid.addWidget(c3, 1, 0)
        grid.addWidget(c4, 1, 1)
        layout.addLayout(grid)

        # Status FSM & Circuito de Shutdown (SDC)
        safety_box = QFrame()
        safety_box.setStyleSheet("background-color: #141720; border: 1px solid #232936; border-radius: 6px; padding: 6px;")
        sf_layout = QVBoxLayout(safety_box)
        sf_layout.setContentsMargins(10, 8, 10, 8)
        sf_title = QLabel("ESTADO DE SEGURANÇA & MALHA SDC (FSAE EV)")
        sf_title.setStyleSheet("font-size: 9px; color: #8C9BAE; font-weight: bold;")
        sf_layout.addWidget(sf_title)

        self.lbl_fsm_badge = QLabel("DRIVE — SDC ARMADO")
        self.lbl_fsm_badge.setStyleSheet("""
            background-color: rgba(0, 230, 118, 0.15);
            color: #00E676;
            border: 1px solid #00E676;
            border-radius: 4px;
            padding: 6px;
            font-size: 12px;
            font-weight: 900;
        """)
        self.lbl_fsm_badge.setAlignment(Qt.AlignCenter)
        sf_layout.addWidget(self.lbl_fsm_badge)
        layout.addWidget(safety_box)

        # Informação sobre limite FSAE
        fsae_info = QLabel("Regra FSAE EV: Tensão máx 84V (TS) | Potência máx 80 kW | Temperatura máx 60.0°C")
        fsae_info.setWordWrap(True)
        fsae_info.setStyleSheet("font-size: 9px; color: #64748B; margin-top: 4px;")
        layout.addWidget(fsae_info)

        layout.addStretch()
        return rail

    def update_view(self):
        # 1. Repintar chassi do carro
        self.chassis_widget.update()

        # 2. Atualizar métricas do rail
        spd = self.state.vehicle_speed_kmh
        self.lbl_speed_val.setText(f"{spd:.0f} <span style='font-size: 16px; color: #8C9BAE;'>km/h</span>")

        power_kw = (self.state.pack_voltage * self.state.pack_current) / 1000.0
        p_color = "#FF1744" if abs(power_kw) > 72.0 else "#FFFFFF"
        self.lbl_power_val.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {p_color};")
        self.lbl_power_val.setText(f"{power_kw:+.1f} kW")

        # Estimativa de energia consumida baseada na variação de SOC (54 Ah @ 72V nom ~= 3.88 kWh)
        energy_kwh = max(0.0, (100.0 - self.state.pack_soc) * 0.0388)
        self.lbl_energy_val.setText(f"{energy_kwh:.2f} kWh")

        i_pack = self.state.pack_current
        i_color = "#FF8800" if i_pack >= 0 else "#00E676"
        self.lbl_current_val.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {i_color};")
        self.lbl_current_val.setText(f"{i_pack:+.1f} A")

        delta = self.state.cell_delta_mv
        d_color = "#00E676" if delta < 60 else ("#FF8800" if delta < 120 else "#FF1744")
        self.lbl_delta_val.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {d_color};")
        self.lbl_delta_val.setText(f"{delta} mV")

        # Status FSM
        fsm = self.state.fsm_state
        sdc = "ARMADO" if self.state.sdc_armed else "TRIPPED"
        if fsm == "DRIVE" and self.state.sdc_armed:
            self.lbl_fsm_badge.setText("DRIVE — SDC ARMADO (OK)")
            self.lbl_fsm_badge.setStyleSheet("""
                background-color: rgba(0, 230, 118, 0.15); color: #00E676;
                border: 1px solid #00E676; border-radius: 4px; padding: 6px; font-size: 12px; font-weight: 900;
            """)
        else:
            self.lbl_fsm_badge.setText(f"{fsm} — SDC {sdc}")
            self.lbl_fsm_badge.setStyleSheet("""
                background-color: rgba(255, 23, 68, 0.25); color: #FF1744;
                border: 1px solid #FF1744; border-radius: 4px; padding: 6px; font-size: 12px; font-weight: 900;
            """)

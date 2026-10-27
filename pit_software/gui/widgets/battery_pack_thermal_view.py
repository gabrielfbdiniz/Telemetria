"""
battery_pack_thermal_view.py - Visão Estrutural, Mapa Térmico e Detalhamento Expansível por Módulo
Formula ITA - Formula SAE Electric (2025-2026)
Opção 2: Stealth Glass & Cyber-Chassis (Preto, Laranja, Vermelho e Verde Funcional)
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout,
    QPushButton, QProgressBar
)
import pyqtgraph as pg

from core.telemetry_state import TelemetryState


class BatteryPackThermalPanel(QFrame):
    """
    Tela 2:
    - Superior / Esquerda: Visão Estrutural dos 4 Módulos do Pack com Mapa de Calor NTC
    - Inferior / Direita: Detalhamento Expansível do Módulo Selecionado (Tensões 5S, NTC e Fusível RLS)
    """
    def __init__(self, state: TelemetryState, parent=None):
        super().__init__(parent)
        self.state = state
        self.selected_module_idx = 0  # 0 = Módulo 1 (Células 1-5), 1 = Mód 2 (6-10), etc.

        self.setStyleSheet("""
            QFrame {
                background-color: #0A0B0E;
                border: none;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(10)

        # 1. Seção Superior: Visão Geral dos 4 Módulos (Heatmap Cards)
        main_layout.addWidget(self._build_pack_overview_card(), 45)

        # 2. Seção Inferior: Módulo Detalhado Expansível
        main_layout.addWidget(self._build_module_detail_card(), 55)

    def _build_pack_overview_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #0F1218;
                border: 1px solid #1F2430;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("DISTRIBUIÇÃO TÉRMICA & ARQUITETURA DO PACK DE BATERIAS (20s18p — 4 MÓDULOS 5S)")
        title.setStyleSheet("font-size: 11px; font-weight: 900; color: #FF6B00; letter-spacing: 1px;")
        header.addWidget(title)
        header.addStretch()

        self.lbl_pack_extremes = QLabel("Temp Máx: 28.5 °C (Mód #3) | Delta Térmico: 0.9 °C")
        self.lbl_pack_extremes.setStyleSheet("font-size: 11px; font-weight: bold; color: #00E676;")
        header.addWidget(self.lbl_pack_extremes)
        layout.addLayout(header)

        # 4 Cartões dos Módulos (Heatmap)
        modules_grid = QGridLayout()
        modules_grid.setSpacing(10)

        self.module_cards = []
        self.module_temp_labels = []
        self.module_volt_labels = []

        for m in range(4):
            m_frame = QFrame()
            m_frame.setStyleSheet("""
                QFrame {
                    background-color: #141720;
                    border: 1px solid #28303F;
                    border-radius: 6px;
                    padding: 4px;
                }
            """)
            m_layout = QVBoxLayout(m_frame)
            m_layout.setContentsMargins(12, 8, 12, 8)
            m_layout.setSpacing(4)

            top_m = QHBoxLayout()
            m_title = QLabel(f"MÓDULO #{m+1} (5S18p)")
            m_title.setStyleSheet("font-size: 10px; font-weight: 900; color: #FF8800;")
            top_m.addWidget(m_title)
            top_m.addStretch()

            lbl_t = QLabel("28.0 °C")
            lbl_t.setStyleSheet("font-size: 14px; font-weight: 900; color: #00E676;")
            top_m.addWidget(lbl_t)
            self.module_temp_labels.append(lbl_t)
            m_layout.addLayout(top_m)

            lbl_v = QLabel("Tensão Barramento: 18.00 V")
            lbl_v.setStyleSheet("font-size: 10px; color: #8C9BAE;")
            m_layout.addWidget(lbl_v)
            self.module_volt_labels.append(lbl_v)

            pbar = QProgressBar()
            pbar.setRange(20, 65)
            pbar.setValue(28)
            pbar.setTextVisible(False)
            pbar.setFixedHeight(8)
            pbar.setStyleSheet("""
                QProgressBar { background-color: #0A0B0E; border: 1px solid #1F2430; border-radius: 4px; }
                QProgressBar::chunk { background-color: #00E676; border-radius: 3px; }
            """)
            m_layout.addWidget(pbar)

            # Botão de Selecionar para detalhamento
            btn_sel = QPushButton(f"🔍 Inspecionar Módulo #{m+1}")
            btn_sel.setStyleSheet("""
                QPushButton {
                    background-color: #1A1F2B;
                    color: #E2E8F0;
                    border: 1px solid #2D3748;
                    border-radius: 4px;
                    padding: 4px;
                    font-size: 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #FF6B00;
                    color: #000000;
                    border-color: #FF8800;
                }
            """)
            # Fix closure in loop
            btn_sel.clicked.connect(lambda _, idx=m: self._select_module(idx))
            m_layout.addWidget(btn_sel)

            modules_grid.addWidget(m_frame, 0, m)
            self.module_cards.append((m_frame, pbar))

        layout.addLayout(modules_grid)
        return card

    def _build_module_detail_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #0F1218;
                border: 1px solid #1F2430;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        # Seletor Pill Tabs no Topo
        pill_layout = QHBoxLayout()
        self.lbl_selected_title = QLabel("DETALHAMENTO EXPANSÍVEL — MÓDULO #1 (CÉLULAS 01 A 05)")
        self.lbl_selected_title.setStyleSheet("font-size: 11px; font-weight: 900; color: #FFFFFF; letter-spacing: 1px;")
        pill_layout.addWidget(self.lbl_selected_title)
        pill_layout.addStretch()

        self.pill_buttons = []
        for i in range(4):
            btn = QPushButton(f"Módulo #{i+1}")
            btn.setCheckable(True)
            if i == 0:
                btn.setChecked(True)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #141720;
                    color: #A0AEC0;
                    border: 1px solid #28303F;
                    border-radius: 12px;
                    padding: 4px 14px;
                    font-size: 10px;
                    font-weight: bold;
                }
                QPushButton:checked {
                    background-color: #FF6B00;
                    color: #000000;
                    border-color: #FF8800;
                }
            """)
            btn.clicked.connect(lambda _, idx=i: self._select_module(idx))
            pill_layout.addWidget(btn)
            self.pill_buttons.append(btn)

        layout.addLayout(pill_layout)

        # Divisão 50/50: Gráfico das 5 Células vs Painel de Saúde do Módulo
        split_layout = QHBoxLayout()
        split_layout.setSpacing(12)

        # Gráfico das 5 Células
        pg.setConfigOptions(antialias=True)
        self.plot_detail = pg.PlotWidget()
        self.plot_detail.setBackground("#0A0B0E")
        self.plot_detail.showGrid(x=True, y=True, alpha=0.2)
        self.plot_detail.setYRange(2500, 4350)
        self.plot_detail.setXRange(0, 6)
        self.plot_detail.getAxis("bottom").setTicks([[ (k, f"Célula #{k}") for k in range(1, 6) ]])
        self.plot_detail.getAxis("left").setLabel("Tensão (mV)", color="#8C9BAE")

        # Linhas de Limite FSAE
        self.plot_detail.addItem(pg.InfiniteLine(pos=4200, angle=0, pen=pg.mkPen(color="#FF1744", width=1.2, style=Qt.DashLine)))
        self.plot_detail.addItem(pg.InfiniteLine(pos=2800, angle=0, pen=pg.mkPen(color="#FF1744", width=1.2, style=Qt.DashLine)))

        self.detail_bars = pg.BarGraphItem(x=[1, 2, 3, 4, 5], height=[3600]*5, width=0.55, brush="#00E676", pen=pg.mkPen("#000000", width=1))
        self.plot_detail.addItem(self.detail_bars)
        split_layout.addWidget(self.plot_detail, 60)

        # Painel Lateral de Diagnóstico do Módulo
        side_panel = QFrame()
        side_panel.setStyleSheet("background-color: #141720; border: 1px solid #232936; border-radius: 6px; padding: 8px;")
        sp_layout = QVBoxLayout(side_panel)
        sp_layout.setContentsMargins(10, 8, 10, 8)
        sp_layout.setSpacing(8)

        lbl_diag_head = QLabel("DIAGNÓSTICO TÉRMICO & FUSÍVEL DO MÓDULO")
        lbl_diag_head.setStyleSheet("font-size: 10px; font-weight: 900; color: #FF8800;")
        sp_layout.addWidget(lbl_diag_head)

        self.lbl_mod_volt_total = QLabel("Tensão do Barramento 5S: 18.00 V")
        self.lbl_mod_volt_total.setStyleSheet("font-size: 12px; font-weight: bold; color: #FFFFFF;")
        sp_layout.addWidget(self.lbl_mod_volt_total)

        self.lbl_mod_temp_exact = QLabel("Sensor NTC Módulo: 28.0 °C (Nominal)")
        self.lbl_mod_temp_exact.setStyleSheet("font-size: 12px; font-weight: bold; color: #00E676;")
        sp_layout.addWidget(self.lbl_mod_temp_exact)

        self.lbl_mod_delta = QLabel("Delta Interno do Módulo: 8 mV")
        self.lbl_mod_delta.setStyleSheet("font-size: 12px; font-weight: bold; color: #00E676;")
        sp_layout.addWidget(self.lbl_mod_delta)

        self.lbl_mod_fuse_status = QLabel("FUSÍVEIS DO SEGMENTO: TODOS ÍNTEGROS (18p)")
        self.lbl_mod_fuse_status.setStyleSheet("""
            background-color: rgba(0, 230, 118, 0.15);
            color: #00E676;
            border: 1px solid #00E676;
            border-radius: 4px;
            padding: 8px;
            font-size: 11px;
            font-weight: bold;
        """)
        sp_layout.addWidget(self.lbl_mod_fuse_status)
        sp_layout.addStretch()

        split_layout.addWidget(side_panel, 40)
        layout.addLayout(split_layout)

        return card

    def _select_module(self, idx: int):
        self.selected_module_idx = idx
        for i, btn in enumerate(self.pill_buttons):
            btn.setChecked(i == idx)
        start_cell = idx * 5 + 1
        end_cell = start_cell + 4
        self.lbl_selected_title.setText(f"DETALHAMENTO EXPANSÍVEL — MÓDULO #{idx+1} (CÉLULAS {start_cell:02d} A {end_cell:02d})")
        self.plot_detail.getAxis("bottom").setTicks([[ (k - start_cell + 1, f"Célula #{k}") for k in range(start_cell, end_cell + 1) ]])
        self.update_view()

    def update_view(self):
        temps = self.state.module_temperatures
        t_min = min(temps)
        t_max = max(temps)
        t_delta = t_max - t_min

        color_extremes = "#00E676" if t_max < 50.0 else ("#FF8800" if t_max < 58.0 else "#FF1744")
        self.lbl_pack_extremes.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {color_extremes};")
        self.lbl_pack_extremes.setText(f"Temp Máx: {t_max:.1f} °C (Mód #{temps.index(t_max)+1}) | Delta Térmico: {t_delta:.1f} °C")

        # Atualizar os 4 cards superiores
        all_cells = self.state.cell_voltages
        for m in range(4):
            t = temps[m]
            lbl_t = self.module_temp_labels[m]
            lbl_v = self.module_volt_labels[m]
            frame, pbar = self.module_cards[m]

            pbar.setValue(int(max(20, min(65, t))))
            lbl_t.setText(f"{t:.1f} °C")

            # Tensão do barramento somando as 5 células do módulo
            m_cells = all_cells[m * 5 : (m + 1) * 5]
            v_sum = sum(m_cells) / 1000.0
            lbl_v.setText(f"Tensão Barramento: {v_sum:.2f} V")

            # Cor do degradê térmico
            if t >= 58.0:
                color_hex = "#FF1744"
                pbar.setStyleSheet("""
                    QProgressBar { background-color: #0A0B0E; border: 1px solid #FF1744; border-radius: 4px; }
                    QProgressBar::chunk { background-color: #FF1744; border-radius: 3px; }
                """)
            elif t >= 45.0:
                color_hex = "#FF8800"
                pbar.setStyleSheet("""
                    QProgressBar { background-color: #0A0B0E; border: 1px solid #FF8800; border-radius: 4px; }
                    QProgressBar::chunk { background-color: #FF8800; border-radius: 3px; }
                """)
            else:
                color_hex = "#00E676"
                pbar.setStyleSheet("""
                    QProgressBar { background-color: #0A0B0E; border: 1px solid #1F2430; border-radius: 4px; }
                    QProgressBar::chunk { background-color: #00E676; border-radius: 3px; }
                """)
            lbl_t.setStyleSheet(f"font-size: 14px; font-weight: 900; color: {color_hex};")

        # Atualizar o módulo detalhado selecionado
        sel = self.selected_module_idx
        start = sel * 5
        sub_cells = all_cells[start : start + 5]
        v_sub_sum = sum(sub_cells) / 1000.0
        self.lbl_mod_volt_total.setText(f"Tensão do Barramento 5S: {v_sub_sum:.2f} V")

        t_sel = temps[sel]
        status_temp = "Nominal" if t_sel < 45.0 else ("Atenção" if t_sel < 58.0 else "CRÍTICO (>60°C)")
        t_col = "#00E676" if t_sel < 45.0 else ("#FF8800" if t_sel < 58.0 else "#FF1744")
        self.lbl_mod_temp_exact.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {t_col};")
        self.lbl_mod_temp_exact.setText(f"Sensor NTC Módulo: {t_sel:.1f} °C ({status_temp})")

        d_sub = max(sub_cells) - min(sub_cells)
        d_col = "#00E676" if d_sub < 40 else ("#FF8800" if d_sub < 90 else "#FF1744")
        self.lbl_mod_delta.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {d_col};")
        self.lbl_mod_delta.setText(f"Delta Interno do Módulo: {d_sub} mV")

        # Verificar se o fusível rompido pertence a este módulo
        blown = self.state.fuse_blown
        blown_idx = self.state.blown_block_index
        if blown and (start <= blown_idx < start + 5):
            self.lbl_mod_fuse_status.setText(f"⚠ FUSÍVEL ROMPIDO NO BLOCO #{blown_idx + 1} (OPERAÇÃO 17P)")
            self.lbl_mod_fuse_status.setStyleSheet("""
                background-color: rgba(255, 23, 68, 0.25);
                color: #FF1744;
                border: 2px solid #FF1744;
                border-radius: 4px;
                padding: 8px;
                font-size: 11px;
                font-weight: bold;
            """)
        else:
            self.lbl_mod_fuse_status.setText("FUSÍVEIS DO SEGMENTO: TODOS ÍNTEGROS (18p)")
            self.lbl_mod_fuse_status.setStyleSheet("""
                background-color: rgba(0, 230, 118, 0.15);
                color: #00E676;
                border: 1px solid #00E676;
                border-radius: 4px;
                padding: 8px;
                font-size: 11px;
                font-weight: bold;
            """)

        # Cores das 5 barras
        brushes = []
        for v in sub_cells:
            if v < 2800 or v > 4220:
                brushes.append(pg.mkBrush("#FF1744"))
            elif v < 3100:
                brushes.append(pg.mkBrush("#FF8800"))
            else:
                brushes.append(pg.mkBrush("#00E676"))
        self.detail_bars.setOpts(height=sub_cells, brushes=brushes)

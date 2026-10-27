"""
cell_bars.py - Visualizador Gráfico das 20 Células em Tempo Real
Formula ITA - Formula SAE Electric (2025-2026)
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
import pyqtgraph as pg
from core.telemetry_state import TelemetryState


class CellBarsWidget(QFrame):
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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)

        # Cabeçalho com métricas extremas
        header_layout = QHBoxLayout()
        title = QLabel("TENSÕES INDIVIDUAIS DOS 20 BLOCOS (mV)")
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #00e5ff; letter-spacing: 1px;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.lbl_extremes = QLabel("Min: 3.600 V (#1) | Max: 3.600 V (#1) | Delta: 0 mV")
        self.lbl_extremes.setStyleSheet("font-size: 12px; font-weight: bold; color: #e0e0e0;")
        header_layout.addWidget(self.lbl_extremes)
        layout.addLayout(header_layout)

        # Plot PyQtGraph
        pg.setConfigOptions(antialias=True)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground("#14171c")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.25)
        self.plot_widget.setYRange(2500, 4350)
        self.plot_widget.setXRange(0, 21)
        self.plot_widget.getAxis("bottom").setTicks([[ (i, f"#{i}") for i in range(1, 21) ]])
        self.plot_widget.getAxis("left").setLabel("Tensão (mV)", color="#a0a0a0")

        # Linhas de Limites FSAE
        line_max = pg.InfiniteLine(pos=4200, angle=0, pen=pg.mkPen(color="#ff3344", width=1.5, style=Qt.DashLine))
        line_min = pg.InfiniteLine(pos=2800, angle=0, pen=pg.mkPen(color="#ff3344", width=1.5, style=Qt.DashLine))
        line_nom = pg.InfiniteLine(pos=3600, angle=0, pen=pg.mkPen(color="#44bbff", width=1, style=Qt.DotLine))
        self.plot_widget.addItem(line_max)
        self.plot_widget.addItem(line_min)
        self.plot_widget.addItem(line_nom)

        self.bar_item = pg.BarGraphItem(x=list(range(1, 21)), height=[3600]*20, width=0.68, brush="#00e676", pen=pg.mkPen("#00b359", width=1))
        self.plot_widget.addItem(self.bar_item)

        layout.addWidget(self.plot_widget)

    def update_view(self):
        voltages = self.state.cell_voltages
        v_min = self.state.cell_volt_min
        v_max = self.state.cell_volt_max
        v_min_id = self.state.cell_volt_min_id
        v_max_id = self.state.cell_volt_max_id
        delta_mv = self.state.cell_delta_mv

        # Atualizar texto do cabeçalho
        color_delta = "#00e676" if delta_mv < 80 else ("#ffbb33" if delta_mv < 150 else "#ff3344")
        self.lbl_extremes.setText(
            f"V_min: {v_min/1000.0:.3f} V (Bloco #{v_min_id})  |  "
            f"V_max: {v_max/1000.0:.3f} V (Bloco #{v_max_id})  |  "
            f"<span style='color:{color_delta};'>Delta: {delta_mv} mV</span>"
        )

        # Montar cores personalizadas das barras (destaca anomalias e limites)
        brushes = []
        for i, v in enumerate(voltages):
            if v < 2800 or v > 4220:
                brushes.append(pg.mkBrush("#ff1744"))  # Alarme crítico Vermelho
            elif v < 3100:
                brushes.append(pg.mkBrush("#ff9100"))  # Subtensão preliminar Laranja
            elif i + 1 == v_min_id and delta_mv > 60:
                brushes.append(pg.mkBrush("#2979ff"))  # Menor célula destacada em Azul
            else:
                brushes.append(pg.mkBrush("#00e676"))  # Normal Verde Esmeralda

        self.bar_item.setOpts(height=voltages, brushes=brushes)

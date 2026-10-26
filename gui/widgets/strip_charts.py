"""
strip_charts.py - Gráficos Temporais Contínuos de Corrente, Tensão e SOC
Formula ITA - Formula SAE Electric (2025-2026)
"""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
import pyqtgraph as pg
from core.telemetry_state import TelemetryState


class StripChartsWidget(QFrame):
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

        title = QLabel("TELEMETRIA TEMPORAL: CORRENTE (A) & TENSÃO (V)")
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #00e5ff; letter-spacing: 1px;")
        layout.addWidget(title)

        # Plot 1: Corrente do Pack
        self.plot_current = pg.PlotWidget()
        self.plot_current.setBackground("#14171c")
        self.plot_current.showGrid(x=True, y=True, alpha=0.25)
        self.plot_current.setYRange(-50, 200)
        self.plot_current.getAxis("left").setLabel("Corrente (A)", color="#ff9100")
        self.curve_current = self.plot_current.plot(pen=pg.mkPen(color="#ff9100", width=2))
        
        # Linha zero de corrente
        zero_line = pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen(color="#666666", width=1, style=pg.QtCore.Qt.DashLine))
        self.plot_current.addItem(zero_line)
        layout.addWidget(self.plot_current)

        # Plot 2: Tensão do Pack e SOC
        self.plot_voltage = pg.PlotWidget()
        self.plot_voltage.setBackground("#14171c")
        self.plot_voltage.showGrid(x=True, y=True, alpha=0.25)
        self.plot_voltage.setYRange(55, 86)
        self.plot_voltage.getAxis("left").setLabel("Tensão Pack (V)", color="#00e5ff")
        self.curve_voltage = self.plot_voltage.plot(pen=pg.mkPen(color="#00e5ff", width=2))
        layout.addWidget(self.plot_voltage)

    def update_view(self):
        if len(self.state.current_history) > 1:
            curr_data = list(self.state.current_history)
            volt_data = list(self.state.voltage_history)
            x_axis = list(range(len(curr_data)))

            self.curve_current.setData(x_axis, curr_data)
            self.curve_voltage.setData(x_axis, volt_data)

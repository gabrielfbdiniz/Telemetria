"""
fuse_diag.py - Painel de Diagnóstico do Algoritmo RLS de Fusível & Temperaturas
Formula ITA - Formula SAE Electric (2025-2026)
"""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QProgressBar
from PySide6.QtCore import Qt
from core.telemetry_state import TelemetryState


class FuseDiagnosticWidget(QFrame):
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
        layout.setSpacing(10)

        title = QLabel("DIAGNÓSTICO RLS (FUSÍVEIS) & TEMPERATURAS")
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #00e5ff; letter-spacing: 1px;")
        layout.addWidget(title)

        # 1. Seção Térmica: 4 Módulos Escravos
        temp_title = QLabel("Temperaturas dos Módulos Escravos (NTC):")
        temp_title.setStyleSheet("font-size: 11px; color: #a0a0a0; font-weight: bold;")
        layout.addWidget(temp_title)

        grid_temp = QGridLayout()
        grid_temp.setSpacing(8)
        self.temp_bars = []
        self.temp_labels = []

        for m in range(4):
            lbl_name = QLabel(f"Módulo #{m+1} (5S):")
            lbl_name.setStyleSheet("font-size: 11px; color: #cfcfcf;")
            grid_temp.addWidget(lbl_name, m, 0)

            bar = QProgressBar()
            bar.setRange(20, 65)
            bar.setValue(25)
            bar.setTextVisible(False)
            bar.setFixedHeight(14)
            bar.setStyleSheet("""
                QProgressBar {
                    background-color: #14171c;
                    border: 1px solid #333;
                    border-radius: 4px;
                }
                QProgressBar::chunk {
                    background-color: #00e676;
                    border-radius: 3px;
                }
            """)
            grid_temp.addWidget(bar, m, 1)
            self.temp_bars.append(bar)

            lbl_val = QLabel("25.0 °C")
            lbl_val.setStyleSheet("font-size: 11px; font-weight: bold; color: #00e676;")
            grid_temp.addWidget(lbl_val, m, 2)
            self.temp_labels.append(lbl_val)

        layout.addLayout(grid_temp)

        # Linha Divisória
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("border-top: 1px solid #2d3540;")
        layout.addWidget(line)

        # 2. Seção RLS e Fusível
        rls_title = QLabel("Estimador RLS de Resistência Ôhmica (20s18p):")
        rls_title.setStyleSheet("font-size: 11px; color: #a0a0a0; font-weight: bold;")
        layout.addWidget(rls_title)

        # Banner de Status de Fusível
        self.lbl_fuse_status = QLabel("TODOS OS 20 BLOCOS ÍNTEGROS (18P)")
        self.lbl_fuse_status.setAlignment(Qt.AlignCenter)
        self.lbl_fuse_status.setStyleSheet("""
            background-color: rgba(0, 230, 118, 0.15);
            border: 1px solid #00e676;
            color: #00e676;
            font-size: 12px;
            font-weight: bold;
            padding: 8px;
            border-radius: 6px;
        """)
        layout.addWidget(self.lbl_fuse_status)

        # Métricas do RLS
        grid_metrics = QGridLayout()
        grid_metrics.setSpacing(6)

        lbl_r_target_title = QLabel("R₀ Bloco Alvo:")
        lbl_r_target_title.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        grid_metrics.addWidget(lbl_r_target_title, 0, 0)

        self.lbl_r_target = QLabel("833 µΩ")
        self.lbl_r_target.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: bold;")
        grid_metrics.addWidget(self.lbl_r_target, 0, 1)

        lbl_r_mean_title = QLabel("Média Pack (R̄):")
        lbl_r_mean_title.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        grid_metrics.addWidget(lbl_r_mean_title, 1, 0)

        self.lbl_r_mean = QLabel("833 µΩ")
        self.lbl_r_mean.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: bold;")
        grid_metrics.addWidget(self.lbl_r_mean, 1, 1)

        lbl_z_score_title = QLabel("Desvio Z-Score:")
        lbl_z_score_title.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        grid_metrics.addWidget(lbl_z_score_title, 2, 0)

        self.lbl_z_score = QLabel("0.00")
        self.lbl_z_score.setStyleSheet("color: #00e676; font-size: 11px; font-weight: bold;")
        grid_metrics.addWidget(self.lbl_z_score, 2, 1)

        layout.addLayout(grid_metrics)

    def update_view(self):
        # 1. Atualizar Módulos de Temperatura
        temps = self.state.module_temperatures
        for m in range(4):
            t = temps[m]
            self.temp_bars[m].setValue(int(max(20, min(65, t))))
            self.temp_labels[m].setText(f"{t:.1f} °C")

            if t >= 58.0:
                self.temp_labels[m].setStyleSheet("font-size: 11px; font-weight: bold; color: #ff1744;")
                self.temp_bars[m].setStyleSheet("""
                    QProgressBar { background-color: #14171c; border: 1px solid #ff1744; border-radius: 4px; }
                    QProgressBar::chunk { background-color: #ff1744; border-radius: 3px; }
                """)
            elif t >= 45.0:
                self.temp_labels[m].setStyleSheet("font-size: 11px; font-weight: bold; color: #ff9100;")
                self.temp_bars[m].setStyleSheet("""
                    QProgressBar { background-color: #14171c; border: 1px solid #ff9100; border-radius: 4px; }
                    QProgressBar::chunk { background-color: #ff9100; border-radius: 3px; }
                """)
            else:
                self.temp_labels[m].setStyleSheet("font-size: 11px; font-weight: bold; color: #00e676;")
                self.temp_bars[m].setStyleSheet("""
                    QProgressBar { background-color: #14171c; border: 1px solid #333; border-radius: 4px; }
                    QProgressBar::chunk { background-color: #00e676; border-radius: 3px; }
                """)

        # 2. Atualizar Métricas RLS
        r0 = self.state.estimated_r0_uohm
        r_mean = self.state.average_r_uohm
        z = self.state.z_score
        blown = self.state.fuse_blown
        blown_idx = self.state.blown_block_index

        self.lbl_r_target.setText(f"{r0} µΩ ({r0/1000.0:.3f} mΩ)")
        self.lbl_r_mean.setText(f"{r_mean} µΩ ({r_mean/1000.0:.3f} mΩ)")

        if z >= 3.0 or blown:
            self.lbl_z_score.setText(f"{z:.2f} (ANOMALIA DETECTADA)")
            self.lbl_z_score.setStyleSheet("color: #ff1744; font-size: 11px; font-weight: bold;")
            self.lbl_fuse_status.setText(f"⚠ FUSÍVEL ROMPIDO NO BLOCO #{blown_idx + 1} (OPERAÇÃO 17P)")
            self.lbl_fuse_status.setStyleSheet("""
                background-color: rgba(255, 23, 68, 0.25);
                border: 2px solid #ff1744;
                color: #ff1744;
                font-size: 12px;
                font-weight: bold;
                padding: 8px;
                border-radius: 6px;
            """)
        else:
            self.lbl_z_score.setText(f"{z:.2f} (Normal < 3.0)")
            self.lbl_z_score.setStyleSheet("color: #00e676; font-size: 11px; font-weight: bold;")
            self.lbl_fuse_status.setText("TODOS OS 20 BLOCOS ÍNTEGROS (18P)")
            self.lbl_fuse_status.setStyleSheet("""
                background-color: rgba(0, 230, 118, 0.15);
                border: 1px solid #00e676;
                color: #00e676;
                font-size: 12px;
                font-weight: bold;
                padding: 8px;
                border-radius: 6px;
            """)

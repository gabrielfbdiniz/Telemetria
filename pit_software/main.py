"""
main.py - Ponto de Entrada da Aplicação de Telemetria de Pista (Pit Software)
Formula ITA - Formula SAE Electric (2025-2026)
Trilha: Gabriel Diniz
"""

import sys
import os

# Garantir que a pasta pit_software esteja no sys.path
app_dir = os.path.dirname(os.path.abspath(__file__))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Telemetria Formula ITA - Pit Station")
    app.setOrganizationName("Formula ITA")

    # Tipografia de corrida limpa
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

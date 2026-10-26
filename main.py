"""
main.py - Ponto de Entrada da Aplicação de Telemetria
Formula ITA - Formula SAE Electric (2025-2026)
"""

import sys
import os

# Garantir que o diretório raiz esteja no sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Telemetria Formula ITA - BMS Master")
    app.setOrganizationName("Formula ITA")

    # Fonte limpa
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

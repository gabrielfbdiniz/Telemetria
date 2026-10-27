"""
main.py - Launcher Unificado da Telemetria Formula ITA
Formula SAE Electric (2025-2026)
Redireciona para o software de pista em pit_software/main.py
"""

import sys
import os

# Adiciona pit_software ao caminho de execução
pit_software_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pit_software")
if pit_software_dir not in sys.path:
    sys.path.insert(0, pit_software_dir)

from pit_software.main import main

if __name__ == "__main__":
    main()

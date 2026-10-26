# Telemetria - V0 — Formula ITA
Sistema de Telemetria Veicular, Enlace Sub-GHz 915 MHz (`HM-TRP-915S`), Barramento CAN (`SN65HVD230`) e Dashboard de Pista em Tempo Real para o Protótipo Formula SAE Elétrico (2025-2026).

## Estrutura do Repositório
* `config/bms_can_matrix.dbc`: Matriz CAN oficial unificada (11 mensagens do BMS Master 20s18p + mensagens de expansão de VCU e Inversor).
* `core/`: Decodificador/Codificador DBC (`CANDecoder`), gerenciador de estado thread-safe (`TelemetryState`) e emulador eletrotérmico de alta fidelidade (`VirtualBatteryEmulator`).
* `io_interfaces/`:
  * `hm_trp_serial.py`: Protocolo binário **`FITA-TELEM v1`** (15 bytes com `CRC-8` e contador de sequência `SEQ`), receptor serial assíncrono, transmissor HIL de bancada e programador de comandos hexadecimais `0xAA 0xFA` para os módulos **`HM-TRP-915S`**.
  * `can_receiver.py`: Receptor direto para adaptadores USB-CAN (`slcan`, `pcan`, `kvaser`, `socketcan`).
* `firmware_telemetry/`:
  * `node1_bms_car_emulator/`: Firmware para a **MCU #1 + `SN65HVD230 #1`** que emula fisicamente o BMS Master (G474RE), VCU e Inversor no barramento CAN a 500 kbps.
  * `node2_telemetry_gateway/`: Firmware definitivo do **Gateway de Telemetria do Carro (`MCU #2` + `SN65HVD230 #2` + `HM-TRP-915S TX`)** com decimação inteligente de taxa e bypass imediato de falhas.
* `gui/`: Interface gráfica de pista em PySide6 + PyQtGraph com 2 abas:
  * **Aba 1 (`🔋 BMS Master & Acumulador 20s18p`):** Barras das 20 células, gráficos temporais e diagnóstico RLS de fusíveis/temperaturas.
  * **Aba 2 (`📡 Link RF HM-TRP-915S, Inspetor CAN & Sensores do Carro`):** Saúde do link 915 MHz (CRC, Packet Loss %, kbps), programador HM-TRP, Sniffer CAN hexadecimal ao vivo e telemetria de pedais/motor/inversor.
* `docs/GUIA_ARQUITETURA_E_VALIDACAO_BANCADA.md`: Manual completo de pinagem e validação passo a passo com os módulos `SN65HVD230` e `HM-TRP-915S`.

## Como Executar
1. Dê um duplo clique em `run.bat` (ou execute `python main.py`).
2. Para rodar os testes automatizados:
   ```powershell
   python -m unittest discover -s tests -v
   ```

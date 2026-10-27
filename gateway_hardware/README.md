# Gateway Hardware — Telemetria Embarcada
**Formula ITA — Formula SAE Electric (2025-2026)**
**Responsável:** Iago

## Objetivo da Placa
Projetar uma PCB compacta para ser instalada no chassi do veículo contendo:
1. Microcontrolador de processamento (ex: ESP32-WROOM-32E ou STM32).
2. Transceptor CAN 3.3V com proteção automotiva (TVS ESD nos pinos `CAN_H` e `CAN_L`, resistor de terminação de $120\ \Omega$ selecionável por jumper).
3. Conector Molex Micro-Fit para alimentação 12V da linha GLV (com regulador buck para 3.3V / 500mA com proteção ISO 7637-2).
4. Soquete / footprint para montagem do módulo de rádio Sub-GHz **`HM-TRP-915S`** com conector de antena SMA fêmea de 50 $\Omega$.
5. LEDs indicadores de status:
   * LED Verde: Alimentação 3.3V OK.
   * LED Laranja: Atividade no barramento CAN (RX).
   * LED Azul: Transmissão no rádio RF (TX).

## Estrutura desta Pasta
* `kicad/`: Projeto mestre no KiCad 10 (esquemático `.kicad_sch`, layout `.kicad_pcb` e BOM).

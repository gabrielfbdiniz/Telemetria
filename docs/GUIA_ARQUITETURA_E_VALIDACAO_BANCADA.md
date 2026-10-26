# Guia Completo de Arquitetura, Pinagem e Validação de Bancada (SN65HVD230 + HM-TRP-915S)
**Formula ITA — Formula SAE Electric (Temporada 2025-2026)**

Este documento detalha passo a passo como montar, configurar e validar todo o sistema de telemetria usando os **módulos CAN `SN65HVD230`** e o **par de rádios Sub-GHz `HM-TRP-915S`**, permitindo validar 100% da cadeia física de dados **antes mesmo de o BMS Master (Nucleo-G474RE) estar fabricado**.

---

## 1. Visão Geral das Conexões Físicas

### 1.1 Pinagem do Módulo Transceptor CAN `SN65HVD230`
O `SN65HVD230` converte os sinais lógicos `CTX` (TX) e `CRX` (RX) de um microcontrolador de **3.3V** (ESP32 ou STM32) no par diferencial **`CAN_H` e `CAN_L`**.

| Pino no Módulo `SN65HVD230` | Onde Conectar | Observação Crítica |
| :---: | :--- | :--- |
| **`VCC` (3V3)** | Pino **`3.3V`** da MCU | **NUNCA ligue em 5V!** O `SN65HVD230` é estritamente 3.3V. |
| **`GND`** | Pino **`GND`** da MCU | Referência comum do circuito. |
| **`CTX` (ou `TXD`)** | Pino **`CAN_TX`** da MCU (No ESP32: `GPIO 5`) | Entrada de transmissão do transceptor. |
| **`CRX` (ou `RXD`)** | Pino **`CAN_RX`** da MCU (No ESP32: `GPIO 4`) | Saída de recepção do transceptor. |
| **`RS`** | Ligar ao **`GND`** (ou manter jumper de fábrica) | Em `GND` ativa o **High-Speed Mode (até 1 Mbps)**. |
| **`CAN_H`** | Fio **`CAN_H`** do par trançado (ligado ao `CAN_H` do outro módulo) | Deve haver um resistor de **$120\ \Omega$** entre `CAN_H` e `CAN_L` em cada ponta do cabo. (As plaquinhas de desenvolvimento `SN65HVD230` geralmente já vêm com um resistor SMD `121` = $120\ \Omega$ soldado na placa!). |
| **`CAN_L`** | Fio **`CAN_L`** do par trançado (ligado ao `CAN_L` do outro módulo) | Par diferencial com `CAN_H`. |

---

### 1.2 Pinagem do Módulo de Rádio 915 MHz `HM-TRP-915S`
O `HM-TRP-915S` (HopeRF) é um transceptor FSK de **915 MHz** com potência de até **+20 dBm (100 mW)** que funciona como uma ponte serial transparente (UART 3.3V).

| Pino no `HM-TRP-915S` | No Carro / Nó 2 (MCU Gateway) | No Notebook da Pista (Adaptador USB-TTL) | Função |
| :---: | :--- | :--- | :--- |
| **`VCC`** | **`3.3V`** (+ Capacitor $\ge 10\ \mu\text{F}$) | **`3.3V`** do USB-TTL (+ Capacitor $\ge 10\ \mu\text{F}$) | Alimentação (`2.4V` a `3.6V`). Consome picos de `140 mA` no TX! |
| **`GND`** | **`GND`** | **`GND`** | Terra comum. |
| **`DRX` (ou `RXD`)** | Pino **`UART2_TX` (`GPIO 17`)** da MCU | Pino **`TXD`** do conversor USB-TTL | Entrada de dados seriais que serão transmitidos pelo ar em 915 MHz. |
| **`DTX` (ou `TXD`)** | Pino **`UART2_RX` (`GPIO 16`)** da MCU | Pino **`RXD`** do conversor USB-TTL | Saída de dados seriais recebidos pelo ar em 915 MHz. |
| **`ENABLE`** | Ligar no **`GND` (LOW)** | Ligar no **`GND` (LOW)** | Em `GND` mantém o rádio ligado. Se for para `3.3V`, entra em *Sleep*. |
| **`CONFIG`** | **Desconectado (Flutuante / `3.3V`)** | **Desconectado** em operação normal (`GND` apenas para configurar!) | Em `HIGH`/Flutuante transmite dados; em `GND` aceita comandos `0xAA 0xFA` a `9600 bps`. |
| **`ANT`** | Antena 915 MHz (SMA ou fio rígido de **$7{,}8\text{ cm}$**) | Antena 915 MHz (SMA ou fio rígido de **$7{,}8\text{ cm}$**) | **Nunca transmita por longo tempo sem antena soldada/conectada!** |

> **Dica de Ouro para a Antena de Bancada:** Se os seus módulos `HM-TRP-915S` ainda não estiverem com conector SMA soldado, solde um pedaço reto de fio rígido (22 AWG) com exatos **$7{,}8\text{ cm}$ de comprimento** no pad `ANT` ($\lambda / 4$ para $915\text{ MHz}$).

---

## 2. Roteiro de Validação Progressiva na Bancada

### Passo 1: Validar os 2 Módulos `HM-TRP-915S` Direto no Notebook (Modo Loopback HIL)
Antes mesmo de ligar os microcontroladores, você pode validar o enlace de rádio 915 MHz:
1. Conecte o **`HM-TRP-915S #1`** a um conversor USB-TTL (ex: `COM4`) e o **`HM-TRP-915S #2`** a outro conversor USB-TTL (ex: `COM3`) no notebook. (Ambos com `ENABLE = GND` e `CONFIG` desconectado).
2. Abra o software `Telemetria - V0` (`run.bat` ou `python main.py`).
3. Na barra superior:
   * Selecione `Rádio 915MHz (HM-TRP Serial)`, escolha a porta do receptor (`COM3`), o Baudrate (`57600` ou `9600` se os módulos ainda estiverem no padrão de fábrica) e clique em **`📡 Conectar Hardware`**.
   * Clique no botão **`📤 HIL TX Serial`** e escolha a porta do transmissor (`COM4`).
4. **O que acontece:** O `VirtualBatteryEmulator` do Python passa a codificar as 13 mensagens CAN do DBC em pacotes binários de 15 bytes (`FITA-TELEM v1`), envia pela `COM4` para o `HM-TRP #1`, o sinal viaja em **915 MHz** pelo ar até o `HM-TRP #2` na `COM3`, e o dashboard plota tudo ao vivo!
5. Vá na **Aba 2 (`📡 Link RF, Inspetor CAN & Sensores do Carro`)** para ver a **Taxa de Perda de Pacotes (%)**, **Erros de CRC-8** e a tabela de mensagens CAN.

### Passo 2: Montar o Barramento CAN Físico Real com os Módulos `SN65HVD230` + Rádios `HM-TRP-915S`
Agora vamos validar toda a cadeia embarcada exatamente como funcionará no carro:
1. **Grave o Nó 1 (`firmware_telemetry/node1_bms_car_emulator/node1_bms_car_emulator.ino`)** na **MCU #1** conectada ao **`SN65HVD230 #1`**.
   * Este Nó 1 faz o papel do **BMS Master (G474RE) + VCU + Inversor**, injetando os frames CAN reais a 500 kbps no cabo `CAN_H` / `CAN_L`.
2. **Grave o Nó 2 (`firmware_telemetry/node2_telemetry_gateway/node2_telemetry_gateway.ino`)** na **MCU #2** conectada ao **`SN65HVD230 #2`** e ao **`HM-TRP-915S #1 (TX)`**.
   * Este Nó 2 é o **Gateway de Telemetria Embarcada oficial do carro**.
3. Interligue `CAN_H` do `SN65HVD230 #1` ao `CAN_H` do `SN65HVD230 #2`, e `CAN_L` ao `CAN_L` (e `GND` comum entre as placas na bancada).
4. Deixe apenas o **`HM-TRP-915S #2 (RX)`** plugado no notebook via USB-TTL e conecte no software `Telemetria - V0`.
5. **Teste de Injeção de Falha em Malha Fechada:**
   * Abra o Serial Monitor na MCU #1 (ou envie pelo terminal) a tecla **`f`** (Queima de Fusível RLS no Bloco 7), **`u`** (Subtensão < 2.80V), **`t`** (Sobretemperatura > 60°C) e **`r`** (Restaurar `DRIVE`).
   * Observe a falha atravessar fisicamente o transceptor `SN65HVD230 #1` $\to$ Cabo `CAN_H`/`CAN_L` $\to$ `SN65HVD230 #2` $\to$ MCU #2 $\to$ `HM-TRP-915S #1` (915 MHz) $\to$ `HM-TRP-915S #2` $\to$ Dashboard do Notebook em menos de 40 ms!

---

## 3. Como Adicionar os Próximos Sensores do Carro no Futuro
O protocolo `FITA-TELEM v1` transporta qualquer mensagem CAN de 8 bytes de forma transparente:
1. Adicione a nova mensagem e seus sinais no arquivo [`config/bms_can_matrix.dbc`](../config/bms_can_matrix.dbc).
2. A **MCU #2 (Gateway)** já encaminha automaticamente qualquer novo `CAN_ID` que aparecer no barramento `SN65HVD230` (e ele aparecerá imediatamente na tabela do **Inspetor de Barramento CAN** na Aba 2 do software!).
3. Mapeie os sinais decodificados em [`core/telemetry_state.py`](../core/telemetry_state.py) para criar novos gráficos ou indicadores dedicados.

# Telemetria — Formula ITA (2025-2026)
### Sistema de Telemetria Veicular, Gateway CAN-RF e Dashboard de Pista para Protótipo Formula SAE Electric

Repositório unificado de telemetria da equipe **Formula ITA**. Este repositório foi estruturado para suportar o desenvolvimento modular em duas trilhas paralelas:

* **Trilha 1 (Gabriel Diniz):** Software de Pista (`pit_software/`), Interface Gráfica HUD, decodificação da telemetria do BMS Master (20s18p), diagnóstico térmico e RLS de fusíveis.
* **Trilha 2 (Iago):** Gateway de Telemetria Embarcada (`gateway_firmware/` e `gateway_hardware/`), integração dos demais sensores veiculares (Pedais APPS 1/2, Freio BSE, Velocidade, RPM e Inversor).

---

## 📁 Estrutura do Repositório

```text
Telemetria/
├── docs/                               <-- Documentação de engenharia e manuais
│   ├── ARQUITETURA_DE_INTEGRACAO.md   <-- [LEITURA OBRIGATÓRIA] Guia mestre e checklist de bancada
│   └── GUIA_ARQUITETURA_E_VALIDACAO_BANCADA.md <-- Pinagem e ligações de rádio e CAN
│
├── config/                             <-- Contrato oficial de barramento do carro
│   └── vehicle_can_matrix.dbc         <-- Matriz CAN Oficial (11 msgs BMS + msgs VCU/Inversor)
│
├── pit_software/                       <-- [Área de Trabalho: Gabriel Diniz]
│   ├── core/                          <-- Decodificador DBC e gerenciamento de estado thread-safe
│   ├── io_interfaces/                 <-- Drivers de rádio RF HM-TRP-915S e USB-CAN
│   ├── gui/                           <-- Interface gráfica 60 FPS (Chassi HUD & Pack Térmico)
│   ├── simulator/                     <-- Emulador virtual de ciclo de corrida FSAE
│   ├── tests/                         <-- Testes automatizados com unittest
│   ├── main.py                        <-- Ponto de entrada da estação de pista
│   └── requirements.txt               <-- Dependências Python (PySide6, pyqtgraph, cantools, pyserial)
│
├── gateway_firmware/                   <-- [Área de Trabalho: Iago]
│   ├── src/main.cpp                   <-- Firmware C++ do Gateway (CAN 500k -> Decimação -> RF 915MHz)
│   ├── include/protocol.h             <-- Protocolo binário FITA-TELEM v1 (15 bytes + CRC8)
│   ├── include/decimation.h           <-- Regras de filtro de taxa de transmissão
│   └── platformio.ini                 <-- Configuração de compilação da MCU (ESP32 / STM32)
│
├── gateway_hardware/                   <-- [Área de Trabalho: Iago]
│   ├── kicad/                         <-- Projeto eletrônico da PCB embarcada no KiCad
│   └── README.md                      <-- Especificação técnica de componentes e conectores
│
├── run.bat                             <-- Executável de 1 clique para Windows
├── main.py                             <-- Launcher unificado
└── .gitignore                          <-- Proteção contra arquivos temporários e logs
```

---

## 🚀 Como Executar o Software de Pista (Pit Software)

1. **Instalar dependências (apenas na primeira vez):**
   ```powershell
   pip install -r pit_software/requirements.txt
   ```

2. **Iniciar o dashboard:**
   * Dê um duplo clique no arquivo `run.bat` (ou execute `python main.py` no terminal).
   * O software iniciará automaticamente no **Modo Simulação Virtual**, permitindo testar toda a interface mesmo sem nenhum rádio ou hardware conectado.

3. **Executar os testes automatizados:**
   ```powershell
   python -m unittest discover -s pit_software/tests -v
   ```

---

## 📖 Documentação de Referência
Antes de iniciar os testes com placas reais, leia com atenção:
* [**Arquitetura de Integração & Checklist de Bancada**](docs/ARQUITETURA_DE_INTEGRACAO.md) — Roteiro de comissionamento passo a passo quando chegarem as placas do BMS Master (NUCLEO-G474RE) e BMS 5S Slaves.
* [**Guia de Pinagem e Conexões**](docs/GUIA_ARQUITETURA_E_VALIDACAO_BANCADA.md) — Diagrama de ligação elétrica dos módulos `SN65HVD230` e `HM-TRP-915S`.

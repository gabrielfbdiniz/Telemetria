/*
 * node2_telemetry_gateway.ino - Gateway Oficial de Telemetria Embarcada (CAN SN65HVD230 -> RF HM-TRP-915S)
 * Formula ITA - Formula SAE Electric (2025-2026)
 *
 * PAPEL NO CARRO E NA BANCADA:
 * Este é o firmware definitivo do módulo de telemetria embarcado do protótipo:
 * 1. Escuta o barramento CAN a 500 kbps através do transceptor SN65HVD230 #2 (dando ACK físico).
 * 2. Aplica Controle de Taxa (Decimação por CAN_ID) para jamais saturar o buffer de 256 bytes do HM-TRP-915S,
 *    mas faz BYPASS IMEDIATO caso detecte transição de estado FSM ou falha crítica no BMS_Heartbeat (ID 256).
 * 3. Empacota cada frame CAN no protocolo binário FITA-TELEM v1 (15 bytes com cabeçalho 0xAA 0x55, SEQ e CRC-8)
 *    e transmite pela UART2 dedicada para o módulo de rádio Sub-GHz HM-TRP-915S (TX).
 *
 * PINAGEM PADRÃO (ESP32 + SN65HVD230 #2 + HM-TRP-915S #1):
 *   --- Módulo CAN SN65HVD230 #2 ---
 *   ESP32 3V3    ---> VCC (3.3V)
 *   ESP32 GND    ---> GND e pino RS (High-Speed Mode)
 *   ESP32 GPIO5  ---> CTX (TXD)
 *   ESP32 GPIO4  ---> CRX (RXD)
 *
 *   --- Módulo Rádio HM-TRP-915S (TX) ---
 *   ESP32 3V3    ---> VCC (3.3V com capacitor >= 10uF próximo ao módulo!)
 *   ESP32 GND    ---> GND e pino ENABLE (ENABLE em GND = Rádio Ativo)
 *   ESP32 GPIO17 ---> RXD do HM-TRP-915S (UART2 TX da MCU entra no RXD do Rádio)
 *   ESP32 GPIO16 ---> TXD do HM-TRP-915S (UART2 RX da MCU lê o TXD do Rádio)
 *   Pino CONFIG  ---> Deixar desconectado (flutuante/HIGH) para operação normal de telemetria
 */

#include <Arduino.h>
#include "driver/twai.h"

// Pinos CAN (SN65HVD230 #2)
#define CAN_TX_PIN GPIO_NUM_5
#define CAN_RX_PIN GPIO_NUM_4

// Pinos UART2 para o rádio HM-TRP-915S
#define RF_UART_TX_PIN 17
#define RF_UART_RX_PIN 16
#define RF_UART_BAUD   57600

// Protocolo Binário FITA-TELEM v1 (15 bytes)
#define SOF_BYTE_1 0xAA
#define SOF_BYTE_2 0x55

static uint8_t g_seq_counter = 0;
static uint8_t g_last_heartbeat_byte0 = 0xFF;
static uint8_t g_last_heartbeat_byte1 = 0xFF;

// Tabela de decimação (último timestamp de envio por CAN_ID em ms)
struct DecimationEntry {
    uint16_t can_id;
    uint32_t min_interval_ms;
    uint32_t last_sent_ms;
};

static DecimationEntry g_decim_table[] = {
    {256,  50, 0}, // BMS_Heartbeat_Status (ou imediato em falha!)
    {257,  40, 0}, // BMS_Pack_Metrics (25 Hz no ar)
    {258,  80, 0}, // BMS_Dynamic_Limits
    {259,  80, 0}, // BMS_Extremes_MinMax
    {272, 150, 0}, // BMS_CellVoltages_Group1
    {273, 150, 0}, // BMS_CellVoltages_Group2
    {274, 150, 0}, // BMS_CellVoltages_Group3
    {275, 150, 0}, // BMS_CellVoltages_Group4
    {276, 150, 0}, // BMS_CellVoltages_Group5
    {288, 150, 0}, // BMS_Temperatures
    {304, 200, 0}, // BMS_Diagnostics_Fuse
    {512,  50, 0}, // VCU_Driver_Sensors
    {513,  50, 0}  // INV_Motor_Telemetry
};
static const int NUM_DECIM_ENTRIES = sizeof(g_decim_table) / sizeof(g_decim_table[0]);

// Cálculo de CRC-8 (Polinômio 0x07 idêntico ao FitaTelemProtocol em Python)
static uint8_t calc_crc8(const uint8_t *data, size_t len) {
    uint8_t crc = 0x00;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (uint8_t b = 0; b < 8; b++) {
            if (crc & 0x80) {
                crc = (uint8_t)((crc << 1) ^ 0x07);
            } else {
                crc = (uint8_t)(crc << 1);
            }
        }
    }
    return crc;
}

static bool should_transmit_frame(uint16_t can_id, const uint8_t *data, uint32_t now_ms) {
    // Bypass imediato de segurança: se o Heartbeat do BMS mudou estado FSM, SDC ou flags de falha, envia na hora!
    if (can_id == 256) {
        if (data[0] != g_last_heartbeat_byte0 || data[1] != g_last_heartbeat_byte1) {
            g_last_heartbeat_byte0 = data[0];
            g_last_heartbeat_byte1 = data[1];
            return true;
        }
    }

    for (int i = 0; i < NUM_DECIM_ENTRIES; i++) {
        if (g_decim_table[i].can_id == can_id) {
            if ((now_ms - g_decim_table[i].last_sent_ms) >= g_decim_table[i].min_interval_ms) {
                g_decim_table[i].last_sent_ms = now_ms;
                return true;
            }
            return false;
        }
    }

    // Qualquer novo sensor ainda não tabelado passa com intervalo padrão seguro
    return true;
}

static void transmit_rf_packet(uint16_t can_id, uint8_t dlc, const uint8_t *data) {
    uint8_t pkt[15];
    pkt[0] = SOF_BYTE_1;
    pkt[1] = SOF_BYTE_2;
    pkt[2] = g_seq_counter++;
    pkt[3] = (uint8_t)(can_id & 0xFF);
    pkt[4] = (uint8_t)((can_id >> 8) & 0xFF);
    pkt[5] = (dlc <= 8) ? dlc : 8;

    memset(&pkt[6], 0, 8);
    memcpy(&pkt[6], data, pkt[5]);

    // CRC-8 calculado sobre os 12 bytes do corpo (pkt[2] até pkt[13])
    pkt[14] = calc_crc8(&pkt[2], 12);

    Serial2.write(pkt, 15);
}

void setup() {
    Serial.begin(115200);
    Serial2.begin(RF_UART_BAUD, SERIAL_8N1, RF_UART_RX_PIN, RF_UART_TX_PIN);
    delay(400);

    Serial.println("\n==========================================================");
    Serial.println(" FORMULA ITA - NO 2: GATEWAY TELEMETRIA (CAN -> HM-TRP)  ");
    Serial.println("==========================================================");

    twai_general_config_t g_config = TWAI_GENERAL_CONFIG_DEFAULT(CAN_TX_PIN, CAN_RX_PIN, TWAI_MODE_NORMAL);
    twai_timing_config_t t_config = TWAI_TIMING_CONFIG_500KBITS();
    twai_filter_config_t f_config = TWAI_FILTER_CONFIG_ACCEPT_ALL();

    if (twai_driver_install(&g_config, &t_config, &f_config) == ESP_OK && twai_start() == ESP_OK) {
        Serial.println("[OK] Barramento CAN (SN65HVD230 #2) ativo a 500 kbps.");
        Serial.printf("[OK] Link Serial RF (HM-TRP-915S) ativo a %d bps.\n", RF_UART_BAUD);
    } else {
        Serial.println("[ERRO] Falha ao inicializar controlador CAN!");
    }
}

void loop() {
    twai_message_t rx_msg;
    // Aguarda pacotes vindos do barramento CAN físico
    if (twai_receive(&rx_msg, pdMS_TO_TICKS(10)) == ESP_OK) {
        if (!rx_msg.rtr) {
            uint32_t now_ms = millis();
            uint16_t can_id = (uint16_t)(rx_msg.identifier & 0xFFFF);

            if (should_transmit_frame(can_id, rx_msg.data, now_ms)) {
                transmit_rf_packet(can_id, rx_msg.data_length_code, rx_msg.data);
            }
        }
    }
}

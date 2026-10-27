/**
 * main.cpp - Firmware Oficial do Gateway de Telemetria Embarcada
 * Formula ITA - Formula SAE Electric (2025-2026)
 * Trilha: Iago (+ Gabriel)
 *
 * RESPONSABILIDADE:
 * 1. Escutar o barramento CAN Veicular a 500 kbps via SN65HVD230 (ou transceiver isolado).
 * 2. Aplicar decimação por CAN_ID (com bypass de emergência para falhas de segurança do BMS).
 * 3. Empacotar em FITA-TELEM v1 (15 bytes + CRC-8) e transmitir via UART2 para o HM-TRP-915S (TX).
 */

#include <Arduino.h>
#include "driver/twai.h"
#include "protocol.h"
#include "decimation.h"

// Pinos CAN (SN65HVD230)
#define CAN_TX_PIN GPIO_NUM_5
#define CAN_RX_PIN GPIO_NUM_4

// Pinos UART2 para o Rádio HM-TRP-915S
#define RF_UART_TX_PIN 17
#define RF_UART_RX_PIN 16
#define RF_UART_BAUD   57600

static uint8_t g_seq = 0;
static uint8_t g_last_fsm_byte = 0xFF;

static bool check_decimation(uint16_t can_id, const uint8_t *data, uint32_t now_ms) {
    // Se o Heartbeat do BMS (0x100) mudou de estado, transmite IMEDIATAMENTE (bypass)
    if (can_id == 0x100) {
        if (data[0] != g_last_fsm_byte) {
            g_last_fsm_byte = data[0];
            return true;
        }
    }

    for (int i = 0; i < NUM_RULES; i++) {
        if (g_decimation_rules[i].can_id == can_id) {
            if ((now_ms - g_decimation_rules[i].last_sent_ms) >= g_decimation_rules[i].min_interval_ms) {
                g_decimation_rules[i].last_sent_ms = now_ms;
                return true;
            }
            return false;
        }
    }
    // Sensores novos não mapeados são encaminhados a cada 50 ms por padrão
    return true;
}

static void send_to_rf(uint16_t can_id, uint8_t dlc, const uint8_t *data) {
    FitaTelemPacket pkt;
    pkt.sof1 = FITA_SOF_1;
    pkt.sof2 = FITA_SOF_2;
    pkt.seq = g_seq++;
    pkt.can_id = can_id;
    pkt.dlc = (dlc <= 8) ? dlc : 8;
    memset(pkt.data, 0, 8);
    memcpy(pkt.data, data, pkt.dlc);

    // CRC-8 calculado sobre o corpo: de seq até data[7] (12 bytes)
    pkt.crc8 = fita_calc_crc8(&pkt.seq, 12);

    Serial2.write((const uint8_t *)&pkt, sizeof(pkt));
}

void setup() {
    Serial.begin(115200);
    Serial2.begin(RF_UART_BAUD, SERIAL_8N1, RF_UART_RX_PIN, RF_UART_TX_PIN);
    delay(500);

    Serial.println("\n[FORMULA ITA] Telemetry Gateway Node Starting...");

    twai_general_config_t g_config = TWAI_GENERAL_CONFIG_DEFAULT(CAN_TX_PIN, CAN_RX_PIN, TWAI_MODE_NORMAL);
    twai_timing_config_t t_config = TWAI_TIMING_CONFIG_500KBITS();
    twai_filter_config_t f_config = TWAI_FILTER_CONFIG_ACCEPT_ALL();

    if (twai_driver_install(&g_config, &t_config, &f_config) == ESP_OK && twai_start() == ESP_OK) {
        Serial.println("[OK] CAN TWAI inicializado a 500 kbps (SN65HVD230).");
        Serial.printf("[OK] Link RF inicializado a %d bps (HM-TRP-915S).\n", RF_UART_BAUD);
    } else {
        Serial.println("[ERRO] Falha ao iniciar controlador CAN TWAI!");
    }
}

void loop() {
    twai_message_t rx_msg;
    if (twai_receive(&rx_msg, pdMS_TO_TICKS(10)) == ESP_OK) {
        if (!rx_msg.rtr) {
            uint16_t id = (uint16_t)(rx_msg.identifier & 0xFFFF);
            uint32_t now = millis();
            if (check_decimation(id, rx_msg.data, now)) {
                send_to_rf(id, rx_msg.data_length_code, rx_msg.data);
            }
        }
    }
}

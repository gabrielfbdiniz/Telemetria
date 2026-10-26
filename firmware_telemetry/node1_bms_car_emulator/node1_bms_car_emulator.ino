/*
 * node1_bms_car_emulator.ino - Emulador Físico em Barramento CAN do BMS Master (20s18p) + VCU + Inversor
 * Formula ITA - Formula SAE Electric (2025-2026)
 *
 * PAPEL NA BANCADA:
 * Substitui fisicamente a placa do BMS Master (STM32 Nucleo-G474RE), a VCU e o Inversor
 * enquanto o carro não está pronto. Injeta os 13 frames oficiais do arquivo `bms_can_matrix.dbc`
 * a 500 kbps no barramento físico CAN_H / CAN_L através do Módulo CAN #1 (SN65HVD230).
 *
 * PINAGEM PADRÃO (ESP32 + SN65HVD230 #1):
 *   ESP32 3V3   ---> VCC do SN65HVD230 #1  (ATENÇÃO: Usar sempre 3.3V!)
 *   ESP32 GND   ---> GND e pino RS do SN65HVD230 #1 (RS em GND = High-Speed Mode)
 *   ESP32 GPIO5 ---> CTX (TXD) do SN65HVD230 #1
 *   ESP32 GPIO4 ---> CRX (RXD) do SN65HVD230 #1
 *   CAN_H / CAN_L ---> Ligados ao CAN_H / CAN_L do Módulo CAN #2 (Nó 2 Gateway) com resistor 120 Ohm
 *
 * COMANDOS INTERATIVOS VIA USB SERIAL (115200 bps):
 *   'f' -> Queimar Fusível do Bloco #6 (Eleva R0 de 833 para 882 uOhm e dispara alerta RLS Z-Score)
 *   'u' -> Injetar Subtensão Crítica (< 2.80 V na célula #3 -> Abre SDC e vai para FAULT)
 *   't' -> Injetar Sobretemperatura (> 60 °C no módulo #3 -> Abre SDC e vai para FAULT)
 *   'r' -> Restaurar Operação Normal (Estado DRIVE, SDC Armado, AIRs Fechados)
 */

#include <Arduino.h>
#include "driver/twai.h"
#include <math.h>

// Pinos conectados ao módulo transceptor CAN SN65HVD230 #1
#define CAN_TX_PIN GPIO_NUM_5
#define CAN_RX_PIN GPIO_NUM_4

// Estado Eletroquímico Simulado do Pack 20s18p
static float g_soc_pct = 92.5f;
static float g_sim_time = 0.0f;
static uint8_t g_fsm_state = 3;      // 3 = DRIVE, 5 = FAULT
static uint8_t g_sdc_armed = 1;
static uint8_t g_air_plus = 1;
static uint8_t g_air_minus = 1;
static uint8_t g_rolling_counter = 0;

static uint16_t g_r0_blocks[20] = {
    831, 835, 829, 834, 838, 832, 833, 830, 836, 831,
    834, 828, 837, 833, 832, 835, 830, 834, 831, 833
};
static float g_temps[4] = {28.2f, 28.6f, 29.1f, 28.4f};

// Flags de Injeção de Falhas
static bool g_fault_fuse = false;
static bool g_fault_uv = false;
static bool g_fault_ot = false;

static uint32_t g_tx_ok_count = 0;
static uint32_t g_tx_err_count = 0;

static void write_u16_le(uint8_t *buf, uint16_t val) {
    buf[0] = (uint8_t)(val & 0xFF);
    buf[1] = (uint8_t)((val >> 8) & 0xFF);
}

static bool send_can_frame(uint32_t can_id, const uint8_t data[8]) {
    twai_message_t msg;
    memset(&msg, 0, sizeof(msg));
    msg.identifier = can_id;
    msg.extd = 0;
    msg.rtr = 0;
    msg.data_length_code = 8;
    memcpy(msg.data, data, 8);

    if (twai_transmit(&msg, pdMS_TO_TICKS(5)) == ESP_OK) {
        g_tx_ok_count++;
        return true;
    } else {
        g_tx_err_count++;
        return false;
    }
}

static float calc_ocv(float soc_pct) {
    float s = fmaxf(0.0f, fminf(1.0f, soc_pct / 100.0f));
    return 3.00f + 0.85f * s + 0.35f * (s * s);
}

static float calc_drive_current(float t) {
    float phase = fmodf(t, 15.0f);
    if (phase < 3.0f) {
        return 80.0f + 80.0f * sinf((phase / 3.0f) * (3.14159f / 2.0f));
    } else if (phase < 5.0f) {
        return -35.0f;
    } else if (phase < 8.0f) {
        return 30.0f + 10.0f * sinf(phase * 4.0f);
    } else if (phase < 11.0f) {
        return 60.0f + 15.0f * sinf(phase * 2.0f);
    }
    return 110.0f;
}

void setup() {
    Serial.begin(115200);
    delay(500);
    Serial.println("\n=======================================================");
    Serial.println(" FORMULA ITA - NO 1: EMULADOR FISICO CAN (SN65HVD230) ");
    Serial.println(" Comandos USB: [f]=Fusivel [u]=Subtensao [t]=Temp [r]=Reset");
    Serial.println("=======================================================");

    // Configurar controlador CAN (TWAI) a 500 kbps em modo NORMAL (espera ACK do Nó 2!)
    twai_general_config_t g_config = TWAI_GENERAL_CONFIG_DEFAULT(CAN_TX_PIN, CAN_RX_PIN, TWAI_MODE_NORMAL);
    twai_timing_config_t t_config = TWAI_TIMING_CONFIG_500KBITS();
    twai_filter_config_t f_config = TWAI_FILTER_CONFIG_ACCEPT_ALL();

    if (twai_driver_install(&g_config, &t_config, &f_config) == ESP_OK && twai_start() == ESP_OK) {
        Serial.println("[CAN] SN65HVD230 #1 Inicializado a 500 kbps (Modo NORMAL com ACK).");
    } else {
        Serial.println("[ERRO] Falha ao iniciar driver CAN TWAI!");
    }
}

void loop() {
    static uint32_t tick = 0;
    const float dt = 0.02f; // Loop a 50 Hz (20 ms)

    // 1. Ler comandos de injeção de falha via USB Serial
    while (Serial.available() > 0) {
        char cmd = (char)Serial.read();
        if (cmd == 'f' || cmd == 'F') {
            g_fault_fuse = true;
            g_r0_blocks[6] = 882; // Eleva R0 do Bloco #7 (índice 6) para 882 uOhm
            Serial.println("[FALHA INJETADA] Fusivel rompido no bloco #7 (RLS R0 = 882 uOhm)!");
        } else if (cmd == 'u' || cmd == 'U') {
            g_fault_uv = true;
            Serial.println("[FALHA INJETADA] Subtensao critica (< 2.80 V)!");
        } else if (cmd == 't' || cmd == 'T') {
            g_fault_ot = true;
            Serial.println("[FALHA INJETADA] Sobretemperatura (> 60 C)!");
        } else if (cmd == 'r' || cmd == 'R') {
            g_fault_fuse = false;
            g_fault_uv = false;
            g_fault_ot = false;
            g_fsm_state = 3; // DRIVE
            g_sdc_armed = 1;
            g_air_plus = 1;
            g_air_minus = 1;
            g_r0_blocks[6] = 833;
            g_temps[0] = 28.2f; g_temps[1] = 28.6f; g_temps[2] = 29.1f; g_temps[3] = 28.4f;
            Serial.println("[RESET] Operacao normal DRIVE restaurada.");
        }
    }

    // 2. Evoluir modelo físico da bateria 20s18p
    g_sim_time += dt;
    tick++;
    g_rolling_counter = (g_rolling_counter + 1) & 0x0F;

    float current_a = (g_fsm_state == 3) ? calc_drive_current(g_sim_time) : 0.0f;
    g_soc_pct -= (current_a * dt) / (54.0f * 3600.0f) * 100.0f;
    g_soc_pct = fmaxf(5.0f, fminf(100.0f, g_soc_pct));

    float ocv = calc_ocv(g_soc_pct);
    uint16_t cell_mv[20];
    uint16_t v_min = 5000, v_max = 0;
    uint8_t min_id = 1, max_id = 1;
    uint32_t sum_mv = 0;

    for (int i = 0; i < 20; i++) {
        float v_drop = current_a * ((float)g_r0_blocks[i] * 1e-6f);
        float v_cell = ocv - v_drop;
        if (g_fault_uv && i == 2) {
            v_cell = 2.68f;
        }
        uint16_t mv = (uint16_t)fmaxf(2000.0f, fminf(4300.0f, v_cell * 1000.0f));
        cell_mv[i] = mv;
        sum_mv += mv;
        if (mv < v_min) { v_min = mv; min_id = i + 1; }
        if (mv > v_max) { v_max = mv; max_id = i + 1; }
    }
    float pack_voltage = (float)sum_mv / 1000.0f;

    if (g_fault_ot) {
        g_temps[2] = 62.5f;
    }

    bool uv_trip = (v_min < 2800);
    bool ov_trip = (v_max > 4250);
    bool ot_trip = (g_temps[2] > 60.0f);

    if (uv_trip || ov_trip || ot_trip) {
        g_fsm_state = 5; // FAULT
        g_sdc_armed = 0;
        g_air_plus = 0;
        g_air_minus = 0;
    }

    uint8_t payload[8];

    // (A) 0x101 (257) BMS_Pack_Metrics (a cada 20 ms)
    memset(payload, 0, 8);
    write_u16_le(&payload[0], (uint16_t)roundf(pack_voltage / 0.01f));
    write_u16_le(&payload[2], (uint16_t)roundf((current_a + 500.0f) / 0.1f));
    write_u16_le(&payload[4], (uint16_t)roundf(g_soc_pct / 0.1f));
    write_u16_le(&payload[6], (uint16_t)roundf(99.2f / 0.1f));
    send_can_frame(257, payload);

    // (B) 0x100 (256), 0x102 (258), 0x103 (259), 0x200 (512), 0x201 (513) (a cada 40 ms)
    if (tick % 2 == 0) {
        // 256: BMS_Heartbeat_Status
        memset(payload, 0, 8);
        payload[0] = (g_fsm_state & 0x0F) | ((g_sdc_armed & 1) << 4) | ((g_air_plus & 1) << 5) | ((g_air_minus & 1) << 6);
        payload[1] = (uv_trip ? 1 : 0) | ((ov_trip ? 1 : 0) << 1) | ((ot_trip ? 1 : 0) << 2) |
                     (((g_sdc_armed == 0) ? 1 : 0) << 6) | ((g_fault_fuse ? 1 : 0) << 7);
        payload[2] = (g_rolling_counter & 0x0F);
        payload[3] = uv_trip ? 0x42 : (ot_trip ? 0x81 : 0x00);
        send_can_frame(256, payload);

        // 258: BMS_Dynamic_Limits
        memset(payload, 0, 8);
        float dcl = g_fault_fuse ? 235.0f : 250.0f;
        write_u16_le(&payload[0], (uint16_t)roundf(dcl / 0.1f));
        write_u16_le(&payload[2], (uint16_t)roundf(45.0f / 0.1f));
        write_u16_le(&payload[4], (uint16_t)roundf((g_air_plus ? pack_voltage : 0.0f) / 0.01f));
        payload[6] = 60;
        payload[7] = g_fault_fuse ? 1 : 0;
        send_can_frame(258, payload);

        // 259: BMS_Extremes_MinMax
        memset(payload, 0, 8);
        write_u16_le(&payload[0], v_min);
        payload[2] = (uint8_t)(min_id - 1);
        write_u16_le(&payload[3], v_max);
        payload[5] = (uint8_t)(max_id - 1);
        payload[6] = (uint8_t)roundf(g_temps[0] + 40.0f);
        payload[7] = (uint8_t)roundf(g_temps[2] + 40.0f);
        send_can_frame(259, payload);

        // 512: VCU_Driver_Sensors
        memset(payload, 0, 8);
        float apps = (current_a > 0.0f) ? fminf(100.0f, (current_a / 160.0f) * 100.0f) : 0.0f;
        float brk  = (current_a < 0.0f) ? fminf(65.0f, (-current_a / 35.0f) * 42.0f) : 0.0f;
        uint8_t spd = (g_fsm_state == 3) ? (uint8_t)(40.0f + apps * 0.6f) : 0;
        write_u16_le(&payload[0], (uint16_t)roundf(apps / 0.1f));
        write_u16_le(&payload[2], (uint16_t)roundf(apps / 0.1f));
        write_u16_le(&payload[4], (uint16_t)roundf(brk / 0.1f));
        payload[6] = spd;
        payload[7] = 1 | (((uint8_t)((0 + 120) / 2) & 0x7F) << 1);
        send_can_frame(512, payload);

        // 513: INV_Motor_Telemetry
        memset(payload, 0, 8);
        write_u16_le(&payload[0], (uint16_t)(spd * 48));
        write_u16_le(&payload[2], (uint16_t)roundf(((current_a / 160.0f) * 210.0f + 100.0f) / 0.1f));
        write_u16_le(&payload[4], (uint16_t)roundf((42.5f + 40.0f) / 0.1f));
        write_u16_le(&payload[6], (uint16_t)roundf((39.0f + 40.0f) / 0.1f));
        send_can_frame(513, payload);
    }

    // (C) Tensões das 20 Células (272..276) e Temperaturas (288) a cada 100 ms
    if (tick % 5 == 0) {
        for (int g = 0; g < 5; g++) {
            for (int c = 0; c < 4; c++) {
                write_u16_le(&payload[c * 2], cell_mv[g * 4 + c]);
            }
            send_can_frame(272 + g, payload);
        }

        for (int m = 0; m < 4; m++) {
            write_u16_le(&payload[m * 2], (uint16_t)roundf((g_temps[m] + 40.0f) / 0.1f));
        }
        send_can_frame(288, payload);
    }

    // (D) 0x130 (304) BMS_Diagnostics_Fuse a cada 200 ms
    if (tick % 10 == 0) {
        memset(payload, 0, 8);
        uint16_t r_target = g_r0_blocks[6];
        uint16_t r_mean = 833;
        float z_score = g_fault_fuse ? 4.25f : 0.15f;
        payload[0] = (g_fault_fuse ? 1 : 0) | ((6 & 0x7F) << 1);
        write_u16_le(&payload[1], r_target);
        write_u16_le(&payload[3], r_mean);
        write_u16_le(&payload[5], (uint16_t)roundf(z_score / 0.01f));
        payload[7] = 0;
        send_can_frame(304, payload);
    }

    delay(20);
}

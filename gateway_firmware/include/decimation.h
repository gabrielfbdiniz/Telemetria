#pragma once
#include <stdint.h>

/**
 * Tabela de Decimação de Taxa de Transmissão (Downsampling)
 * Garante que o barramento CAN de 500 kbps não sobrecarregue o buffer do HM-TRP-915S (57600 bps).
 */
struct DecimationRule {
    uint16_t can_id;
    uint16_t min_interval_ms;
    uint32_t last_sent_ms;
};

// IDs Oficiais do Carro (BMS 0x100..0x130, VCU 0x200, Inversor 0x201)
static DecimationRule g_decimation_rules[] = {
    {0x100,  50, 0}, // 256: BMS_Heartbeat_Status (bypass imediato em mudança de estado FSM)
    {0x101,  40, 0}, // 257: BMS_Pack_Metrics (25 Hz no ar)
    {0x102,  80, 0}, // 258: BMS_Dynamic_Limits
    {0x103,  80, 0}, // 259: BMS_Extremes_MinMax
    {0x110, 150, 0}, // 272: BMS_CellVoltages_Group1
    {0x111, 150, 0}, // 273: BMS_CellVoltages_Group2
    {0x112, 150, 0}, // 274: BMS_CellVoltages_Group3
    {0x113, 150, 0}, // 275: BMS_CellVoltages_Group4
    {0x114, 150, 0}, // 276: BMS_CellVoltages_Group5
    {0x120, 150, 0}, // 288: BMS_Temperatures
    {0x130, 200, 0}, // 304: BMS_Diagnostics_Fuse
    {0x200,  50, 0}, // 512: VCU_Driver_Sensors (Pedais APPS/BSE, Velocidade)
    {0x201,  50, 0}  // 513: INV_Motor_Telemetry (RPM, Torque, Temp Motor/IGBT)
};

static const int NUM_RULES = sizeof(g_decimation_rules) / sizeof(g_decimation_rules[0]);

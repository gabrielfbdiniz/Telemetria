#pragma once
#include <stdint.h>
#include <stddef.h>

/**
 * Protocolo Binário FITA-TELEM v1 (15 bytes por frame CAN):
 * [0..1] 0xAA 0x55 (Sync SOF)
 * [2]    SEQ (0..255)
 * [3..4] CAN_ID (Little-Endian uint16)
 * [5]    DLC (0..8)
 * [6..13] DATA[8]
 * [14]   CRC-8 (Polinômio 0x07 sobre bytes 2..13)
 */
#define FITA_SOF_1 0xAA
#define FITA_SOF_2 0x55
#define FITA_PACKET_SIZE 15

#pragma pack(push, 1)
struct FitaTelemPacket {
    uint8_t sof1;
    uint8_t sof2;
    uint8_t seq;
    uint16_t can_id;
    uint8_t dlc;
    uint8_t data[8];
    uint8_t crc8;
};
#pragma pack(pop)

static inline uint8_t fita_calc_crc8(const uint8_t *data, size_t len) {
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

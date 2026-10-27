"""
test_telemetry.py - Suite de Testes Automatizados para a Camada de Telemetria, RF (HM-TRP-915S) e CAN
Formula ITA - Formula SAE Electric (2025-2026)
"""

import unittest
import os
import sys
import time

# Inserir raiz no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.can_decoder import CANDecoder
from core.telemetry_state import TelemetryState
from simulator import VehicleSimulator as VirtualBatteryEmulator
from io_interfaces.hm_trp_serial import FitaTelemProtocol, StreamParser, HMTRPConfigTool


class TestTelemetry(unittest.TestCase):
    def setUp(self):
        self.decoder = CANDecoder()
        self.state = TelemetryState()

    def test_dbc_loading_13_messages(self):
        self.assertIsNotNone(self.decoder.db)
        self.assertEqual(len(self.decoder.db.messages), 13)
        expected_msgs = [
            "BMS_Heartbeat_Status", "BMS_Pack_Metrics", "BMS_Dynamic_Limits",
            "BMS_Extremes_MinMax", "BMS_CellVoltages_Group1", "BMS_CellVoltages_Group2",
            "BMS_CellVoltages_Group3", "BMS_CellVoltages_Group4", "BMS_CellVoltages_Group5",
            "BMS_Temperatures", "BMS_Diagnostics_Fuse",
            "VCU_Driver_Sensors", "INV_Motor_Telemetry"
        ]
        for name in expected_msgs:
            self.assertIn(name, self.decoder._msg_by_name)

    def test_encode_decode_metrics_and_vehicle_sensors(self):
        signals = {
            "BMS_Pack_Voltage": 74.25,
            "BMS_Pack_Current": 85.4,
            "BMS_Pack_SOC": 91.2,
            "BMS_Pack_SOH": 98.5
        }
        can_id, payload = self.decoder.encode("BMS_Pack_Metrics", signals)
        self.assertEqual(can_id, 257)
        self.assertEqual(len(payload), 8)

        decoded = self.decoder.decode(can_id, payload)
        self.assertAlmostEqual(decoded["BMS_Pack_Voltage"], 74.25, places=2)
        self.assertAlmostEqual(decoded["BMS_Pack_Current"], 85.4, places=1)
        self.assertAlmostEqual(decoded["BMS_Pack_SOC"], 91.2, places=1)
        self.assertAlmostEqual(decoded["BMS_Pack_SOH"], 98.5, places=1)

        # Testar VCU_Driver_Sensors (0x200 = 512)
        vcu_sig = {
            "VCU_APPS1_Pct": 76.5,
            "VCU_APPS2_Pct": 76.2,
            "VCU_Brake_Pressure_Bar": 12.4,
            "VCU_Vehicle_Speed_Kmh": 84,
            "VCU_APPS_BSE_Plausible": 1,
            "VCU_Steering_Angle_Deg": -14
        }
        vcu_id, vcu_data = self.decoder.encode("VCU_Driver_Sensors", vcu_sig)
        self.assertEqual(vcu_id, 512)
        vcu_dec = self.decoder.decode(vcu_id, vcu_data)
        self.state.update_from_decoded_frame("VCU_Driver_Sensors", vcu_dec)
        self.assertAlmostEqual(self.state.apps1_pct, 76.5, places=1)
        self.assertEqual(self.state.vehicle_speed_kmh, 84.0)
        self.assertEqual(self.state.steering_angle_deg, -14.0)

    def test_fita_telem_protocol_and_stream_parser_noise_resilience(self):
        parser = StreamParser()
        _, payload1 = self.decoder.encode("BMS_Pack_Metrics", {
            "BMS_Pack_Voltage": 72.0,
            "BMS_Pack_Current": 50.0,
            "BMS_Pack_SOC": 90.0,
            "BMS_Pack_SOH": 99.0
        })
        pkt1 = FitaTelemProtocol.encode_can_frame(seq=10, can_id=257, data=payload1)
        self.assertEqual(len(pkt1), 15)

        # Pacote corrompido (alterando 1 bit do payload)
        pkt_corrupt = bytearray(FitaTelemProtocol.encode_can_frame(seq=11, can_id=257, data=payload1))
        pkt_corrupt[8] ^= 0xFF

        # Pacote seguinte com SEQ=13 (simulando que o SEQ=11 corrompeu e o SEQ=12 se perdeu no ar = 2 pacotes perdidos)
        pkt3 = FitaTelemProtocol.encode_can_frame(seq=13, can_id=257, data=payload1)

        # Stream com lixo antes, entre e depois dos pacotes
        noisy_stream = b"\x00\xFF\xAA\x12" + pkt1 + bytes(pkt_corrupt) + b"\x99\x88" + pkt3
        extracted = parser.feed(noisy_stream)

        self.assertEqual(len(extracted), 2)
        self.assertEqual(extracted[0][0], 10)
        self.assertEqual(extracted[0][1], 257)
        self.assertEqual(extracted[0][2], payload1)
        self.assertEqual(extracted[1][0], 13)

        self.assertEqual(parser.packets_ok, 2)
        self.assertGreaterEqual(parser.crc_errors, 1)
        self.assertEqual(parser.packets_lost, 2)  # Faltaram SEQ 11 e 12

    def test_hmtrp_config_commands(self):
        self.assertEqual(HMTRPConfigTool.cmd_reset_factory(), b"\xAA\xFA\xF0")
        self.assertEqual(HMTRPConfigTool.cmd_read_parameters(), b"\xAA\xFA\xE1")
        # 915.000.000 Hz = 0x3689CAC0
        self.assertEqual(HMTRPConfigTool.cmd_set_frequency(915_000_000), b"\xAA\xFA\xD2\x36\x89\xCA\xC0")
        # Potência máxima nível 7 (+20 dBm)
        self.assertEqual(HMTRPConfigTool.cmd_set_tx_power(7), b"\xAA\xFA\x96\x07")

    def test_state_update_fuse_diagnostic(self):
        signals = {
            "BMS_Fuse_Blown_Detected": 1,
            "BMS_Blown_Block_Index": 6,
            "BMS_Estimated_R0_uOhm": 882,
            "BMS_Average_R_uOhm": 833,
            "BMS_Z_Score": 4.15,
            "BMS_Fuse_Diag_Reserved": 0
        }
        self.state.update_from_decoded_frame("BMS_Diagnostics_Fuse", signals)
        self.assertTrue(self.state.fuse_blown)
        self.assertEqual(self.state.blown_block_index, 6)
        self.assertEqual(self.state.estimated_r0_uohm, 882)
        self.assertAlmostEqual(self.state.z_score, 4.15, places=2)

    def test_virtual_emulator_and_hil_sink(self):
        emulator = VirtualBatteryEmulator(self.decoder, self.state)
        sink_frames = []
        emulator.frame_sink = lambda cid, data: sink_frames.append((cid, data))

        emulator.start()
        self.assertTrue(emulator.is_running())
        time.sleep(0.22)  # Aguardar ~10 ciclos para emitir todos os grupos de mensagens
        emulator.stop()
        self.assertFalse(emulator.is_running())

        self.assertGreater(self.state.frames_received, 0)
        self.assertGreater(len(sink_frames), 0)
        self.assertIn(257, self.state.can_bus_inspector)
        self.assertIn(512, self.state.can_bus_inspector)
        self.assertIn(513, self.state.can_bus_inspector)


if __name__ == "__main__":
    unittest.main()

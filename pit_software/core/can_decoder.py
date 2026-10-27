"""
can_decoder.py - Decodificador e Codificador Universal CAN baseado no DBC Oficial
Formula ITA - Formula SAE Electric (2025-2026)
"""

import os
from typing import Dict, Any, Optional, Tuple
import cantools


class CANDecoder:
    def __init__(self, dbc_path: Optional[str] = None):
        if dbc_path is None:
            # Buscar na raiz do repositório Telemetria ou dentro do pit_software
            current_dir = os.path.dirname(os.path.abspath(__file__))
            candidates = [
                os.path.join(os.path.dirname(os.path.dirname(current_dir)), "config", "vehicle_can_matrix.dbc"),
                os.path.join(os.path.dirname(os.path.dirname(current_dir)), "config", "bms_can_matrix.dbc"),
                os.path.join(os.path.dirname(current_dir), "config", "vehicle_can_matrix.dbc"),
                os.path.join(current_dir, "vehicle_can_matrix.dbc")
            ]
            for cand in candidates:
                if os.path.isfile(cand):
                    dbc_path = cand
                    break

        if dbc_path is None or not os.path.isfile(dbc_path):
            raise FileNotFoundError(f"Arquivo DBC não encontrado em nenhum dos locais esperados: {candidates}")

        self.dbc_path = dbc_path
        self.db = cantools.database.load_file(dbc_path)
        
        # Mapeamento rápido de ID para objeto Message
        self._msg_by_id = {msg.frame_id: msg for msg in self.db.messages}
        self._msg_by_name = {msg.name: msg for msg in self.db.messages}

    def decode(self, frame_id: int, data: bytes) -> Optional[Dict[str, Any]]:
        """
        Decodifica um frame CAN recebido dado seu ID e payload em bytes.
        Retorna um dicionário com os nomes dos sinais e valores convertidos, ou None.
        """
        msg = self._msg_by_id.get(frame_id)
        if msg is None:
            return None
        
        try:
            return msg.decode(data, decode_choices=False)
        except Exception as e:
            # Caso o tamanho do payload ou dados estejam corrompidos
            return None

    def encode(self, name_or_id: Any, signals: Dict[str, Any]) -> Tuple[int, bytes]:
        """
        Codifica um dicionário de sinais em um payload CAN de 8 bytes.
        Retorna uma tupla (frame_id, payload_bytes).
        """
        if isinstance(name_or_id, int):
            msg = self._msg_by_id.get(name_or_id)
        else:
            msg = self._msg_by_name.get(name_or_id)

        if msg is None:
            raise KeyError(f"Mensagem não cadastrada no DBC: {name_or_id}")

        data = msg.encode(signals)
        return msg.frame_id, data

    def get_message_name(self, frame_id: int) -> Optional[str]:
        msg = self._msg_by_id.get(frame_id)
        return msg.name if msg else None

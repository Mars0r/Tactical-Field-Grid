# =============================================================================
# MÓDULO DE GENERACIÓN CoT (Cursor-on-Target)
# 
# Este archivo contiene lógica derivada y adaptada del proyecto:
# "rns-atak-bridge" por sansscott (https://github.com/sansscott/rns-atak-bridge)
# 
# El proyecto original se distribuye bajo la Licencia MIT.
# =============================================================================

import struct
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET
from printer import imprimir

class CotHandler:
    def __init__(self, callsign_prefix="TFG-", stale_minutes=5):
        self.prefix = callsign_prefix
        self.stale_minutes = stale_minutes
        self.dt_fmt = "%Y-%m-%dT%H:%M:%S.%fZ"

    def _get_time_str(self, dt):
        return dt.strftime(self.dt_fmt)

    def push_to_cot(self, soldier_id, lat, lon, hops=0, interface="LoRa"):
        #imprimir.debug(f"Generando CoT para Soldier-{soldier_id} | Lat: {lat}, Lon: {lon}, Hops: {hops}, Interface: {interface}")
        """
        Convierte datos de TFG a un evento XML de ATAK (CoT).
        """
        now = datetime.now(timezone.utc)
        stale = now + timedelta(minutes=self.stale_minutes)
        uid = f"{self.prefix}{soldier_id}"

        # Nodo raíz <event>
        event = ET.Element("event", {
            "version": "2.0",
            "uid": uid,
            "type": "a-f-G-U-C", # Icono azul (aliado) de infantería
            "time": self._get_time_str(now),
            "start": self._get_time_str(now),
            "stale": self._get_time_str(stale),
            "how": "m-g"
        })

        # <point> - Ubicación
        ET.SubElement(event, "point", {
            "lat": f"{lat:.6f}",
            "lon": f"{lon:.6f}",
            "hae": "0", # Altitud (si no tienes GPS real, dejamos 100m)
            "ce": "10",  # Error circular (m)
            "le": "10"   # Error lineal (m)
        })

        # <detail> - Metadatos para el panel de ATAK
        detail = ET.SubElement(event, "detail")
        ET.SubElement(detail, "contact", {"callsign": uid})
        
        remarks = ET.SubElement(detail, "remarks")
        remarks.text = f"T.F.G. Node | Hops: {hops} | Interface: {interface}"

        # Color de equipo (Azul)
        ET.SubElement(detail, "__group", {"name": "Blue", "role": "Team Member"})

        # Retornamos el string XML listo para enviar por UDP
        return ET.tostring(event, encoding='utf-8')
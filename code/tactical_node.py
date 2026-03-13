import os
import RNS
import re
import threading
import time
import struct
import random
import queue
import socket
import datetime
from cot_handler import CotHandler
from printer import imprimir

class TAKControl:
    def __init__(self):
        imprimir.system("[TAK] Controlador de TAK inicializado.")
        self.id_soldado = None
        self.ATAK_MCAST_GRP = '127.0.0.1' # UDP Bradcast
        self.ATAK_MCAST_PORT = 6969
        self.ATAK_CHAT_IP = '224.10.10.1'
        self.ATAK_CHAT_PORT = 17013

        
    def gps_a_atak(self,id_soldado, lat, lon):
        #imprimir.debug(f"Preparando CoT para Soldier-{id_soldado} con Lat: {lat}, Lon: {lon}")
        cot_xml = self.cot_manager.push_to_cot(id_soldado, lat, lon)

        self.broadcast_udp(cot_xml)

    def inyectar_chat_en_atak(self,id_remoto, texto):
        # 1. Usar UTC real (imprescindible para TAK)
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # 2. Sumar 10 minutos de forma segura (gestiona cambios de hora/día automáticamente)
        stale = now + datetime.timedelta(minutes=10)

        # 3. Formatear strings
        time_str = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        stale_str = stale.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        
        callsign = f"ALPHA-{id_remoto:02d}"
        # UID específico para que el mensaje no se "pise" con otros
        # El formato GeoChat.UID.Callsign.Tiempo es el estándar
        event_uid = f"GeoChat.SOLDIER-{id_remoto}.{callsign}.{now.timestamp()}"
        soldier_uid = f"SOLDIER-{id_remoto}"

        # XML de Chat optimizado para ATAK/WinTAK
        chat_xml = f"""<?xml version='1.0' standalone='yes'?>
        <event version="2.0" uid="{event_uid}" type="b-t-f" time="{time_str}" start="{time_str}" stale="{stale_str}" how="m-g">
            <point lat="0.0" lon="0.0" hae="0.0" ce="999999" le="999999"/>
            <detail>
                <__chat parent="RootContactGroup" groupName="All Staff" chatId="All Staff" senderCallsign="{callsign}" message="{texto}">
                    <chatgrp uid0="Team-Blue" uid1="{soldier_uid}"/>
                </__chat>
                <link uid="{soldier_uid}" type="a-f-G-U-C" relation="p-p"/>
                <remarks>{texto}</remarks>
                <contact callsign="{callsign}"/>
            </detail>
        </event>"""

        imprimir.tak(f"Inyectando chat de {callsign}: {texto}")
        self.broadcast_udp(chat_xml) # La función que ya tienes para enviar a 127.0.0.1:6969

    def broadcast_udp(self, xml_mssg):  
        # Simple UDP Unicast a localhost (WinTAK lo recibirá igual si escucha en el 6969)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.sendto(xml_mssg, (self.ATAK_MCAST_GRP, self.ATAK_MCAST_PORT))
            #self.imprimir.system(f"Inyectado en ATAK: {xml_mssg[:100]}...") # Log parcial para no saturar
        
        except Exception as e:
            imprimir.error(f" ERROR UDP {e}")

        #3. Pequeña pausa para no quemar la CPU
        time.sleep(0.05)

    def escuchar_wintak(self):

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        
        # Permitir que varios programas (como WinTAK y tu script) usen el puerto
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('0.0.0.0', self.ATAK_CHAT_PORT))

        # --- LA MAGIA DEL MULTICAST PARA WINDOWS ---
        # Le decimos a la tarjeta de red: "Por favor, déjame pasar los paquetes de la 224.10.10.1"
        mreq = struct.pack("4sl", socket.inet_aton(self.ATAK_CHAT_IP), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        # -------------------------------------------

        imprimir.system(f"Escuchando MULTICAST en {self.ATAK_CHAT_IP}:{self.ATAK_CHAT_PORT}...")
        
        while True:
            try:
                data, addr = sock.recvfrom(4096)
                
                # errors='ignore' es vital aquí para no crashear con la cabecera binaria 'eM<HY...'
                raw_data = data.decode('utf-8', errors='ignore')
                
                # Buscamos si es un mensaje de chat con <remarks>
                if '<remarks' in raw_data and 'b-t-f' in raw_data:
                    # Usamos regex para extraer el mensaje limpio, ignorando la basura del principio
                    match_msg = re.search(r'<remarks.*?>(.*?)</remarks>', raw_data)
                    match_sender = re.search(r'senderCallsign="(.*?)"', raw_data)
                    
                    if match_msg:
                        mensaje = match_msg.group(1)
                        sender = match_sender.group(1) if match_sender else "Desconocido"
                        
                        # Filtro anti-eco (cambia 'GUARDIAN' por tu callsign de WinTAK/Script si hace falta)
                        if sender == "BROCHURE": 
                            continue

                        imprimir.tak(f"Mensaje interceptado de {sender}: {mensaje}")
                    
                    # Empaquetamos para LoRa (0x02)
                    texto_bin = mensaje.encode('utf-8')[:50] 
                    paquete_lora = struct.pack(f'>BBB{len(texto_bin)}s', 
                                               0x02, self.id_soldado, len(texto_bin), texto_bin)
                    
                    # Aquí podrías enviar el paquete_lora a través de tu radio LoRa

            except Exception as e:
                imprimir.error(f"Error parseando chat: {e}")


# --- CAPA DE APLICACIÓN (LÓGICA DEL SOLDADO) ---
class TacticalNode:
    def __init__(self):
        self.id_soldado = 1 # ID único para cada nodo (1-255)
        
        self.cot_manager = CotHandler(callsign_prefix="TFG-")

        self.reticulum = RNS.Reticulum()

        self.identity = RNS.Identity()
        self.identity.update_hashes()

        self.destino_comms = RNS.Destination(
            self.identity,
            RNS.Destination.IN,
            RNS.Destination.SINGLE,
            "tactical","comms"
        )
        
        self.destino_comms.set_packet_callback(self.recibir_comms)
        self.destino_comms.announce()


        self.tak = TAKControl()
        self.tak.id_soldado = self.id_soldado
        self.tak.cot_manager = self.cot_manager
      

    def start(self):

        # Arrancamos el hilo de escucha de WinTAK para recibir chats (Daemon = muere si cierra el main)
        self.hilo_wintak = threading.Thread(target=self.tak.escuchar_wintak, daemon=True)
        self.hilo_wintak.start()
        
        imprimir.system("Hilo de escucha WinTAK iniciado.")

        # Arrancamos el bucle principal de la aplicación
        self.bucle_generador_gps()

    def bucle_generador_gps(self):
        """
        Simula la lectura del GPS y la generación de paquetes.
        """
        #imprimir.system("[APP] Nodo Táctico Operativo. Generando tráfico...")
        contador = -1
        lat = 40.416
        lat_entera = int(lat * 1e7)
        lon = -3.703
        lon_entera = int(lon * 1e7)
        
        try:
            while True:
                # 1. Simular movimiento
                lat_entera += int(random.uniform(-1000, 1000))
                
                # 2. Crear paquete BINARIO (Protocolo TFG)
                # Estructura: [CABECERA (1B)] + [ID (1B)] + [LAT (4B)] + [LON (4B)]
                # Cabecera 0x01 = PLI (Posición)
                paquete = struct.pack('>BBii', 0x01, self.id_soldado, lat_entera, lon_entera)
                
                # 3. Enviar a la radio (De forma asíncrona/segura)
                imprimir.system(f"Generando posición GPS para Soldado-{self.id_soldado}")
                self.enviar_posicion(paquete)

                # 2. DISPARADOR DE PRUEBA: Cada 3 envíos, simulamos un chat recibido por LoRa
                contador += 1
                if contador % 1 == 0:
                    imprimir.system("PROBANDO INYECCIÓN DE CHAT...")
                    
                    # --- EL FIX DE HOY ---
                    # 1. Inyectamos una posición falsa para crear a Soldier-2 en el mapa de ATAK
                    self.tak.gps_a_atak(2, lat_entera/1e7, lon_entera/1e7)
                    
                    # Pequeña pausa opcional (0.5s) para asegurar que ATAK procesa primero el mapa
                    time.sleep(0.5) 
                    
                    # 2. Ahora le enviamos el mensaje asignado a Soldier-2
                    #self.tak.inyectar_chat_en_atak(2, "MENSAJE DE PRUEBA TFG")
                # 4. Esperar 2 segundos antes del siguiente 'ping'
                time.sleep(10)
                
        except KeyboardInterrupt:
            imprimir.system("\nApagando nodo táctico...")


    def recibir_comms(self, packet):
        data = packet.data
        tipo = data[0]
        imprimir.info(f"Paquete recibido por Rns! Tamaño: {len(data)} bytes | Contenido (hex): {data.hex().upper()}")

        if tipo == 0x01: # GPS de otro soldado
            header, id_remoto, lat_e, lon_e = struct.unpack('>BBii', data)
            self.tak.gps_a_atak(id_remoto, lat_e/1e7, lon_e/1e7)
            imprimir.radio_rx(f"GPS de Soldado-{id_remoto} posicionado en ATAK")
            
        elif tipo == 0x02: # Chat de otro soldado
            id_remoto = data[1]
            msg = data[2:].decode('utf-8')
            #self.tak.inyectar_chat_en_atak(id_remoto, msg)

        else:
            imprimir.error(f"Tipo de paquete desconocido: {tipo}")
            imprimir.info(f"Contenido completo del paquete: {data.hex().upper()}")

    def enviar_posicion(self, paquete_binario):
        """ Método para enviar a la red """
        # Para el TFG, simplificaremos enviando a un destino conocido
        # o usando el método de propagación de RNS.
        if hasattr(self, 'ultimo_destino_visto'):
            p = RNS.Packet(self.ultimo_destino_visto, paquete_binario)
            p.send()
            imprimir.info(f"Posición enviada a {self.ultimo_destino_visto} por RNS.")

# --- PUNTO DE ENTRADA ---
if __name__ == "__main__":
    nodo = TacticalNode()
    nodo.start()
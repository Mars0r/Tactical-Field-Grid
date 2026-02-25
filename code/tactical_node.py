import re
import threading
import time
import struct
import random
import queue
import socket
import datetime

# --- CONFIGURACIÓN ---
# Pon False cuando tengas la Raspberry con LoRa real
def Simulación():
    simint = input("[SISTEMA] ¿Iniciar el sistema como simulación? (1/0): ")
    if simint == '1':
        print("[SISTEMA] Modo SIMULACIÓN ACTIVADO. No se usará hardware real.")
        return True
    else:
        print("[SISTEMA] Modo REAL ACTIVADO. Se intentará usar hardware LoRa.")
        return False
    
SIMULACION = Simulación()
ATAK_MCAST_GRP = '239.2.3.1' # UDP Bradcast
ATAK_MCAST_PORT = 6969
ATAK_CHAT_GRP = '224.10.10.1'
ATAK_CHAT_PORT = 17012

def gps_a_atak(id_soldado, lat, lon):
    """Convierte datos de posición en un evento CoT y lo envía a la tablet local.    """
    # 1. Usar UTC real (imprescindible para TAK)
    now = datetime.datetime.now(datetime.timezone.utc)
    
    # 2. Sumar 10 minutos de forma segura (gestiona cambios de hora/día automáticamente)
    stale = now + datetime.timedelta(minutes=10)

    # 3. Formatear strings
    time_str = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    stale_str = stale.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    # ... resto de tu lógica ...
    print(f"[DEBUG] Sent at: {time_str} | Expires at: {stale_str}")

    # Definimos el Callsign basado en el ID
    callsign = f"ALPHA-{id_soldado:02d}"
    uid = f"SOLDIER-{id_soldado}"

    # XML CoT estándar (a-f-G-U-C = Amigo, Tierra, Combatiente)
    cot_xml = f"""<?xml version='1.0' standalone='yes'?>
    <event version="2.0" uid="{uid}" type="a-f-G-U-C" time="{time_str}" start="{time_str}" stale="{stale_str}" how="m-g">
        <point lat="{lat:.7f}" lon="{lon:.7f}" hae="0.0" ce="10.0" le="10.0"/>
        <detail>
            <contact callsign="{callsign}"/>
            <__group name="Blue" role="Team Member"/>
        </detail>
    </event>"""

    broadcast_udp(cot_xml)

def inyectar_chat_en_atak(id_remoto, texto):
    now = datetime.now()
    time_str = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    # Los chats suelen tener un tiempo de vida corto en el mapa, pero persistente en el log
    stale_str = (datetime.now()).replace(minute=(now.minute + 1) % 60).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    callsign = f"ALPHA-{id_remoto:02d}"
    uid = f"SOLDIER-{id_remoto}"

    # XML de Chat simplificado pero compatible con WinTAK
    chat_xml = f"""<?xml version='1.0' standalone='yes'?>
    <event version="2.0" uid="GeoChat.{uid}.{now.timestamp()}" type="b-t-f" time="{time_str}" start="{time_str}" stale="{stale_str}" how="m-g">
        <point lat="0.0" lon="0.0" hae="0.0" ce="999999" le="999999"/>
        <detail>
            <__chat parent="RootContactGroup" groupName="All Staff" chatId="All Staff" senderCallsign="{callsign}" message="{texto}">
                <chatgrp uid0="Team-Blue" uid1="{uid}"/>
            </__chat>
            <link uid="{uid}" type="a-f-G-U-C" relation="p-p"/>
            <remarks>{texto}</remarks>
            <contact callsign="{callsign}"/>
        </detail>
    </event>"""

    print(f"[ATAK] Inyectando chat de {callsign}: {texto}")
    broadcast_udp(chat_xml) # La función que ya tienes para enviar a 127.0.0.1:6969

def broadcast_udp(xml_mssg):  
    # Simple UDP Unicast a localhost (WinTAK lo recibirá igual si escucha en el 6969)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(xml_mssg.encode('utf-8'), (ATAK_MCAST_GRP, ATAK_MCAST_PORT))
        print(f"[ATAK] Inyectado en ATAK: {xml_mssg[:100]}...") # Log parcial para no saturar
    
    except Exception as e:
        print(f"[ERROR-UDP] {e}")

    #3. Pequeña pausa para no quemar la CPU
    time.sleep(0.05)



# --- MOCK PARA SIMULAR HARDWARE (Solo si no tienes el chip) ---
class MockSerial:
    def __init__(self):
        print("[HW] Simulación de LoRa iniciada.")
        self.in_waiting = 0
        global SIMULACION
        SIMULACION = True

    
    def write(self, data):
        # Simula el tiempo que tarda el chip en enviar por aire (Airtime)
        time.sleep(0.2) 
        print(f"[RADIO-TX] >>> {data.hex().upper()} ({len(data)} bytes)")
        
    def read(self, size):
        return b'' # Por ahora simulamos silencio en la radio
    
    # --- CLASE GESTORA DE HARDWARE (DRIVER) ---
class GestorRadio:
    def __init__(self, puerto='/dev/ttyUSB0'):
        if not SIMULACION:
            try: 
                import serial
                self.serial = serial.Serial(puerto, 9600, timeout=0.1)

            except Exception as e:
                print(f"[ERROR] No se pudo abrir el puerto {puerto}: {e}")
                print("[SISTEMA] Cambiando a modo SIMULACIÓN.")  
                
                self.serial = MockSerial()

        else:
            self.serial = MockSerial()
            
        
        # COLA DE TRANSMISIÓN (El Buzón de Salida)
        # Aquí la App deja los mensajes. El Driver los recoge uno a uno.
        self.tx_queue = queue.Queue()
        
        # Bandera para detener el hilo suavemente
        self.running = True

    def enviar_seguro(self, datos):
        """Método público: La App llama a esto para enviar."""
        self.tx_queue.put(datos) # No bloquea, solo deja la carta en el buzón

    def loop_controlador(self):
        """
        EL HILO GUARDIÁN (Traffic Cop).
        Es el ÚNICO que tiene permiso para tocar self.serial
        """
        print("[SYSTEM] Controlador de Radio iniciado.")
        
        while self.running:
            data = None
            item = None
            # 1. ¿Hay algo que enviar? (Prioridad TX)
            if not self.tx_queue.empty():
                item = self.tx_queue.get()
                try:
                    # Escribir en hardware
                    self.serial.write(item)
                    self.tx_queue.task_done()
                except Exception as e:
                    print(f"[ERROR] Fallo en TX: {e}")
            
            # 2. ¿Hay algo que recibir? (RX Polling)
            # (En simulación esto no hace mucho, pero en real lee del buffer)
            try:
                if SIMULACION:
                    data = item # En simulación no leemos nada por ahora
                elif self.serial.in_waiting > 0:
                    data = self.serial.read(self.serial.in_waiting)
                    print(f"[RADIO-RX] <<< {data.hex()}")

                    # Dentro del hilo de escucha (RX)
                if data:
                    tipo_mensaje = data[0]
                    print(f"[RADIO-RX] <<< {data.hex().upper()}")
                    trama = data[:10]
                    if tipo_mensaje == 0x01 and len(trama) >=10:
                        _, id_remoto, lat_rx, lon_rx = struct.unpack('>BBii', data[:10])

                        lat_final = lat_rx / 1e7
                        lon_final = lon_rx / 1e7

                        gps_a_atak(id_remoto, lat_final, lon_final)
                        print(f"[ATAK] Inyectado Soldado-{id_remoto} en {lat_final:.6f}, {lon_final:.6f}")

                    # ... dentro del bloque de recepción ...
                    elif tipo_mensaje == 0x02: # TIPO CHAT
                        # data[0]=Tipo, data[1]=ID_Origen, data[2]=Longitud
                        id_remoto = data[1]
                        longitud = data[2]
                        texto = data[3:3+longitud].decode('utf-8')
                        
                        print(f"[LORA-CHAT] Soldado-{id_remoto} dice: {texto}")
                        
                        # Lo metemos en WinTAK para que el usuario lo lea
                        inyectar_chat_en_atak(id_remoto, texto)

            except Exception as e:
                print(f"[ERROR] Fallo en RX: {e}")


# --- CAPA DE APLICACIÓN (LÓGICA DEL SOLDADO) ---
class TacticalNode:
    def __init__(self):
        self.radio = GestorRadio()
        self.id_soldado = 1
        
        
    def start(self):
        # Arrancamos el hilo del controlador de radio (Daemon = muere si cierra el main)
        #hilo_radio = threading.Thread(target=self.radio.loop_controlador, daemon=True)
        #hilo_radio.start()
        #print("[SYSTEM] Controlador de Radio iniciado.")

        # Arrancamos el hilo de escucha de WinTAK para recibir chats (Daemon = muere si cierra el main)
        self.hilo_wintak = threading.Thread(target=self.escuchar_wintak, daemon=True)
        self.hilo_wintak.start()
        
        print("[SYSTEM] Hilo de escucha WinTAK iniciado.")
        #self.hilo_wintak.join() # Esperamos a que termine (en realidad no debería terminar nunca)
        # Arrancamos el bucle principal de la aplicación
        self.bucle_generador_gps()

    def bucle_generador_gps(self):
        """
        Simula la lectura del GPS y la generación de paquetes.
        """
        print("[APP] Nodo Táctico Operativo. Generando tráfico...")
        
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
                print(f"[APP] Generando posición GPS...")
                self.radio.enviar_seguro(paquete)
                
                # 4. Esperar 2 segundos antes del siguiente 'ping'
                time.sleep(10)
                
        except KeyboardInterrupt:
            print("\n[SYSTEM] Apagando nodo táctico...")
            self.radio.running = False



    def escuchar_wintak(self):
        UDP_IP = "0.0.0.0" 
        UDP_PORT = 17012
        MCAST_GRP = "224.10.10.1" # La dirección de chat de TAK

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        
        # Permitir que varios programas (como WinTAK y tu script) usen el puerto
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((UDP_IP, UDP_PORT))

        # --- LA MAGIA DEL MULTICAST PARA WINDOWS ---
        # Le decimos a la tarjeta de red: "Por favor, déjame pasar los paquetes de la 224.10.10.1"
        mreq = struct.pack("4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        # -------------------------------------------

        print(f"[CHAT-LISTENER] Escuchando MULTICAST en {MCAST_GRP}:{UDP_PORT}...")
        
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

                        print(f"\n[WINTAK/ATAK] Mensaje interceptado de {sender}: {mensaje}")
                    
                    # Empaquetamos para LoRa (0x02)
                    texto_bin = mensaje.encode('utf-8')[:50] 
                    paquete_lora = struct.pack(f'>BBB{len(texto_bin)}s', 
                                               0x02, self.id_soldado, len(texto_bin), texto_bin)
                    
                    self.radio.enviar_seguro(paquete_lora)

            except Exception as e:
                print(f"[ERROR] Error parseando chat: {e}")

# --- PUNTO DE ENTRADA ---
if __name__ == "__main__":
    nodo = TacticalNode()
    nodo.start()
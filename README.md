# 📡 Proyecto TFG: Red Táctica Híbrida de Malla (Hybrid Tactical Mesh Network)

**Estado del Proyecto:** Fase de Diseño Arquitectónico y Selección de Hardware Completada.
**Objetivo:** Desarrollar un sistema de comunicaciones táctico para despliegue rápido (Base ↔ Soldado/Dron) que garantice transmisión de vídeo y telemetría crítica mediante redundancia espectral.

---

## 1. Concepto y Arquitectura 🧠

El sistema se basa en una arquitectura de **"Doble Plano"** para garantizar la resiliencia en entornos hostiles o con alta interferencia:

1. **Plano de Banda Ancha (Vídeo):** Opera sobre **WiFi (2.4 GHz)**. Su función es transmitir vídeo en tiempo real y datos pesados. Es sacrificable; si se corta, la misión continúa.
2. **Plano de Control Crítico (Telemetría):** Opera sobre **LoRa (868 MHz)**. Su función es mantener el mando y control (C2), coordenadas GPS y órdenes de texto. Es robusto y de largo alcance.

**Topología:**

* **Lógica:** Malla (Mesh) distribuida. Todos los nodos pueden enrutar tráfico de otros.
* **Física:** Enlace inalámbrico Ad-Hoc/Mesh Point entre nodos móviles.

---

## 2. Hardware y Presupuesto Estimado 🛠️

La selección de hardware prioriza componentes COTS (*Commercial Off-The-Shelf*) compatibles nativamente con Linux y estándares abiertos.

### Nodo Base / Soldado (Por unidad)

| Componente | Modelo Recomendado | Justificación Técnica | Precio Est. |
| --- | --- | --- | --- |
| **Computador** | Raspberry Pi 4/5 (o PC Portátil) | Potencia suficiente para codificar vídeo y gestionar enrutamiento. | 60€ - N/A |
| **Interfaz WiFi** | **Alfa Network AWUS036ACM** | Chipset **MT7612U**. Soporta modo Monitor, Inyección y **Mesh Point (802.11s)**. Doble puerto de antena (MIMO/Diversidad). | ~35€ |
| **Interfaz LoRa** | Módulo ESP32 LoRa (LilyGO/TTGO) | Para correr el firmware de interfaz RNS (Reticulum). Económico y bajo consumo. | ~15€ |
| **Antenas** | 2x Omnidireccionales + (Opcional) 1x Panel | 2.4GHz para WiFi y 868MHz para LoRa. Uso de antena de panel en Base para sectorización. | ~20€ |
| **Total aprox.** |  |  | **~130€ / nodo** |

---

## 3. Stack de Software y Lógica 💻

### A. Capa de Red (Vídeo - WiFi)

* **Estándar:** IEEE **802.11s** (Mesh Point). Sustituye al antiguo modo Ad-Hoc (IBSS) por ser más eficiente y soportar seguridad moderna.
* **Protocolo de Enrutamiento:** **B.A.T.M.A.N. adv** (Better Approach To Mobile Ad-hoc Networking).
* *Lógica:* Opera en Capa 2 (Enlace de Datos). Simula un switch virtual gigante donde todos los nodos parecen estar conectados por un cable ethernet invisible.


* **Frecuencia:** **2.4 GHz** (Canales 1, 6 u 11).
* *Motivo:* Mejor penetración de obstáculos (árboles, muros) que 5GHz, crucial para operarios a nivel de suelo.



### B. Capa de Control (Comandos - LoRa)

* **Protocolo:** **Reticulum Network Stack (RNS)**.
* *Lógica:* Red soberana sin IP. Usa criptografía asimétrica para direccionamiento. Si el WiFi cae, RNS sigue enviando coordenadas y estado del soldado.


* **Frecuencia:** **868 MHz** (Europa). Alcance de varios Km con baja tasa de datos.

---

## 4. Desafíos de Ingeniería y Soluciones Adoptadas 🚧

Durante la fase de diseño, se encontraron los siguientes problemas técnicos y se definieron estas soluciones:

### 🔴 Problema 1: Beamforming y Sigilo (LPD)

**El reto:** Las tarjetas WiFi comerciales USB no permiten *Beamforming* activo (Phased Array) por software para dirigir la señal y evitar ser detectados por el enemigo.
**La Solución:** Estrategia mixta Software/Hardware.

1. **ATPC (Software):** Implementar un script que lea la calidad del enlace (TQ/RSSI) y ajuste dinámicamente la potencia de transmisión (`txpower`). *Lógica: "Susurrar" en vez de gritar si el receptor está cerca.*
2. **Diversidad de Sector (Hardware):** Usar los dos puertos de antena de la tarjeta Alfa ACM. Conectar una antena orientada al Norte y otra al Sur. El driver elegirá la mejor antena (Diversity), simulando un direccionamiento básico.

### 🔴 Problema 2: Vídeo Analógico vs. Digital

**El reto:** El vídeo analógico (5.8GHz FPV) tiene latencia cero, pero no permite enrutamiento.
**La Solución:** Uso de **Vídeo Digital**.

* Aunque tiene más latencia (~100-200ms), permite encapsular el vídeo en paquetes IP. Esto habilita la **topología Mesh** (saltar de un soldado a otro para llegar a la base) y el **cifrado** de la imagen, requisitos indispensables para una red táctica.

### 🔴 Problema 3: Conexión Automática Segura

**El reto:** Necesidad de que los soldados se conecten automáticamente al encender el equipo (Zero-Touch) sin dejar la red abierta a intrusos.
**La Solución:** **WPA3-SAE**.

* Utilizar el estándar 802.11s con autenticación SAE (Simultaneous Authentication of Equals) pre-configurada en el archivo `wpa_supplicant`.
* Esto permite autodescubrimiento seguro: los nodos solo hacen "peering" si tienen la clave criptográfica correcta.

### 🔴 Problema 4: WiFi HaLow (802.11ah) vs. Híbrido

**El reto:** Existencia de tecnologías unificadas (HaLow) que prometen largo alcance y vídeo en un solo chip.
**La Solución:** Mantener la **Arquitectura Híbrida**.

* Se rechaza HaLow por falta de madurez en drivers Linux y por seguridad operativa: Si se satura o interfiere la frecuencia única de HaLow, se pierde *todo*. Con el sistema híbrido (2.4G + 868M), se garantiza la supervivencia del enlace de control (LoRa) ante la pérdida del vídeo.
* 

### 🔴 Problema 5. Estrategia de Autoconfiguración "Zero-Touch" 🤖
Para garantizar la operatividad inmediata en campo sin intervención técnica (sin teclados ni pantallas), se ha diseñado un sistema de auto-descubrimiento y configuración automática que elimina la necesidad de servidores DHCP centrales.

**A. Direccionamiento IP Algorítmico (Persistencia de Identidad)**
En lugar de depender de un servidor DHCP (punto único de fallo), cada nodo calcula su propia dirección IPv4 basándose en su dirección física (MAC Address). Esto garantiza que un soldado siempre tenga la misma IP en cualquier misión, facilitando la identificación.

Lógica: Conversión de los dos últimos octetos de la MAC de Hexadecimal a Decimal.

Espacio de direcciones: Subred privada 10.0.0.0/16.

Fórmula:

Dado MAC: XX:XX:XX:XX:YY:ZZ

IP Generada: 10.0.DEC(YY).DEC(ZZ)

Ejemplo: MAC ...:25:1A → IP 10.0.37.26.

**B. Gestión de Claves por Hardware (Mission Key)**
Para cambiar de red o rotar claves de cifrado sin reconfigurar el sistema operativo, se implementa un mecanismo de "Llave de Misión".

Funcionamiento: Al inicio, el sistema busca un archivo de configuración (wpa_supplicant.conf) en medios extraíbles (USB). Si lo encuentra, actualiza la configuración WiFi automáticamente.

Ventaja Operativa: Permite reasignar un dron o soldado a un pelotón diferente simplemente cambiando la tarjeta SD o conectando un USB de configuración antes del encendido.

---

## 5. Próximos Pasos (Roadmap) 🚀

Al retomar el proyecto, el orden de ejecución será:

1. **Adquisición:** Comprar las tarjetas Alfa AWUS036ACM.
2. **Fase 1 (Enlace Físico):** Configurar `wlan0` en modo Mesh Point (802.11s) en dos máquinas Linux y lograr `ping` entre ellas.
3. **Fase 2 (Enrutamiento):** Levantar B.A.T.M.A.N. adv sobre esa interfaz `wlan0`.
4. **Fase 3 (Aplicación):** Transmitir stream de vídeo por la red BATMAN y probar la reconexión automática.
5. **Fase 4 (Optimización):** Implementar el script de control de potencia (Stealth).

---

*Este documento resume el estado del arte del TFG a fecha de Enero 2026.*

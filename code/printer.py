class imprimir:
    VERDE = '\033[92m'   # Para mensajes de éxito o Radio RX
    AZUL = '\033[94m'    # Para mensajes de TAK / WinTAK
    AMARILLO = '\033[93m' # Para avisos o GPS
    ROJO = '\033[91m'     # Para errores críticos
    CYAN = '\033[96m'     # Para el sistema/hilos
    BOLD = '\033[1m'      # Negrita
    RESET = '\033[0m'     # Volver al color normal (¡IMPRESCINDIBLE!)
    @staticmethod
    def info(mensaje):
        print(f"{imprimir.AMARILLO}[INFO] {mensaje}{imprimir.RESET}")

    @staticmethod
    def error(mensaje):
        print(f"{imprimir.ROJO}[ERROR] {mensaje}{imprimir.RESET}")

    @staticmethod
    def tak(mensaje):
        print(f"{imprimir.AZUL}[TAK] {mensaje}{imprimir.RESET}")

    @staticmethod
    def radio_rx(mensaje):
        print(f"{imprimir.VERDE}[RADIO-RX] <<< {mensaje}{imprimir.RESET}")

    @staticmethod
    def radio_tx(mensaje):
        print(f"{imprimir.CYAN}[RADIO-TX] >>>{mensaje}{imprimir.RESET}")

    @staticmethod
    def system(mensaje):
        print(f"{imprimir.BOLD}[SYSTEM] {mensaje}{imprimir.RESET}")

    @staticmethod
    def debug(mensaje):
        print(f"{imprimir.AMARILLO}[DEBUG] {mensaje}{imprimir.RESET}")
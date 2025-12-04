import json
import socket
import threading
from datetime import datetime
from pathlib import Path
from time import sleep

# Tenta importar RPi.GPIO; se não estiver disponível (ex: desenvolvimento no Windows), usa mock
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("Aviso: RPi.GPIO não disponível. Controle do solenóide desativado (modo simulação).")

HOST = '0.0.0.0'  # Escutar em todas as interfaces de rede
PORT = 5000       # Porta para escutar
BASE_DIR = Path(__file__).parent.resolve()
LOG_FILE = str((BASE_DIR / 'access_log.json').resolve())
AUTH_CARDS_FILE = str((BASE_DIR / 'authorized_cards.json').resolve())

# Configuração do pino GPIO para o solenóide/relé
SOLENOID_PIN = 18          # Pino BCM conectado ao relé do solenóide
DOOR_OPEN_SECONDS = 3      # Tempo que a porta fica destrancada (segundos)

class RFIDServer:
    def __init__(self):
        self.server_socket = None
        self.authorized_cards = self.load_authorized_cards()
        self._setup_gpio()

    def _setup_gpio(self):
        """Configura o pino GPIO para controlar o solenóide/relé."""
        if GPIO_AVAILABLE:
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(SOLENOID_PIN, GPIO.OUT)
            # Garante que o solenóide começa desligado (porta trancada)
            GPIO.output(SOLENOID_PIN, GPIO.HIGH)
            print(f"GPIO {SOLENOID_PIN} configurado para controle do solenóide.")

    def _unlock_door(self):
        """Destrava a porta por DOOR_OPEN_SECONDS segundos."""
        if not GPIO_AVAILABLE:
            print(f"[SIMULAÇÃO] Porta destrancada por {DOOR_OPEN_SECONDS}s")
            return
        print("Destrancando porta...")
        GPIO.output(SOLENOID_PIN, GPIO.LOW)   # Ativa o relé (solenóide ligado)
        sleep(DOOR_OPEN_SECONDS)
        GPIO.output(SOLENOID_PIN, GPIO.HIGH)  # Desativa o relé (solenóide desligado)
        print("Porta trancada novamente.")

    def load_authorized_cards(self):
        try:
            with open(AUTH_CARDS_FILE, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Criar um arquivo padrão se não existir ou for inválido
            default_cards = {
                "cards": [
                    {"id": "0x1a2b3c4d", "name": "Cartão de Admin", "authorized": True},
                    {"id": "0xabcdef12", "name": "Cartão de Visitante", "authorized": False}
                ]
            }
            with open(AUTH_CARDS_FILE, 'w') as f:
                json.dump(default_cards, f, indent=4)
            return default_cards

    def save_access_log(self, card_id, authorized):
        try:
            log_data = []
            try:
                with open(LOG_FILE, 'r') as f:
                    log_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                log_data = []
            
            log_entry = {
                "card_id": card_id,
                "timestamp": datetime.now().isoformat(),
                "authorized": authorized
            }
            log_data.append(log_entry)
            
            with open(LOG_FILE, 'w') as f:
                json.dump(log_data, f, indent=4)
        except Exception as e:
            print(f"Erro ao registrar acesso: {e}")

    def is_card_authorized(self, card_id):
        # Reload authorized cards on each check so dashboard updates apply immediately
        self.authorized_cards = self.load_authorized_cards()
        for card in self.authorized_cards.get("cards", []):
            if card.get("id") == card_id:
                return card.get("authorized", False)
        return False

    def handle_client(self, client_socket, address):
        print(f"Conexão de {address}")
        try:
            # Receber dados do cliente (ESP32)
            data = client_socket.recv(1024).decode('utf-8').strip()
            print(f"Recebido: {data}")
            
            # Verificar se o cartão está autorizado
            authorized = self.is_card_authorized(data)
            
            # Registrar a tentativa de acesso
            self.save_access_log(data, authorized)

            # Se autorizado, destrancar a porta
            if authorized:
                # Executa em thread separada para não bloquear outras conexões
                unlock_thread = threading.Thread(target=self._unlock_door, daemon=True)
                unlock_thread.start()

            # Enviar resposta de volta ao ESP32
            response = "AUTHORIZED" if authorized else "DENIED"
            client_socket.sendall(response.encode('utf-8'))
            print(f"Resposta enviada: {response}")
        except Exception as e:
            print(f"Erro ao processar cliente: {e}")
        finally:
            client_socket.close()

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((HOST, PORT))
        self.server_socket.listen(5)
        print(f"Servidor escutando em {HOST}:{PORT}")
        
        try:
            while True:
                client_socket, address = self.server_socket.accept()
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket, address))
                client_thread.daemon = True
                client_thread.start()
        except KeyboardInterrupt:
            print("Servidor desligando")
        finally:
            self._cleanup_gpio()
            if self.server_socket:
                self.server_socket.close()

    def _cleanup_gpio(self):
        """Libera os recursos do GPIO ao encerrar."""
        if GPIO_AVAILABLE:
            GPIO.output(SOLENOID_PIN, GPIO.HIGH)  # Garante porta trancada
            GPIO.cleanup()
            print("GPIO liberado.")

if __name__ == "__main__":
    server = RFIDServer()
    server.start()

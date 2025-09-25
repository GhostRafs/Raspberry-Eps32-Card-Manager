#include <SPI.h>
#include <MFRC522.h>
#include <WiFi.h>

// Credenciais de rede - ALTERAR
const char* ssid = "SEU_WIFI_SSID";
const char* password = "SUA_SENHA_WIFI";

// Configurações do servidor
const char* serverAddress = "192.168.1.100"; // Endereço IP do Raspberry Pi
const int serverPort = 5000;

// Definições de pinos para ESP32
#define SS_PIN 5    // Pino SDA
#define RST_PIN 22  // Pino RST
#define GREEN_LED 25 // GPIO para LED verde (autorizado)
#define RED_LED 26   // GPIO para LED vermelho (negado)
#define BUZZER 27    // GPIO para buzzer

// Create MFRC522 instance
MFRC522 rfid(SS_PIN, RST_PIN);

// ID do último cartão lido
String lastCardID = "";
unsigned long lastReadTime = 0;
const int READ_DELAY = 5000;

void setup() {
  // Inicializar comunicação serial
  Serial.begin(115200);
  while (!Serial); 
  
  SPI.begin();
    rfid.PCD_Init();
  delay(4);
  rfid.PCD_DumpVersionToSerial();

  // Conectar ao WiFi
  connectToWifi();
  
  Serial.println("Pronto para ler cartões RFID...");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Conexão WiFi perdida. Reconectando...");
    connectToWifi();
  }
  
  if (!rfid.PICC_IsNewCardPresent()) {
    return;
  }
  
  if (!rfid.PICC_ReadCardSerial()) {
    return;
  }
  
  // Obter ID do cartão como string hexadecimal
  String cardID = getCardIDHex();
  
  // Verificar se é o mesmo cartão lido dentro do tempo de atraso
  unsigned long currentTime = millis();
  if (cardID == lastCardID && (currentTime - lastReadTime < READ_DELAY)) {
    return;
  }
  
  // Atualizar informações do último cartão lido
  lastCardID = cardID;
  lastReadTime = currentTime;
  
  Serial.print("Cartão detectado, ID: ");
  Serial.println(cardID);
  String response = sendCardToServer(cardID);
  
  if (response == "AUTHORIZED") {
    Serial.println("Acesso autorizado!");
    indicateAuthorized();
  } 
  else if (response == "DENIED") {
    Serial.println("Acesso negado!");
    indicateDenied();
  } 
  else {
    Serial.print("Resposta desconhecida: ");
    Serial.println(response);
    indicateError();
  }
  
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
  
  delay(1000);
}

// Converter ID do cartão RFID para string hexadecimal
String getCardIDHex() {
  String hex = "0x";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) {
      hex += "0";
    }
    hex += String(rfid.uid.uidByte[i], HEX);
  }
  hex.toLowerCase();
  return hex;
}

// Conectar à rede WiFi
void connectToWifi() {
  Serial.print("Conectando a ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  // Aguardar conexão com timeout
  int timeout = 0;
  while (WiFi.status() != WL_CONNECTED && timeout < 20) {
    delay(500);
    Serial.print(".");
    timeout++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi conectado");
    Serial.print("Endereço IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nFalha ao conectar ao WiFi");
  }
}

// Enviar ID do cartão para o servidor e obter resposta
String sendCardToServer(String cardID) {
  WiFiClient client;
  String response = "";
  
  Serial.print("Conectando a ");
  Serial.println(serverAddress);
  
  if (client.connect(serverAddress, serverPort)) {
    Serial.println("Conectado ao servidor");
    
    // Enviar o ID do cartão
    client.println(cardID);
    Serial.print("Enviado: ");
    Serial.println(cardID);
    
    // Aguardar pela resposta do servidor
    unsigned long timeout = millis();
    while (client.connected() && !client.available()) {
      if (millis() - timeout > 5000) {
        Serial.println("Timeout do servidor!");
        client.stop();
        return "ERRO: TIMEOUT";
      }
    }
    
    // Ler a resposta
    while (client.available()) {
      char c = client.read();
      response += c;
    }
    
    // Desconectar
    client.stop();
    
    Serial.print("Recebido: ");
    Serial.println(response);
  } 
  else {
    Serial.println("Falha na conexão com o servidor");
    response = "ERRO: FALHA_CONEXAO";
  }
  
  return response;
}


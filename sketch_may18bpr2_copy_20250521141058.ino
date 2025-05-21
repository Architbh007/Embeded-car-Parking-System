#include <SPI.h>
#include <WiFiNINA.h>
#include <PubSubClient.h>
#include <WiFiUdp.h>
WiFiUDP udp;

// Wi-Fi credentials
const char* ssid = "iPhone";
const char* password = "saymyname";

// Public MQTT broker
const char* mqttServer = "broker.hivemq.com";
const int mqttPort = 1883;

// Sensor pins
const int trig1 = 2;
const int echo1 = 3;
const int trig2 = 4;
const int echo2 = 5;

WiFiClient wifiClient;
PubSubClient client(wifiClient);

void setup() {
  Serial.begin(9600);

  // Sensor pin modes
  pinMode(trig1, OUTPUT);
  pinMode(echo1, INPUT);
  pinMode(trig2, OUTPUT);
  pinMode(echo2, INPUT);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting...");
  }

  Serial.println("✅ Connected to WiFi!");
  Serial.println(WiFi.localIP());

  Serial.print("Pinging MQTT broker... ");
  int result = udp.beginPacket(mqttServer, 1883);
  Serial.println(result ? "✅ Reachable!" : "❌ NOT reachable!");

  // Setup MQTT server
  client.setServer(mqttServer, mqttPort);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }

  client.loop();  // handle incoming/outgoing MQTT traffic

  long dist1 = readDistance(trig1, echo1);
  long dist2 = readDistance(trig2, echo2);

  String slot1 = (dist1 < 10) ? "occupied" : "vacant";
  String slot2 = (dist2 < 10) ? "occupied" : "vacant";

  String payload = "{\"slot1\":\"" + slot1 + "\",\"slot2\":\"" + slot2 + "\"}";
  Serial.println("📡 Publishing: " + payload);

  // publishing it to the topic
  client.publish("archit/parking", payload.c_str());

  delay(3000);
}

void reconnect() {
  while (!client.connected()) {
    Serial.println("Connecting to MQTT...");
    if (client.connect("ArduinoClient", "", "")) {
      Serial.println(" Connected to MQTT!");
    } else {
      Serial.print("MQTT failed, rc=");
      Serial.println(client.state());
      delay(2000);
    }
  }
}

long readDistance(int trig, int echo) {
  digitalWrite(trig, LOW);
  delayMicroseconds(2);
  digitalWrite(trig, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig, LOW);
  long duration = pulseIn(echo, HIGH);
  return duration * 0.034 / 2;
}

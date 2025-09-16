#include <ArduinoBLE.h>
#include "HX711.h"

// Define the pins for the HX711
const int DOUT_PIN = 3;
const int SCK_PIN = 2;

// Create an instance of the HX711 class
HX711 scale;

// Define BLE Service and Characteristic UUIDs. You can generate these online.
BLEService loadCellService("ff8ebe26-ed45-4905-941c-85694ec1a320");
BLEFloatCharacteristic weightCharacteristic("ff8ebe26-ed45-4905-941c-85694ec1a320", BLERead | BLENotify);

void setup() {
  Serial.begin(9600);
  while (!Serial);

  // Initialize the HX711 module
  scale.begin(DOUT_PIN, SCK_PIN);
  scale.set_scale(2280.f); // Set your calibration factor here
  scale.tare();

  // Initialize BLE
  if (!BLE.begin()) {
    Serial.println("Starting BLE failed!");
    while (1);
  }

  // Set local name and add service/characteristic
  BLE.setLocalName("Uno R4 Load Cell");
  BLE.setAdvertisedService(loadCellService);
  loadCellService.addCharacteristic(weightCharacteristic);
  BLE.addService(loadCellService);

  // Set the initial value of the characteristic
  weightCharacteristic.writeValue(0.0f);

  // Start advertising
  BLE.advertise();
  Serial.println("BLE advertising started.");
}

void loop() {
  // Wait for a central device to connect
  BLEDevice central = BLE.central();
  if (central) {
    Serial.print("Connected to central: ");
    Serial.println(central.address());

    // While connected, send data every 100 ms
    while (central.connected()) {
      float weight = scale.get_units();
      weightCharacteristic.writeValue(weight); // Send the float value over BLE
      
      Serial.print("Sending weight: ");
      Serial.println(weight, 2);
      
      delay(100);
    }

    // When disconnected
    Serial.print("Disconnected from central: ");
    Serial.println(central.address());
  }
}
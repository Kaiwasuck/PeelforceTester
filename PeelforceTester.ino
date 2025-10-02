#include <Arduino.h>
#include "HX711.h"
#include "DRV8834.h"
#include <EEPROM.h>


// EEPROM definitions
#define EEPROM_SCALE 0    // int
#define EEPROM_OFFSET 4   // 16-bit int


// Pin Defenitions
#define DIR 11
#define STEP 10
#define M0 8
#define M1 9
#define DATAPIN 7
#define CLOCKPIN 6
#define UPPERLIMIT 4
#define LOWERLIMIT 5


//////////////////////// Stepper Motor Parameters /////////////////////////////
// MOTOR_STEPS  - Motor steps per revolution. This stepper is 200 steps or 1.8 
//                degrees/step
// RPM          - Rotation/min, change for spd
// MICROSTEPS   - Microstepping Mode:
//                  1 : Full Step, 2: 1/2 step, 4: 1/4 step, 8: 1/8 step, 
//                  16: 1/16 step, 32: 1/32 step
///////////////////////////////////////////////////////////////////////////////
#define MOTOR_STEPS 200
int RPM = 100;
#define MICROSTEPS 1
DRV8834 stepper(MOTOR_STEPS, DIR, STEP, M0, M1);

HX711 myScale;


bool testing = false;
bool resetting = false;
int direction = 1;
int loggingInterval = 1000;
int resetHeight = 1;
bool reachedBottom = false;
unsigned wait_time_micros;
String incomingCommand = ""; // A string to hold incoming data
unsigned long startTime;
bool prevLowerSwitch = false;
bool prevUpperSwitch = false;

void setup() {
  // Initialize Pins
  pinMode(UPPERLIMIT, INPUT);
  pinMode(LOWERLIMIT, INPUT);

  // Initialize Serial
  Serial.begin(115200);
  while (!Serial) {
    delay(50);  // wait for Serial to connect
  }
  Serial.setTimeout(100);
  

  // read scale values from EEPROM
  float scale;
  EEPROM.get(EEPROM_SCALE, scale);
  if (isnan(scale)) scale = 988.453125; //scale value
  int32_t offset;
  EEPROM.get(EEPROM_OFFSET, offset);
  if (isnan(offset)) offset = 525556; //scale value
  // set up scale
  myScale.begin(DATAPIN, CLOCKPIN);
  myScale.set_offset(offset);
  myScale.set_scale(scale);
  myScale.tare();

  // Initialize Stepper
  stepper.begin(RPM, MICROSTEPS);
  Serial.println("Status: Ready");
}


void loop() {
  // motor control loop - send pulse and return how long to wait until next pulse
  wait_time_micros = stepper.nextAction();

  // execute other code in between clock pulses
  if (wait_time_micros > 100){
    serialRead();
    switchLogic();

    if (testing) readScale();
  } else if (wait_time_micros <= 0){
    // if the motor is stopped
    serialRead();
    switchLogic();
  }

}

void switchLogic(){
  bool currLowerSwitch = digitalRead(LOWERLIMIT);
  bool currUpperSwitch = digitalRead(UPPERLIMIT);

  if(!testing && !resetting){    // when idle can use switches to move motor up or down
    if(currLowerSwitch == HIGH && prevLowerSwitch == LOW){
      stepper.startMove(1 * MOTOR_STEPS * MICROSTEPS);
      Serial.println("Status: lowering motor");
    } else if (currUpperSwitch == HIGH && prevUpperSwitch == LOW){
      stepper.startMove(-1 * MOTOR_STEPS * MICROSTEPS);
      Serial.println("Status: raising motor");
    }

  } else if (resetting){     // for resetting back to original position
    if (currLowerSwitch == HIGH && prevLowerSwitch == LOW){
      stepper.stop();
      direction = -1;
      stepper.startMove(direction * resetHeight * MOTOR_STEPS * MICROSTEPS);
      reachedBottom = true;
    }
    if (reachedBottom && wait_time_micros <= 0){
      resetting = false;
      reachedBottom = false;
    }

  } else {              // the code for when the test starts
    // check if stopper was hit
    if (currUpperSwitch == HIGH && prevUpperSwitch == LOW){
      Serial.println("Status: TOP REACHED");
      stepper.stop();
    } else if (currLowerSwitch == HIGH && prevLowerSwitch == LOW){
      Serial.println("Status: BOTTOM REACHED");
      stepper.stop();
    }
  }
  if (prevUpperSwitch != currUpperSwitch)   prevUpperSwitch = currUpperSwitch;
  if (prevLowerSwitch != currLowerSwitch)   prevLowerSwitch = currLowerSwitch;
}

void readScale(){
  // get a scale reading and print to serial every loggingInterval
  if(millis() - myScale.last_time_read() > loggingInterval){
    if(myScale.is_ready()){
      float scaleValue = myScale.get_units(1);
      float force = scaleValue / 1000 * 9.80665; // convert grams to Newtons

      Serial.print(millis()-startTime);
      Serial.print(", ");
      Serial.println(force);
    }
  }
}

void serialRead(){
  if (Serial.available() > 0) {
    incomingCommand = Serial.readStringUntil('\n');
    incomingCommand.trim(); // Remove any whitespace
    
    if (incomingCommand.length() > 0) {
      char commandType = incomingCommand.charAt(0); // Get the command character
      String commandValue = incomingCommand.substring(1); // Get the value after the character

      switch (commandType){
        case 'A': // Start Motor
          testing = true;
          resetting = false;
          direction = -1;
          startTime = millis();
          stepper.startMove(direction * 100 * MOTOR_STEPS * MICROSTEPS);
          Serial.println("Status: Motor started.");
          break;

        case 'B': // Stop Motor
          testing = false;
          resetting = false;
          stepper.stop();
          Serial.println("Status: Motor stopped.");
          break;

        case 'C': // Reset Position
          testing = false;
          resetting = true;
          direction = 1;
          stepper.startMove(direction * 100 * MOTOR_STEPS * MICROSTEPS);
          Serial.println("Status: Motor resetting");
          break;

        case 'D': // calibrate
          testing = false;
          resetting = false;
          stepper.stop();
          Serial.println("Status: Calibrating Load Cell");
          calibrate();
          break;

        case 'R': // Set RPM
          RPM = commandValue.toInt();
          stepper.setRPM(RPM);
          Serial.println("Status: RPM set to " + String(RPM));
          // Add code to update your motor's speed here
          break;

        case 'I': // Set Interval
          loggingInterval = commandValue.toInt();
          Serial.println("Status: Logging interval set to " + String(loggingInterval) + " ms");
          break;
          
        default:
          Serial.println("Error: Unknown command");
          break;
      }
    }
  }
}

void calibrate(){
  Serial.println("\n==========CALIBRATION==========");
  Serial.print("remove all weight from the loadcell");
  //  flush Serial input
  while (Serial.available()) Serial.read();

  Serial.println("and press enter\n");
  while (Serial.available() == 0);

  Serial.println("Determine zero weight offset");
  //  average 20 measurements.
  myScale.tare(20);
  int32_t offset = myScale.get_offset();
  EEPROM.put(EEPROM_OFFSET, offset);
  Serial.print("OFFSET: ");
  Serial.println(offset);
  Serial.println();


  Serial.println("Place a weight on the loadcell and");
  //  flush Serial input
  while (Serial.available()) Serial.read();

  Serial.println("enter the weight in (whole) grams and press enter");
  uint32_t weight = 0;
  while (Serial.peek() != '\n'){
    if (Serial.available()){
      char ch = Serial.read();
      if (isdigit(ch)){
        weight *= 10;
        weight = weight + (ch - '0');
      }
    }
  }
  Serial.print("WEIGHT: ");
  Serial.println(weight);
  myScale.calibrate_scale(weight, 20);
  float scale = myScale.get_scale();
  EEPROM.put(EEPROM_SCALE, scale);

  Serial.print("SCALE:  ");
  Serial.println(scale, 6);

  Serial.print("\nLoad Cell offset set to: ");
  Serial.print(offset);
  Serial.print(" and Load Cell scale set to: ");
  Serial.print(scale, 6);
  Serial.print(");\n\n");

  Serial.println("CALIBRATION: Finished!"); 

}
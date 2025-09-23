/*
 * Example using non-blocking mode to move until a switch is triggered.
 *
 * Copyright (C)2015-2017 Laurentiu Badea
 *
 * This file may be redistributed under the terms of the MIT license.
 * A copy of this license has been included with this distribution in the file LICENSE.
 */
#include <Arduino.h>
#include "HX711.h"

// this pin should connect to Ground when want to stop the motor
#define STOPPER_PIN 4

// Motor steps per revolution. Most steppers are 200 steps or 1.8 degrees/step
#define MOTOR_STEPS 200
#define RPM 100
// Microstepping mode. If you hardwired it to save pins, set to the same value here.
#define MICROSTEPS 1

#define DIR 8
#define STEP 9
#define SLEEP 13 // optional (just delete SLEEP from everywhere if not used)

/*
 * Choose one of the sections below that match your board
 */

#include "DRV8834.h"
#define M0 10
#define M1 11
DRV8834 stepper(MOTOR_STEPS, DIR, STEP, SLEEP, M0, M1);

HX711 myScale;
//  adjust pins if needed.
uint8_t dataPin = 6;
uint8_t clockPin = 7;

// #include "BasicStepperDriver.h" // generic
// BasicStepperDriver stepper(MOTOR_STEPS, DIR, STEP);

void setup() {
    Serial.begin(115200);

    // Configure stopper pin to read HIGH unless grounded
    pinMode(STOPPER_PIN, INPUT_PULLUP);

    stepper.begin(RPM, MICROSTEPS);
    // if using enable/disable on ENABLE pin (active LOW) instead of SLEEP uncomment next line
    // stepper.setEnableActiveState(LOW);
    stepper.enable();
    delay(1000);
    myScale.begin(dataPin, clockPin);

    myScale.set_offset(525556);
    myScale.set_scale(988.453125);
    myScale.tare();

    Serial.println("START");

    

    // set the motor to move continuously for a reasonable time to hit the stopper
    // let's say 100 complete revolutions (arbitrary number)
    stepper.startMove(10 * MOTOR_STEPS * MICROSTEPS);     // in microsteps
    // stepper.startRotate(100 * 360);                     // or in degrees
}

int cycle = 1;
void loop() {
    // first, check if stopper was hit
    if (digitalRead(STOPPER_PIN) == LOW){
        Serial.println("STOPPER REACHED");

        /*
         * Choosing stop() vs startBrake():
         *
         * constant speed mode, they are the same (stop immediately)
         * linear (accelerated) mode with brake, the motor will go past the stopper a bit
         */

        stepper.stop();
        // stepper.startBrake();
    }

    // motor control loop - send pulse and return how long to wait until next pulse
    unsigned wait_time_micros = stepper.nextAction();

    // 0 wait time indicates the motor has stopped
    if (wait_time_micros <= 0) {
        stepper.disable();       // comment out to keep motor powered
        cycle *= -1;
        stepper.startMove(5 * cycle * MOTOR_STEPS * MICROSTEPS);     // in microsteps
    }

    // (optional) execute other code if we have enough time
    if (wait_time_micros > 100){
        if(millis()-myScale.last_time_read() > 1000){
            if(myScale.is_ready()){
                Serial.println(myScale.get_units(5));
            }
        }
    }
}


void calibrate()
{
  Serial.println("\n\nCALIBRATION\n===========");
  Serial.println("remove all weight from the loadcell");
  //  flush Serial input
  while (Serial.available()) Serial.read();

  Serial.println("and press enter\n");
  while (Serial.available() == 0);

  Serial.println("Determine zero weight offset");
  //  average 20 measurements.
  myScale.tare(20);
  int32_t offset = myScale.get_offset();

  Serial.print("OFFSET: ");
  Serial.println(offset);
  Serial.println();


  Serial.println("place a weight on the loadcell");
  //  flush Serial input
  while (Serial.available()) Serial.read();

  Serial.println("enter the weight in (whole) grams and press enter");
  uint32_t weight = 0;
  while (Serial.peek() != '\n')
  {
    if (Serial.available())
    {
      char ch = Serial.read();
      if (isdigit(ch))
      {
        weight *= 10;
        weight = weight + (ch - '0');
      }
    }
  }
  Serial.print("WEIGHT: ");
  Serial.println(weight);
  myScale.calibrate_scale(weight, 20);
  float scale = myScale.get_scale();

  Serial.print("SCALE:  ");
  Serial.println(scale, 6);

  Serial.print("\nuse scale.set_offset(");
  Serial.print(offset);
  Serial.print("); and scale.set_scale(");
  Serial.print(scale, 6);
  Serial.print(");\n");
  Serial.println("in the setup of your project");

  Serial.println("\n\n");
}
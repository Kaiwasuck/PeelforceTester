// Define the pins for the DRV8834 driver
const int STEP_PIN = 5;
const int DIR_PIN = 4;
const int M0_PIN = 6;
const int M1_PIN = 7;

void setup() {
  // Set the pin modes
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(M0_PIN, OUTPUT);
  pinMode(M1_PIN, OUTPUT);
  
  digitalWrite(M0_PIN, LOW);
  digitalWrite(M1_PIN, LOW);

  // Start serial communication for debugging
  Serial.begin(9600);
  Serial.println("Stepper motor control ready.");
}

void loop() {
  // Rotate 200 steps clockwise (one full revolution for a 200-step motor)
  Serial.println("Moving clockwise...");
  moveStepper(200, HIGH, 3000);
  delay(3000); // Wait for 1 second

  // Rotate 200 steps counter-clockwise
  Serial.println("Moving counter-clockwise...");
  moveStepper(200, LOW, 3000);
  delay(3000); // Wait for 1 second
}

/**
 * Moves the stepper motor a specified number of steps.
 * * @param steps The number of steps to move.
 * @param direction The direction of rotation (HIGH for one direction, LOW for the other).
 * @param stepDelay_us The delay in microseconds between steps.
 */
void moveStepper(int steps, int direction, int stepDelay_us) {
  // Set the direction
  digitalWrite(DIR_PIN, direction);
  
  // Loop for the specified number of steps
  for (int i = 0; i < steps; i++) {
    // Pulse the STEP pin to make the motor take one step
    digitalWrite(STEP_PIN, HIGH);
    delayMicroseconds(stepDelay_us);
    digitalWrite(STEP_PIN, LOW);
    delayMicroseconds(stepDelay_us);
  }
}
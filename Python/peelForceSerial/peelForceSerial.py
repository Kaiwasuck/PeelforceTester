# SETUP
# install pyserial using "pip install pyserial" in terminal


import serial
import csv
import datetime
import time

# Update with your serial port and baud rate
# use getPorts.py and copy and paste the Port info below.
SERIAL_PORT = '/dev/cu.usbmodem9888E008AF402'
BAUD_RATE = 9600

# Name of the output CSV file
CSV_FILENAME = 'serial_data_log.csv'

try:
    # Open the serial port connection
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    print(f"Connected to serial port: {SERIAL_PORT}")

    # Open the CSV file and prepare to write data
    with open(CSV_FILENAME, 'a', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)

        # Write the header if the file is new
        if csvfile.tell() == 0:
            csv_writer.writerow(['Timestamp', 'Data'])

        # Start the main loop to read and log data
        while True:
            if ser.in_waiting > 0:
                # Read a full line of data from the serial port
                line = ser.readline().decode('utf-8').strip()

                if line:
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

                    # Log the timestamp and data to the CSV file
                    csv_writer.writerow([timestamp, line])
                    print(f"Logged: {timestamp}, {line}")

            time.sleep(0.01)  # Small delay to prevent busy-waiting

except serial.SerialException as e:
    print(f"Error: Could not open port {SERIAL_PORT} - {e}")
    print("Please check if the device is connected and the correct port is selected.")
except KeyboardInterrupt:
    print("Program terminated by user.")
finally:
    # Ensure the serial port is closed when the program exits
    if 'ser' in locals() and ser.is_open:
        ser.close()
        print("Serial connection closed.")
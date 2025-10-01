import sys
import serial
import serial.tools.list_ports
import csv  # NEW: Import the csv module
from datetime import datetime  # NEW: Import datetime for timestamps
from PySide6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout,
                               QWidget, QTextEdit, QComboBox, QLabel, QHBoxLayout, QFileDialog)  # MODIFIED
from PySide6.QtCore import QThread, Signal, Slot


# --- Serial Communication Worker (No changes here) ---
class SerialWorker(QThread):
    data_received = Signal(str)
    connection_status = Signal(bool)

    def __init__(self, port, baud_rate):
        super().__init__()
        self.port = port
        self.baud_rate = baud_rate
        self.serial_port = None
        self.running = False

    def run(self):
        try:
            self.serial_port = serial.Serial(self.port, self.baud_rate, timeout=1)
            self.running = True
            self.connection_status.emit(True)

            while self.running:
                if self.serial_port.in_waiting > 0:
                    line = self.serial_port.readline().decode('utf-8').strip()
                    if line:
                        self.data_received.emit(line)
        except serial.SerialException as e:
            print(f"Error: {e}")
            self.connection_status.emit(False)
        finally:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
            self.connection_status.emit(False)

    def send_command(self, command):
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.write(command.encode('utf-8'))
            print(f"Sent: {command}")

    def stop(self):
        self.running = False
        self.quit()
        self.wait()


# --- Main GUI Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Peel Force Tester")
        self.setGeometry(100, 100, 450, 400)  # MODIFIED: Slightly wider window

        # Serial worker thread
        self.serial_worker = None

        # NEW: CSV Logging state variables
        self.is_logging = False
        self.csv_file = None
        self.csv_writer = None

        # --- UI Elements ---
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)

        # Port selection
        port_layout = QHBoxLayout()
        self.port_label = QLabel("Serial Port:")
        self.port_combo = QComboBox()
        self.refresh_button = QPushButton("Refresh")
        port_layout.addWidget(self.port_label)
        port_layout.addWidget(self.port_combo)
        port_layout.addWidget(self.refresh_button)
        layout.addLayout(port_layout)

        # Connect/Disconnect button
        self.connect_button = QPushButton("Connect")
        layout.addWidget(self.connect_button)

        # Logging button
        self.log_button = QPushButton("Start Logging")
        self.log_button.setEnabled(False)  # Disabled until connected
        layout.addWidget(self.log_button)

        # Motor control buttons
        self.start_button = QPushButton("Start Motor")
        self.stop_button = QPushButton("Stop Motor")
        self.reset_button = QPushButton("Reset Position")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.reset_button.setEnabled(False)

        # Horizontal layout for control buttons
        control_layout = QHBoxLayout()
        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.stop_button)
        layout.addLayout(control_layout)
        layout.addWidget(self.reset_button)

        # Log display
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        layout.addWidget(self.log_display)

        # --- Connect Signals to Slots (Functions) ---
        self.refresh_button.clicked.connect(self.populate_ports)
        self.connect_button.clicked.connect(self.toggle_connection)
        self.start_button.clicked.connect(self.start_motor)
        self.stop_button.clicked.connect(self.stop_motor)
        self.reset_button.clicked.connect(self.reset_motor)
        self.log_button.clicked.connect(self.toggle_logging)  # NEW

        self.populate_ports()

    def populate_ports(self):
        # ... (no changes in this function)
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(port.device)
        self.log_message("Refreshed serial ports.")

    def toggle_connection(self):
        # ... (no changes in this function)
        if self.serial_worker is None or not self.serial_worker.isRunning():
            selected_port = self.port_combo.currentText()
            if not selected_port:
                self.log_message("Error: No serial port selected.")
                return

            self.connect_button.setText("Connecting...")
            self.serial_worker = SerialWorker(port=selected_port, baud_rate=115200)
            self.serial_worker.data_received.connect(self.log_message)
            self.serial_worker.connection_status.connect(self.on_connection_status_changed)
            self.serial_worker.start()
        else:
            self.serial_worker.stop()

    @Slot(bool)
    def on_connection_status_changed(self, is_connected):
        if is_connected:
            self.connect_button.setText("Disconnect")
            self.log_message(f"Successfully connected to {self.serial_worker.port}.")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(True)
            self.reset_button.setEnabled(True)
            self.log_button.setEnabled(True)  # MODIFIED: Enable logging button
            self.port_combo.setEnabled(False)
            self.refresh_button.setEnabled(False)
        else:
            if self.is_logging:  # MODIFIED: Stop logging on disconnect
                self.toggle_logging()
            self.connect_button.setText("Connect")
            self.log_message("Disconnected.")
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(False)
            self.reset_button.setEnabled(False)
            self.log_button.setEnabled(False)  # MODIFIED: Disable logging button
            self.port_combo.setEnabled(True)
            self.refresh_button.setEnabled(True)
            if self.serial_worker:
                self.serial_worker = None

    # NEW: Function to handle starting and stopping the CSV log
    def toggle_logging(self):
        if not self.is_logging:
            # Open file dialog to choose where to save the file
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Log File", "", "CSV Files (*.csv);;All Files (*)")

            if file_path:
                try:
                    self.csv_file = open(file_path, 'w', newline='', encoding='utf-8')
                    self.csv_writer = csv.writer(self.csv_file)
                    # Write header
                    self.csv_writer.writerow(['Timestamp', 'Message'])
                    self.is_logging = True
                    self.log_button.setText("Stop Logging")
                    self.log_message(f"Logging started to: {file_path}")
                except Exception as e:
                    self.log_message(f"Error opening file: {e}")
        else:
            # Stop logging
            if self.csv_file:
                self.csv_file.close()
                self.csv_file = None
                self.csv_writer = None

            self.is_logging = False
            self.log_button.setText("Start Logging")
            self.log_message("Logging stopped.")

    def start_motor(self):
        # ... (no changes in this function)
        if self.serial_worker:
            self.serial_worker.send_command("A\n")
            self.log_message("Command: START sent.")

    def stop_motor(self):
        # ... (no changes in this function)
        if self.serial_worker:
            self.serial_worker.send_command("B\n")
            self.log_message("Command: STOP sent.")

    def reset_motor(self):
        #
        if self.serial_worker:
            self.serial_worker.send_command("C\n")
            self.log_message("Command: STOP sent.")

    @Slot(str)
    def log_message(self, message):
        self.log_display.append(message)

        # MODIFIED: Write to CSV if logging is active
        # MODIFIED - Parse the message before writing to CSV
        if self.is_logging and self.csv_writer:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

            # Split the incoming message by the comma
            parsed_data = message.split(',')

            # Check if the message is in the expected "data,data" format
            if len(parsed_data) == 2:
                # Create a new row with the timestamp plus the split data
                # .strip() removes any accidental whitespace
                row = [timestamp] + [item.strip() for item in parsed_data]
                self.csv_writer.writerow(row)
            else:
                # If the message is not data (e.g., "Status: Motor started"),
                # log it in the second column and leave the rest blank.
                self.csv_writer.writerow([timestamp, message, ''])

    def closeEvent(self, event):
        # MODIFIED: Ensure logging is stopped and file is closed on exit
        if self.is_logging:
            self.toggle_logging()
        if self.serial_worker and self.serial_worker.isRunning():
            self.serial_worker.stop()
        event.accept()


# --- Run the Application ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
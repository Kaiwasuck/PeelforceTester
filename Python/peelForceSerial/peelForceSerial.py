import csv
import sys
import json  # NEW
from datetime import datetime
from pathlib import Path

import serial
import serial.tools.list_ports
from PySide6.QtCore import QThread, Signal, Slot
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout,
                               QWidget, QTextEdit, QComboBox, QLabel, QHBoxLayout,
                               QFileDialog, QLineEdit, QDialog)


class CalibrationDialog(QDialog):
    def __init__(self, serial_worker, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scale Calibration")
        self.serial_worker = serial_worker
        self.setMinimumSize(450, 350)
        layout = QVBoxLayout(self)
        self.instructions = QLabel("Follow the instructions from the device below.")
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.input_label = QLabel("Your Input (press Enter to send):")
        self.user_input = QLineEdit()
        self.finish_button = QPushButton("Finish")
        self.finish_button.setAutoDefault(False)
        layout.addWidget(self.instructions)
        layout.addWidget(self.log)
        layout.addWidget(self.input_label)
        layout.addWidget(self.user_input)
        layout.addWidget(self.finish_button)
        self.finish_button.clicked.connect(self.close)
        self.user_input.returnPressed.connect(self.send_input_to_arduino)

    def start_calibration(self):
        self.serial_worker.data_received.connect(self.handle_serial_data)
        self.serial_worker.send_command("D\n")
        self.user_input.setFocus()
        self.show()

    def handle_serial_data(self, message):
        self.log.append(message)
        if "Finished!" in message:
            self.instructions.setText("You can now close this window.")
            self.user_input.setEnabled(False)

    def send_input_to_arduino(self):
        text_to_send = self.user_input.text()
        self.log.append(f">>> {text_to_send}")
        self.serial_worker.send_command(f"{text_to_send}\n")
        self.user_input.clear()

    def closeEvent(self, event):
        try:
            self.serial_worker.data_received.disconnect(self.handle_serial_data)
        except RuntimeError:
            pass
        super().closeEvent(event)


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
        self.setGeometry(100, 100, 450, 500)
        self.serial_worker = None
        self.motor_is_running = False
        self.csv_file = None
        self.csv_writer = None

        # --- Settings Management ---
        self.settings_file = Path.home() / ".peel_force_tester_settings.json"
        self.save_directory = str(Path.home() / "Downloads")  # Default value
        self.load_settings()  # Load saved settings on startup

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)
        layout.setSpacing(10)

        port_layout = QHBoxLayout()
        self.port_label = QLabel("Serial Port:")
        self.port_combo = QComboBox()
        self.refresh_button = QPushButton("Refresh")
        port_layout.addWidget(self.port_label)
        port_layout.addWidget(self.port_combo)
        port_layout.addWidget(self.refresh_button)
        layout.addLayout(port_layout)
        self.connect_button = QPushButton("Connect")
        layout.addWidget(self.connect_button)
        self.int_validator = QIntValidator()
        rpm_layout = QHBoxLayout()
        self.rpm_label = QLabel("Motor RPM:")
        self.rpm_input = QLineEdit("100")
        self.rpm_input.setValidator(self.int_validator)
        self.set_rpm_button = QPushButton("Set RPM")
        rpm_layout.addWidget(self.rpm_label)
        rpm_layout.addWidget(self.rpm_input)
        rpm_layout.addWidget(self.set_rpm_button)
        layout.addLayout(rpm_layout)
        interval_layout = QHBoxLayout()
        self.interval_label = QLabel("Logging Interval (ms) [fastest = 100 ms]:")
        self.interval_input = QLineEdit("1000")
        self.interval_input.setValidator(self.int_validator)
        self.set_interval_button = QPushButton("Set Interval")
        interval_layout.addWidget(self.interval_label)
        interval_layout.addWidget(self.interval_input)
        interval_layout.addWidget(self.set_interval_button)
        layout.addLayout(interval_layout)
        save_layout = QHBoxLayout()
        self.save_location_button = QPushButton("Set Save Location")
        self.calibrate_button = QPushButton("Calibrate Scale")
        save_layout.addWidget(self.save_location_button)
        save_layout.addWidget(self.calibrate_button)
        layout.addLayout(save_layout)
        self.save_location_label = QLabel(f"Saving to: {self.save_directory}")
        self.save_location_label.setWordWrap(True)
        layout.addWidget(self.save_location_label)
        self.start_button = QPushButton("Start Motor")
        self.stop_button = QPushButton("Stop Motor")
        self.reset_button = QPushButton("Reset Position")
        self.controls = [self.rpm_input, self.set_rpm_button, self.interval_input, self.set_interval_button,
                         self.save_location_button, self.calibrate_button, self.start_button, self.stop_button,
                         self.reset_button]
        for control in self.controls:
            control.setEnabled(False)
        control_layout = QHBoxLayout()
        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.stop_button)
        layout.addLayout(control_layout)
        layout.addWidget(self.reset_button)
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        layout.addWidget(self.log_display)
        self.refresh_button.clicked.connect(self.populate_ports)
        self.connect_button.clicked.connect(self.toggle_connection)
        self.start_button.clicked.connect(self.start_motor)
        self.stop_button.clicked.connect(self.stop_motor)
        self.reset_button.clicked.connect(self.reset_motor)
        self.save_location_button.clicked.connect(self.select_save_location)
        self.set_rpm_button.clicked.connect(self.set_rpm)
        self.set_interval_button.clicked.connect(self.set_interval)
        self.calibrate_button.clicked.connect(self.open_calibration_dialog)
        self.populate_ports()

    # --- Functions to load and save settings ---
    def load_settings(self):
        try:
            with open(self.settings_file, 'r') as f:
                settings = json.load(f)
                # Ensure the loaded path is a valid directory, otherwise keep default
                saved_path = settings.get("save_directory", self.save_directory)
                if Path(saved_path).is_dir():
                    self.save_directory = saved_path
        except (FileNotFoundError, json.JSONDecodeError):
            # File doesn't exist or is empty/corrupt, use defaults
            pass

    def save_settings(self):
        settings = {
            "save_directory": self.save_directory
        }
        with open(self.settings_file, 'w') as f:
            json.dump(settings, f, indent=4)

    def select_save_location(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Save Folder", self.save_directory)
        if directory:
            self.save_directory = directory
            self.save_location_label.setText(f"Saving to: {self.save_directory}")

    def closeEvent(self, event):
        self.save_settings()  # Save settings before closing
        if self.motor_is_running:
            self.stop_motor()
        if self.serial_worker and self.serial_worker.isRunning():
            self.serial_worker.stop()
        event.accept()

    @Slot(str)
    def log_message(self, message):
        if message.startswith("R:") and ",I:" in message:
            self.log_display.append(f"Received Settings: {message}")
            try:
                parts = message.split(',')
                rpm_part = parts[0].split(':')[1]
                interval_part = parts[1].split(':')[1]
                self.rpm_input.setText(rpm_part)
                self.interval_input.setText(interval_part)
            except IndexError:
                self.log_display.append("Error: Could not parse settings from Arduino.")
            return

        self.log_display.append(message)

        if self.motor_is_running and self.csv_writer:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            parsed_data = message.split(',')
            if len(parsed_data) == 2:
                row = [timestamp] + [item.strip() for item in parsed_data]
                self.csv_writer.writerow(row)
            elif ',' in message:
                self.csv_writer.writerow([timestamp, message, ''])

    def start_motor(self):
        if not self.serial_worker or self.motor_is_running:
            return
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"peel_test_{timestamp}.csv"
        full_path = Path(self.save_directory) / filename
        try:
            self.csv_file = open(full_path, 'w', newline='', encoding='utf-8')
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow(['Timestamp', 'Time Since Start (ms)', 'Force (N)'])
            self.serial_worker.send_command("A\n")
            self.log_message(f"Motor started. Logging to: {full_path}")
            self.motor_is_running = True
        except Exception as e:
            self.log_message(f"ERROR: Could not create log file. {e}")
            self.csv_file = None
            self.csv_writer = None

    def stop_motor(self):
        if not self.serial_worker or not self.motor_is_running:
            return
        self.serial_worker.send_command("B\n")
        self.log_message("Motor stopped.")
        if self.csv_file:
            self.csv_file.close()
            self.log_message("Log file saved.")
        self.motor_is_running = False
        self.csv_file = None
        self.csv_writer = None

    def open_calibration_dialog(self):
        if self.serial_worker:
            try:
                self.serial_worker.data_received.disconnect(self.log_message)
            except RuntimeError:
                pass
            dialog = CalibrationDialog(self.serial_worker, self)
            dialog.finished.connect(lambda: self.serial_worker.data_received.connect(self.log_message))
            dialog.start_calibration()

    @Slot(bool)
    def on_connection_status_changed(self, is_connected):
        if is_connected:
            self.connect_button.setText("Disconnect")
            self.log_message(f"Successfully connected to {self.serial_worker.port}.")
            for control in self.controls:
                control.setEnabled(True)
            self.port_combo.setEnabled(False)
            self.refresh_button.setEnabled(False)
            self.serial_worker.data_received.connect(self.log_message)
            self.serial_worker.send_command("S\n")
        else:
            if self.motor_is_running: self.stop_motor()
            self.connect_button.setText("Connect")
            self.log_message("Disconnected.")
            for control in self.controls:
                control.setEnabled(False)
            self.port_combo.setEnabled(True)
            self.refresh_button.setEnabled(True)
            if self.serial_worker:
                try:
                    self.serial_worker.data_received.disconnect(self.log_message)
                except RuntimeError:
                    pass
                self.serial_worker = None

    def populate_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports: self.port_combo.addItem(port.device)
        self.log_message("Refreshed serial ports.")

    def toggle_connection(self):
        if self.serial_worker is None or not self.serial_worker.isRunning():
            selected_port = self.port_combo.currentText()
            if not selected_port: return
            self.connect_button.setText("Connecting...")
            self.serial_worker = SerialWorker(port=selected_port, baud_rate=115220)
            self.serial_worker.connection_status.connect(self.on_connection_status_changed)
            self.serial_worker.start()
        else:
            self.serial_worker.stop()

    def set_rpm(self):
        if self.serial_worker and self.rpm_input.text():
            self.serial_worker.send_command(f"R{self.rpm_input.text()}\n")

    def set_interval(self):
        if self.serial_worker and self.interval_input.text():
            self.serial_worker.send_command(f"I{self.interval_input.text()}\n")

    def reset_motor(self):
        if self.serial_worker: self.serial_worker.send_command("C\n")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
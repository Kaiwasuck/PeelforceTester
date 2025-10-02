import csv
import sys
from datetime import datetime

import serial
import serial.tools.list_ports
from PySide6.QtCore import QThread, Signal, Slot
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout,
                               QWidget, QTextEdit, QComboBox, QLabel, QHBoxLayout,
                               QFileDialog, QLineEdit, QDialog) 


# --- Calibration Dialog Box ---
class CalibrationDialog(QDialog):
    def __init__(self, serial_worker, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scale Calibration")
        self.serial_worker = serial_worker
        self.setMinimumSize(450, 350)

        # UI Elements
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

        # Connect signals
        self.finish_button.clicked.connect(self.close)
        self.user_input.returnPressed.connect(self.send_input_to_arduino)

    def start_calibration(self):
        # Temporarily route all serial data to this dialog
        self.serial_worker.data_received.connect(self.handle_serial_data)
        self.serial_worker.send_command("D\n")  # 'D' is calibrate command
        self.user_input.setFocus()  # Make it easy to start typing
        self.show()

    def handle_serial_data(self, message):
        self.log.append(message)
        if "Finished!" in message:
            self.instructions.setText("You can now close this window.")
            self.user_input.setEnabled(False)

    def send_input_to_arduino(self):
        text_to_send = self.user_input.text()
        self.log.append(f">>> {text_to_send}")  # Show user what they sent
        self.serial_worker.send_command(f"{text_to_send}\n")
        self.user_input.clear()

    def closeEvent(self, event):
        # IMPORTANT: Disconnect our handler so the main window gets data again
        try:
            self.serial_worker.data_received.disconnect(self.handle_serial_data)
        except RuntimeError:
            pass  # Signal was already disconnected
        super().closeEvent(event)


# --- Serial Worker  ---
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
        self.is_logging = False
        self.csv_file = None
        self.csv_writer = None
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

        action_layout = QHBoxLayout()
        self.log_button = QPushButton("Start Logging")
        self.calibrate_button = QPushButton("Calibrate Scale")  # NEW BUTTON
        action_layout.addWidget(self.log_button)
        action_layout.addWidget(self.calibrate_button)
        layout.addLayout(action_layout)

        self.start_button = QPushButton("Start Motor")
        self.stop_button = QPushButton("Stop Motor")
        self.reset_button = QPushButton("Reset Position")
        self.controls = [self.rpm_input, self.set_rpm_button, self.interval_input, self.set_interval_button,
                         self.log_button, self.calibrate_button, self.start_button, self.stop_button, self.reset_button]
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
        self.log_button.clicked.connect(self.toggle_logging)
        self.set_rpm_button.clicked.connect(self.set_rpm)
        self.set_interval_button.clicked.connect(self.set_interval)
        self.calibrate_button.clicked.connect(self.open_calibration_dialog)  # Connect the new button
        self.populate_ports()

    def open_calibration_dialog(self):
        if self.serial_worker:
            # Temporarily disconnect the main log while the dialog is open
            try:
                self.serial_worker.data_received.disconnect(self.log_message)
            except RuntimeError:
                pass  # Already disconnected
            dialog = CalibrationDialog(self.serial_worker, self)
            # Reconnect the main log when the dialog closes
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
        else:
            if self.is_logging: self.toggle_logging()
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

    @Slot(str)
    def log_message(self, message):
        self.log_display.append(message)
        if self.is_logging and self.csv_writer:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            parsed_data = message.split(',')
            if len(parsed_data) == 2:
                row = [timestamp] + [item.strip() for item in parsed_data]
                self.csv_writer.writerow(row)
            else:
                if ',' in message:
                    self.csv_writer.writerow([timestamp, message, ''])

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
            self.serial_worker = SerialWorker(port=selected_port, baud_rate=115200)
            self.serial_worker.connection_status.connect(self.on_connection_status_changed)
            self.serial_worker.start()
        else:
            self.serial_worker.stop()

    def toggle_logging(self):
        if not self.is_logging:
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Log File", "", "CSV Files (*.csv);;All Files (*)")
            if file_path:
                self.csv_file = open(file_path, 'w', newline='', encoding='utf-8')
                self.csv_writer = csv.writer(self.csv_file)
                self.csv_writer.writerow(['Timestamp', 'Position', 'Force'])
                self.is_logging = True
                self.log_button.setText("Stop Logging")
        else:
            if self.csv_file: self.csv_file.close()
            self.is_logging = False
            self.log_button.setText("Start Logging")

    def set_rpm(self):
        if self.serial_worker and self.rpm_input.text():
            self.serial_worker.send_command(f"R{self.rpm_input.text()}\n")

    def set_interval(self):
        if self.serial_worker and self.interval_input.text():
            self.serial_worker.send_command(f"I{self.interval_input.text()}\n")

    def start_motor(self):
        if self.serial_worker: self.serial_worker.send_command("A\n")

    def stop_motor(self):
        if self.serial_worker: self.serial_worker.send_command("B\n")

    def reset_motor(self):
        if self.serial_worker: self.serial_worker.send_command("C\n")

    def closeEvent(self, event):
        if self.is_logging: self.toggle_logging()
        if self.serial_worker and self.serial_worker.isRunning(): self.serial_worker.stop()
        event.accept()


# --- Run the Application ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
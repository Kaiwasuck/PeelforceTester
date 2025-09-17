import serial.tools.list_ports


def get_serial_ports():
    # Get a list of available serial ports
    ports = serial.tools.list_ports.comports()

    if not ports:
        print("No serial ports found.")
        return []

    print("Available serial ports:")
    for port, desc, hwid in sorted(ports):
        print(f"  Port: {port}")
        print(f"  Description: {desc}")
        print(f"  Hardware ID: {hwid}")
        print("-" * 20)

    return [port.device for port in ports]


if __name__ == "__main__":
    get_serial_ports()
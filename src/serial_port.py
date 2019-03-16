""" Serial port configuration
"""

import serial


class serial_port:
    def __init__(self, port=0, baudrate=19200):
        self.ser = serial.Serial(
            port=port,  # number of device, numbering starts at
            baudrate=baudrate,  # baudrate
            bytesize=8,  # number of databits
            parity=serial.PARITY_NONE,  # enable parity checking
            stopbits=serial.STOPBITS_ONE,  # number of stopbits
            timeout=0.5,  # set a timeout value, None for waiting forever
            xonxoff=0,  # enable software flow control
            rtscts=0,  # enable RTS/CTS flow control
        )

# Python Serial Monitor

Simple Python script to print / log the output from a serial line (e.g. from a embedded device).

Works with Python 2.7 and Python 3.x. Needs pySerial >= version 2.7.

## Usage examples

Monitor serial port `/dev/ttyACM0` at 9600 baud, just print what was received:

    python pysermon.py

Monitor different port at different baudrate:

    python pysermon.py -p /dev/ttyUSB0 -b 115200

Use the `line` formatter, add a timestamp at the beginning of each line:

    python pysermon.py -p /dev/ttyUSB0 -b 115200 -f line -t

Add some color:

    python pysermon.py -p /dev/ttyUSB0 -b 115200 -f line -t -c

Also write to a file (file always is written without color):

    python pysermon.py -p /dev/ttyUSB0 -b 115200 -f line -t -c -l output.log

Use the 'hex' formatter with ASCII representation (`-a`):

    python pysermon.py -p /dev/ttyUSB0 -b 115200 -f hex -a -t -c

If serial port is not available, wait until it shows up, then connect and monitor:

    python pysermon.py -p /dev/ttyUSB0 -b 115200 -w

Also if serial port gets lost while monitoring, restart and try to connect again:

    python pysermon.py -p /dev/ttyUSB0 -b 115200 -w --persist

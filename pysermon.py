##
# The MIT License (MIT)
#
# Copyright (c) 2017 Stefan Wendler
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
##

"""
Python Serial Monitor

Simple Python script to print / log the output from a serial line (e.g. from a embedded device).

Works with Python 2.7 and Python 3.x. Needs pySerial >= version 2.7.

Usage examples

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
"""

VERSION = "0.1.0"

import serial
import serial.tools.list_ports
import sys
import json
import time
import argparse
import os


quiet = False
color = False


class Reader(object):
    """
    Base class for a reader
    """

    def __init__(self, stream):
        self.stream = stream

    def read(self):
        return self.stream.read()


class Writer(object):
    """
    Base class for a writer
    """

    def __init__(self, stream):

        self.stream = stream
        self.add_timestamp = True
        self.with_color = True
        self.log_stream = None

    def write(self, data):

        self.stream.write(data)
        self.stream.flush()

        self.__log(data)

    def _write_meta(self, data):

        if self.with_color:
            self.stream.write("\033[0;34m| \033[0;32m" + data + "\033[0;m\n")
        else:
            self.stream.write("| " + data + "\n")

        self.stream.flush()

        self.__log("| " + data + "\n")

    def _write_timestamp(self):

        if self.add_timestamp:

            if self.with_color:
                self.stream.write("\033[0;35m%18.7f \033[0;34m|\033[0;m " % time.time())
            else:
                self.stream.write("%18.7f | " % time.time())

            self.__log("%18.7f | " % time.time())

    def __log(self, data):

        if self.log_stream is not None and not self.log_stream.closed:
            self.log_stream.write(data)
            self.log_stream.flush()


class SerialReader(Reader):
    """
    Serial reader implementation
    """

    def __init__(self, stream):

        Reader.__init__(self, stream)


    def read(self):
        return Reader.read(self)


class RawWriter(Writer):
    """
    Raw writer implementation

    Just print what was returned by the reader
    """

    def __init__(self, stream):
        Writer.__init__(self, stream)

    def write(self, data):
        Writer.write(self, data.decode('utf-8', errors='ignore'))


class LineWriter(Writer):
    """
    Line based writer
    """

    def __init__(self, stream):
        Writer.__init__(self, stream)

        self.first = True

    @staticmethod
    def __chr(c):

        if sys.version_info.major == 3:
            return chr(c)
        else:
            return c

    def write(self, data):

        for c in data:

            if self.first:
                self._write_timestamp()
                self.first = False

            Writer.write(self, self.__chr(c))

            if self.__chr(c) == '\n':
                self._write_timestamp()


class HexWriter(Writer):
    """
    Hex writer

    Write bytes from reader in hex. Optionally add ASCII representation.
    """

    def __init__(self, stream):

        Writer.__init__(self, stream)

        self.write_ascii = True
        self.current_line = bytearray()
        self.current_length = 0
        self.max_length = 16

    def __del__(self):

        self.__write_ascii()

    def __write_ascii(self):

        if self.write_ascii:

            if self.current_length < self.max_length:
                Writer.write(self, "   " * (self.max_length - self.current_length))

            Writer._write_meta(self, "%s" %
                               self.current_line.decode('ascii', errors='ignore').replace('\n', '').replace('\r', ''))

            self.current_line = bytearray()

        else:

            Writer.write(self, '\n')

    @staticmethod
    def __ord(c):

        if sys.version_info.major == 3:
            return c
        else:
            return ord(c)

    def write(self, data):

        for c in data:

            if self.current_length == 0:
                self._write_timestamp()

            Writer.write(self, "%02X " % self.__ord(c))

            if self.write_ascii:
                self.current_line.append(c)

            self.current_length += 1

            if self.current_length == self.max_length:

                self.__write_ascii()
                self.current_length = 0


class Monitor(object):
    """
    Serial monitor

    Reads from a reader and passes the result to a writer.
    """

    def __init__(self, reader, writer):

        self.reader = reader
        self.writer = writer

    def monitor(self):

        while True:

            data = self.reader.read()

            if data is not None and len(data):
                self.writer.write(data)


def list_ports():

    ports = serial.tools.list_ports.comports()

    if serial.VERSION.startswith("3."):
        return {"ports": [{"device": p.device, "description": p.description} for p in ports]}
    else:
        return {"ports": [{"device": p[0], "description": p[1]} for p in ports]}

def open_port(port, baudrate):

    try:
        port = serial.Serial(port=port, baudrate=baudrate)
    except OSError:
        return None
    except serial.serialutil.SerialException:
        return None

    return port


def xprint(message, error=False):

    global quiet
    global color

    if not quiet:
        if color:
            if error:
                print("\033[1;31m" + message + "\033[1;m")
            else:
                print("\033[1;32m" + message + "\033[1;m")
        else:
            print(message)

def main():

    global quiet
    global color

    parser = argparse.ArgumentParser(description='Python Serial Monitor %s' % VERSION)

    parser.add_argument("-p", "--port", default="/dev/ttyACM0",
                        help="Serial port")

    parser.add_argument("-b", "--baudrate", type=int, default=9600,
                        help="Serial baudrate")

    parser.add_argument("-l", "--log", default=None,
                        help="If a file is given, also write the received data to this log")

    parser.add_argument("-f", "--format", default='raw', choices=['raw', 'line', 'hex'],
                        help="Output format")

    parser.add_argument("-w", "--wait", default=False, action="store_true",
                        help="If given serial port is not available, wait until it shows up")

    parser.add_argument("-c", "--color", default=False, action="store_true",
                        help="Use color for output")

    parser.add_argument("-t", "--timestamp", default=False, action="store_true",
                        help="Add a timestamp to each line")

    parser.add_argument("-a", "--ascii", default=False, action="store_true",
                        help="Add ASCII representation on HEX output")

    parser.add_argument("-q", "--quiet", default=False, action="store_true",
                        help="Print nothing but serial log (no status or error messages)")

    parser.add_argument("--hexbytes", default=16, type=int,
                        help="Number of bytes displayed in each line when HEX format is choosen")

    parser.add_argument("--listjson", default=False, action="store_true",
                        help="List of available serial ports in JSON format")

    parser.add_argument("--list", default=False, action="store_true",
                        help="List of available serial ports")

    parser.add_argument("--persist", default=False, action="store_true",
                        help="Restart and try to reconnect if serial connection drops")

    parser.add_argument("--version", default=False, action="store_true",
                        help="Print version")

    args = parser.parse_args()


    quiet = args.quiet
    color = args.color

    if args.version:
        print("Python Serial Monitor %s" % VERSION)
        exit(0)

    if args.listjson:

        print(json.dumps(list_ports()))
        exit(0)

    if args.list:

        print("")
        print("Available serial ports:")

        for p in list_ports()["ports"]:
            print(" * % -20s: %s" % (p["device"], p["description"]))

        print("")

        exit(0)

    xprint("Trying to connect to %s" % args.port)

    dots = False

    while True:
        istream = open_port(args.port, args.baudrate)

        if istream is not None or not args.wait:
            break

        if not quiet:
            sys.stdout.write(".")
            sys.stdout.flush()
        dots = True
        time.sleep(0.5)

    if dots:
        xprint("")

    if istream is not None:
        xprint("Successfully connected")
    else:
        xprint("Failed to connect", True)
        exit(1)

    ostream = sys.stdout
    reader = SerialReader(istream)

    if args.format == 'line':

        writer = LineWriter(ostream)

    elif args.format == 'hex':

        writer = HexWriter(ostream)
        writer.max_length = args.hexbytes
        writer.write_ascii = args.ascii

    else:

        writer = RawWriter(ostream)

    writer.add_timestamp = args.timestamp
    writer.with_color = args.color

    if args.log is not None:
        try:
            writer.log_stream = open(args.log, "w+")
        except Exception as e:
            xprint("Failed to open logfile: %s" % e, True)
            exit(1)

    monitor = Monitor(reader, writer)

    try:
        monitor.monitor()
    except serial.serialutil.SerialException:
        xprint("")
        xprint("*** He's dead, Jim! ***", True)
        xprint("")
        if args.persist:
            os.execve(sys.executable, [sys.executable] + sys.argv, os.environ)
        else:
            exit(1)


if __name__ == "__main__":

    try:
        main()
    except KeyboardInterrupt:
        xprint("")

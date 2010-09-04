import logging, binascii, struct, crcmod
from StringIO import StringIO
LOG = logging.getLogger(__name__)
LOG.addHandler(logging.StreamHandler())
LOG.setLevel(logging.DEBUG)

import serial

PORT = 'COM3'
BAUDRATE = 9600



"""
With crcmod, we can perform the correct checksums using these values:

crc16 = crcmod.Crc(0x11021, 0xffff, False)
>>> checksum = crc16.new()
>>> checksum.update(sample)
>>> checksum.digest()
'\x05X'
>>> checksum.hexdigest()
'0558'
>>> 
"""
def hex_to_int(h):
    """Convert a hex string to an integer.

    The hex string can be any length. It can start with an 0x, or not.
    Unrecognized characters will raise a ValueError.

    This function released into the public domain by it's author, Lion
    Kimbro.
    """
    num = 0  # Resulting integer
    h = h.lower()  # Hex string
    if h[:2] == "0x":
        h = h[2:]
    for c in h:  # Hex character
        num *= 16
        if "0" <= c <= "9":
            num += ord(c) - ord("0")
        elif "a" <= c <= "f":
            num += ord(c) - ord("a") + 10
        else:
            raise ValueError(c)
    return num

class Cmd(object):
    STX = '\x02'
    ETX = '\x03'
    _command = None
    _crc16 = crcmod.Crc(0x11021, 0xffff, False)
    
    def _checksum(self, bytes):
        crc = self._crc16.new()
        crc.update(bytes)
        return "%s\x%s\x%s" % (bytes, crc.hexdigest()[0:1],crc.hexdigest()[2:3])
    
    def __str__(self):
        return self._checksum("%s%s%s" % (self.STX, self._command ,self.ETX))

class DisconnectCmd(Cmd):
    _command = '\x06\x08'

class VersionStringCmd(Cmd):
    _command = '\x09\x00\x05\x0D\x02'

class GetRecordCmd(Cmd):
    _command = '\x02\x0A\x03\x05\x1F'
    def __init__(self, id):
        self._command += struct.pack('=H', int(id))
        
class Client(object):
    _connection = None
    
    def __init__(self, port=None):
        self._connect(port)
    def __del__(self):
        self._disconnect()
    def _connect(self, port=None):
        if port:
            self._connection = serial.Serial(port, interCharTimeout=0.01, 
                                             timeout=0.1)
        else:
            for port in range(100):
                try:
                    self._connection = serial.Serial(port,interCharTimeout=0.01, 
                                                     timeout=0.1)
                except serial.SerialException, e:
                    LOG.debug(e)
                    self._connection = None
                if self._connection: break
        
        LOG.info("Got connection on %s" % self._connection.name)
        # reset the connection to put the device in an assured state
        self._disconnect()
                
    def get_sw_version(self):pass
    def _disconnect(self):
        self._connection.write(DisconnectCmd())
    def get_record(self, id):pass
    def get_record_count(self):pass
    def get_serial(self):pass
    

class Command(object):
    STX = '\x02'
    ETX = '\x03'
    
    _command = ()
    _mack = ()
    _ack = ()
    
    @property
    def req(self):
        return ''.join([chr(b) for b in self._command])
    @property
    def mack(self):
        return ''.join([chr(b) for b in self._mack])
    @property
    def ack(self):
        return ''.join([chr(b) for b in self._ack])
    def run(self):
        SER.write(self.req)
        resp = SER.read(len(self.mack))
        if resp != self.mack: LOG.warn("meter's ack is unexpected")
        response = SER.readall()
        response = response[response.find(chr(self.STX)):response.find(chr(self.ETX))][self._skip:]
        if self.ack:
            SER.write(self.ack)
        return response
    
class Disconnect(Command):
    _command = (Command.STX,0x06,0x08,Command.ETX,0xC2,0x62)
    _mack = (Command.STX,0x06,0x0C,Command.ETX,0x06,0xAE)
    _skip = 0

class VersionString(Command):
    _command = (Command.STX,0x09,0x00,0x05,0x0D,0x02,Command.ETX,0xDA,0x71)
    _mack = (Command.STX,0x06,0x06,Command.ETX,0xCD,0x41)
    _ack = (Command.STX,0x06,0x07,Command.ETX,0xFC,0x72)
    _skip = 6

class SerialNumber(Command):
    _command = (Command.STX,0x12,0x00,0x05,0x0B,0x02,0x00,0x00,0x00,0x00,0x84,0x6A,0xE8,0x73,0x00,Command.ETX,0x9B,0xEA)
    _mack = (Command.STX,0x06,0x06,Command.ETX,0xCD,0x41)
    _ack = (Command.STX,0x06,0x07,Command.ETX,0xFC,0x72)
    _skip = 5

class RecordCount(Command):
    _command = (Command.STX,0x0A,0x00,0x05,0x1F,0xF5,0x01,Command.ETX,0x38,0xAA)
    _mack = (Command.STX,0x06,0x06,Command.ETX,0xCD,0x41)
    _ack = (Command.STX,0x06,0x07,Command.ETX,0xFC,0x72)
    _skip = 5

class GetRecord(Command):
    _command = '\x02\x0A\x03\x05\x1F{id}\x03{crc_hi}{crc_lo}'
    _mack = ()
    _ack = ()
    _skip = ()
    def run(self, id):
        id = struct.pack('=H', int(id))
        
        
"""
>>> rec_fmt = '1I 1I0'
>>> data = '\x02\x10\x01\x05\x06\x08\x30\x71\x47\x4F\x00\x00\x00\x03\x58\x05'
>>> struct.unpack(rec_fmt, data[5:13])
(1198600200, 79)
>>> datetime.datetime.fromtimestamp(1198600200)
datetime.datetime(2007, 12, 25, 11, 30)
>>> datetime.datetime.fromtimestamp(1198600200).isoformat()
'2007-12-25T11:30:00'
"""

"""
>>> rec_fmt = '=5BII3B'
>>> struct.unpack(rec_fmt, data)
(2, 16, 1, 5, 6, 1198600200, 351, 3, 88, 5)
"""

def run():
    Client()
def run_():
    
    LOG.debug('(Dis)Connecting.')
    c = Disconnect()
    c.run()
    LOG.debug('Ok.')
    
    LOG.debug('Version String:')
    c = VersionString()
    LOG.info(c.run())
    LOG.debug('Ok.')
    
    LOG.debug('Serial:')
    c = SerialNumber()
    LOG.info(c.run())
    LOG.debug('Ok.')
    
    LOG.debug('Record Count:')
    c = RecordCount()
    LOG.info(hex_to_int(''.join([binascii.hexlify(h) for h in c.run()])))
    LOG.debug('Ok.')
    
    LOG.debug('Disconnecting.')
    c = Disconnect()
    c.run()
    LOG.debug('Ok.')
    return 0
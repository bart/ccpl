import time
import adafruit_bus_device.i2c_device as i2c_device
import struct

# BMP180 default address.
BMP180_I2CADDR           = 0x77

# Operating Modes
BMP180_ULTRALOWPOWER     = 0
BMP180_STANDARD          = 1
BMP180_HIGHRES           = 2
BMP180_ULTRAHIGHRES      = 3

# BMP180 Registers
BMP180_CAL_AC1           = 0xAA  # R   Calibration data (16 bits)
BMP180_CAL_AC2           = 0xAC  # R   Calibration data (16 bits)
BMP180_CAL_AC3           = 0xAE  # R   Calibration data (16 bits)
BMP180_CAL_AC4           = 0xB0  # R   Calibration data (16 bits)
BMP180_CAL_AC5           = 0xB2  # R   Calibration data (16 bits)
BMP180_CAL_AC6           = 0xB4  # R   Calibration data (16 bits)
BMP180_CAL_B1            = 0xB6  # R   Calibration data (16 bits)
BMP180_CAL_B2            = 0xB8  # R   Calibration data (16 bits)
BMP180_CAL_MB            = 0xBA  # R   Calibration data (16 bits)
BMP180_CAL_MC            = 0xBC  # R   Calibration data (16 bits)
BMP180_CAL_MD            = 0xBE  # R   Calibration data (16 bits)
BMP180_CONTROL           = 0xF4
BMP180_TEMPDATA          = 0xF6
BMP180_PRESSUREDATA      = 0xF6

# Commands
BMP180_READTEMPCMD       = 0x2E
BMP180_READPRESSURECMD   = 0x34

class BMP180:
    def __init__(self, i2c, mode=BMP180_STANDARD, address=BMP180_I2CADDR):
        self._mode = mode
        self._i2c = i2c_device.I2CDevice(i2c, address)
        self._load_calibration()

    def _load_calibration(self):
        self.cal_AC1 = self._readS16BE(BMP180_CAL_AC1)   # INT16 408
        self.cal_AC2 = self._readS16BE(BMP180_CAL_AC2)   # INT16 -72
        self.cal_AC3 = self._readS16BE(BMP180_CAL_AC3)   # INT16 -14383
        self.cal_AC4 = self._readU16BE(BMP180_CAL_AC4)   # UINT16 32741
        self.cal_AC5 = self._readU16BE(BMP180_CAL_AC5)   # UINT16 32757
        self.cal_AC6 = self._readU16BE(BMP180_CAL_AC6)   # UINT16 23153
        self.cal_B1 = self._readS16BE(BMP180_CAL_B1)     # INT16 6190
        self.cal_B2 = self._readS16BE(BMP180_CAL_B2)     # INT16 4
        self.cal_MB = self._readS16BE(BMP180_CAL_MB)     # INT16 -32767
        self.cal_MC = self._readS16BE(BMP180_CAL_MC)     # INT16 -8711
        self.cal_MD = self._readS16BE(BMP180_CAL_MD)     # INT16 2868

    def read_raw_temp(self):
        """Reads the raw (uncompensated) temperature from the sensor."""
        self._write_register_byte(BMP180_CONTROL, BMP180_READTEMPCMD)
        time.sleep(0.005)  # Wait 5ms
        raw = self._readU16BE(BMP180_TEMPDATA)
        return raw

    def read_raw_pressure(self):
        """Reads the raw (uncompensated) pressure level from the sensor."""
        self._write_register_byte(BMP180_CONTROL, BMP180_READPRESSURECMD + (self._mode << 6))
        if self._mode == BMP180_ULTRALOWPOWER:
            time.sleep(0.005)
        elif self._mode == BMP180_HIGHRES:
            time.sleep(0.014)
        elif self._mode == BMP180_ULTRAHIGHRES:
            time.sleep(0.026)
        else:
            time.sleep(0.008)
        msb = self._readU8(BMP180_PRESSUREDATA)
        lsb = self._readU8(BMP180_PRESSUREDATA+1)
        xlsb = self._readU8(BMP180_PRESSUREDATA+2)
        raw = ((msb << 16) + (lsb << 8) + xlsb) >> (8 - self._mode)
        return raw

    def read_temperature(self):
        """Gets the compensated temperature in degrees celsius."""
        UT = self.read_raw_temp()
        # Datasheet value for debugging:
        #UT = 27898
        # Calculations below are taken straight from section 3.5 of the datasheet.
        X1 = ((UT - self.cal_AC6) * self.cal_AC5) >> 15
        X2 = (self.cal_MC << 11) // (X1 + self.cal_MD)
        B5 = X1 + X2
        temp = ((B5 + 8) >> 4) / 10.0
        return temp

    def read_pressure(self):
        """Gets the compensated pressure in Pascals."""
        UT = self.read_raw_temp()
        UP = self.read_raw_pressure()
        # Datasheet values for debugging:
        #UT = 27898
        #UP = 23843
        # Calculations below are taken straight from section 3.5 of the datasheet.
        # Calculate true temperature coefficient B5.
        X1 = ((UT - self.cal_AC6) * self.cal_AC5) >> 15
        X2 = (self.cal_MC << 11) // (X1 + self.cal_MD)
        B5 = X1 + X2
        # Pressure Calculations
        B6 = B5 - 4000
        X1 = (self.cal_B2 * (B6 * B6) >> 12) >> 11
        X2 = (self.cal_AC2 * B6) >> 11
        X3 = X1 + X2
        B3 = (((self.cal_AC1 * 4 + X3) << self._mode) + 2) // 4
        X1 = (self.cal_AC3 * B6) >> 13
        X2 = (self.cal_B1 * ((B6 * B6) >> 12)) >> 16
        X3 = ((X1 + X2) + 2) >> 2
        B4 = (self.cal_AC4 * (X3 + 32768)) >> 15
        B7 = (UP - B3) * (50000 >> self._mode)
        if B7 < 0x80000000:
            p = (B7 * 2) // B4
        else:
            p = (B7 // B4) * 2
        X1 = (p >> 8) * (p >> 8)
        X1 = (X1 * 3038) >> 16
        X2 = (-7357 * p) >> 16
        p = p + ((X1 + X2 + 3791) >> 4)
        return p

    def read_altitude(self, sealevel_pa=101325.0):
        """Calculates the altitude in meters."""
        # Calculation taken straight from section 3.6 of the datasheet.
        pressure = float(self.read_pressure())
        altitude = 44330.0 * (1.0 - pow(pressure / sealevel_pa, (1.0/5.255)))
        return altitude

    def read_sealevel_pressure(self, altitude_m=0.0):
        """Calculates the pressure at sealevel when given a known altitude in
        meters. Returns a value in Pascals."""
        pressure = float(self.read_pressure())
        p0 = pressure / pow(1.0 - altitude_m/44330.0, 5.255)
        return p0

    def _read_register(self, register, length):
        """Low level register reading over I2C, returns a list of values"""
        with self._i2c as i2c:
            i2c.write(bytes([register & 0xFF]))
            result = bytearray(length)
            i2c.readinto(result)
            #print("$%02X => %s" % (register, [hex(i) for i in result]))
            return result

    def _write_register_byte(self, register, value):
        """Low level register writing over I2C, writes one 8-bit value"""
        with self._i2c as i2c:
            i2c.write(bytes([register & 0xFF, value & 0xFF]))
            #print("$%02X <= 0x%02X" % (register, value))

    def _readS16BE(self, register):
        data = self._read_register(register, 2)
        return struct.unpack('>h', data)[0]

    def _readS16LE(self, register):
        data = self._read_register(register, 2)
        return struct.unpack('<h', data)[0]

    def _readU16BE(self, register):
        data = self._read_register(register, 2)
        return struct.unpack('>H', data)[0]

    def _readU16LE(self, register):
        data = self._read_register(register, 2)
        return struct.unpack('<H', data)[0]

    def _readU8(self, register):
        data = self._read_register(register, 1)
        return struct.unpack('<H', data)[0]

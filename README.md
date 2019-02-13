# ccpl
A collection of custom circuit python libraries

## BMP180

```
import time
import board
import busio
from adafruit_bmp180 import BMP180
i2c = busio.I2C(board.SCL, board.SDA)
bmp180 = BMP180(i2c)

print('Temp = {0:0.2f} *C'.format(bmp180.read_temperature()))
print('Pressure = {0:0.2f} Pa'.format(bmp180.read_pressure()))
print('Altitude = {0:0.2f} m'.format(bmp180.read_altitude(103220)))
print('Sealevel Pressure = {0:0.2f} Pa'.format(bmp180.read_sealevel_pressure()))
```

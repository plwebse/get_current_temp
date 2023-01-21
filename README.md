# get_current_temp

MicroPython code for collecting data from the Adafruit bmp280 module and exposing the values via Raspberry Pi Pico W webservers. 
The webserver is exposing the data as Prometheus Metrics.

Uses the MicroPython library:
https://github.com/flrrth/pico-bmp280

Example output: 

    bmp280_temperature{unit="°C"} 30.79219
    bmp280_pressure{unit="hPa."} 973.3098


from machine import Pin, SPI
import utime
import network
import socket
import time
from bmp280 import BMP280SPI
import secret

spi1_sck = Pin(10)
spi1_tx = Pin(11)
spi1_rx = Pin(12)
spi1_csn = Pin(13, Pin.OUT, value=1)
spi1 = SPI(1, sck=spi1_sck, mosi=spi1_tx, miso=spi1_rx)
bmp280_spi = BMP280SPI(spi1, spi1_csn)

# gobal settings
cache_ttl = 10
ok_http_header = 'HTTP/1.1 200 OK\r\nContent-type: application/json; charset=utf-8\r\n\r\n'
not_found_http_header = 'HTTP/1.1 404 Not Found\r\nContent-type: application/json; charset=utf-8\r\n\r\n'


wlan = None
s = None
addr = None

def connect_to_wlan(secret):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(secret.ssid, secret.password)

    max_wait = 30
    while max_wait > 0:
        if wlan.status() < 0 or wlan.status() >= 3:
            break
        max_wait -= 1
        print('waiting for connection...')
        time.sleep(1)
    if wlan.status() != 3:
        raise RuntimeError('network connection failed')
    else:
        print('connected')
        status = wlan.ifconfig()
        print( 'ip = ' + status[0] )
    return wlan

def get_addr_info():
    return socket.getaddrinfo('0.0.0.0', 80)[0][-1]

def create_socket(addr):
    s = socket.socket()
    s.settimeout(1.0)
    s.bind(addr)
    s.listen(1)
    print('listening on', addr)
    return s


def send_http_header_and_body_and_close(cl, header,  body):
    cl.send(header)
    cl.send(body)
    cl.close()

def get_read_out_and_convert_to_json():
    readout = bmp280_spi.measurements
    temperature = readout['t']
    pressure = readout['p']    
    return f'{{"temperature":{temperature}, "temperature-unit":"°C", "pressure":{pressure}, "pressure-unit":"hPa."}}'
 
http_body = get_read_out_and_convert_to_json()
cl = None
last_fetch = time.time()
while True:    
    try:
        if wlan is None:
            wlan = connect_to_wlan(secret)
        
        if addr is None:
            addr = get_addr_info()
        
        if s is None:
            s = create_socket(addr)
        
        now = time.time()
        cl, addr = s.accept()
        print('client connected from', addr)
        request = cl.recv(1024)
        request = str(request)
        try:
            request = request.split()[1]
        except IndexError:
            cl.close()
                
        if request == '/':
            if (now - last_fetch) > cache_ttl:                            
                http_body = get_read_out_and_convert_to_json()
                last_fetch = now
                print('updated:', now)
            else:
                print('cached last_fetch was:', last_fetch)
            send_http_header_and_body_and_close(cl, ok_http_header, http_body)
        else:
            send_http_header_and_body_and_close(cl, not_found_http_header, '{}')

    except OSError as e:
        if cl is not None:
            cl.close()
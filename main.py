from machine import Pin, SPI
import utime
import network
import socket
import time
from bmp280 import BMP280SPI
import secret
import rp2

spi1_sck = Pin(10)
spi1_tx = Pin(11)
spi1_rx = Pin(12)
spi1_csn = Pin(13, Pin.OUT, value=1)
spi1 = SPI(1, sck=spi1_sck, mosi=spi1_tx, miso=spi1_rx)
bmp280_spi = BMP280SPI(spi1, spi1_csn)
rp2.country('SE')



cache_ttl = 10
max_wait = 30

wlan = None
server_socket = None
ip_addr = None

def connect_to_wlan(secret):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(secret.ssid, secret.password)
    
    count = 0
    while wlan.status() != 3:
        count = count + 1
        print('waiting for connection... try:', count)
        print('ssid:', secret.ssid)
        print('status:', wlan.status())
        if count >= max_wait:
            time.sleep(10)
            count = 0
        else:
            time.sleep(1)

    print('connected to:', secret.ssid)
    status = wlan.ifconfig()
    print('ip = ' + status[0] )
    return wlan

def create_socket(s):
    ip_addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    print('create socket: ', ip_addr)
    print('socket: ', s)
    while s is None:
        s = socket.socket()
        s.settimeout(1.0)
        s.bind(ip_addr)
        s.listen(1)
        time.sleep(5)
        print('socket_created:', s)
    
    print('listening on', ip_addr)
    return s

def send_http_header_and_body_and_close(cl, header,  body):
    cl.send(header)
    cl.send(body)
    cl.close()

def get_read_out_and_convert_to_json():
    print('get_read_out_and_convert_to_json')
    readout = bmp280_spi.measurements
    temperature = readout['t']
    pressure = readout['p']
    return f'bmp280_temperature{{unit="°C"}} {temperature}\nbmp280_pressure{{unit="hPa."}} {pressure}\n'

def http_request_response(cl, now, last_fetch, cache_ttl, http_body):
    request = cl.recv(1024)
    request = str(request)
    last_update = last_fetch
    ok_http_header = 'HTTP/1.1 200 OK\r\nContent-type: text/plain; version=0.0.4; charset=utf-8\r\n\r\n'
    not_found_http_header = 'HTTP/1.1 404 Not Found\r\nContent-type: application/json; charset=utf-8\r\n\r\n'
    
    try:
        request = request.split()[1]
    except IndexError:
        cl.close()
                
    if request == '/' or request == '/metrics':
        print('request 200:', request)
        if (now - last_update) > cache_ttl:                            
            http_body = get_read_out_and_convert_to_json()
            last_update = now
            print('updated:', last_update)
        else:
            print('cached last_update was:', last_update)
        send_http_header_and_body_and_close(cl, ok_http_header, http_body)
    else:
        print('request 404:', request)
        send_http_header_and_body_and_close(cl, not_found_http_header, '{}')
    return (http_body, last_update)

last_fetch = time.time()
http_body = get_read_out_and_convert_to_json()

while True:
    cl = None
    now = time.time()
    try:
        if wlan is not None and not wlan.isconnected():
            print(f'not connected to wifi waiting: {max_wait} before tring to connect agian.')
            time.sleep(max_wait)
            wlan = None            
            server_socket = None
            print("trying to connect to wifi agian")
        
        if wlan is None:
            print('wlan is None')
            wlan = connect_to_wlan(secret)
            server_socket = create_socket(server_socket)

        if server_socket is None:
            print('server_socket is None')
            server_socket = create_socket(server_socket)
            time.sleep(10)
            continue

        cl, cl_ip_addr = server_socket.accept()
        print('client connected from', cl_ip_addr)
        http_body, last_fetch = http_request_response(cl, now, last_fetch, cache_ttl, http_body)
        
    except OSError as e:
        if cl is not None:
            cl.close()
    except RuntimeError as e:
        print('runtime error:', e)
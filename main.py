from machine import Pin, SPI
import utime
import network
import socket
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

def connect_to_wlan():
    global wlan
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
            utime.sleep(10)
            count = 0
        else:
            utime.sleep(2)

    print('connected to:', secret.ssid)
    status = wlan.ifconfig()
    print('ip = ' + status[0] )

def create_socket():
    global server_socket
    ip_addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    print('create socket: ', ip_addr)   
    while server_socket is None:
        print('socket: ', server_socket)    
        utime.sleep(1)
        try:
            server_socket = socket.socket()
            server_socket.settimeout(1.0)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(ip_addr)
            server_socket.listen(1)
            print('socket_created:', server_socket)
        except OSError as e:
            print('error:', e)
            machine.reset()
            if server_socket is not None:
                server_socket.close()
            server_socket = None
        utime.sleep(10)
    print('listening on', ip_addr)

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

last_fetch = utime.time()
http_body = get_read_out_and_convert_to_json()

while True:
    cl = None
    now = utime.time()
    try:
        if wlan is not None and not wlan.isconnected():
            print(f'not connected to wifi waiting: {max_wait} before tring to connect agian.')
            utime.sleep(max_wait)
            wlan.disconnect()
            wlan = None            
            server_socket = None
            print("trying to connect to wifi agian")
        
        if wlan is None:
            print('wlan is None')
            connect_to_wlan()
            create_socket()
            utime.sleep(10)

        if server_socket is None:
            print('server_socket is None')
            create_socket()
            utime.sleep(10)
            continue

        cl, cl_ip_addr = server_socket.accept()
        print('client connected from', cl_ip_addr)
        http_body, last_fetch = http_request_response(cl, now, last_fetch, cache_ttl, http_body)
        
    except OSError as e:
        if cl is not None:
            cl.close()
#        print('OSError: ', e)
    except RuntimeError as e:
        print('RuntimeError:', e)
    finally:
        if cl is not None:
            cl.close()
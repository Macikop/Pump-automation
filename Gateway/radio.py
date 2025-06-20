import sys
import socket
import selectors
import types

import json
import datetime
import struct
from pyrf24 import * 

message_gateway = {
    "emergency" : False,
    "get_status" : False,
    "turn_on" : False,
    "turn_off" : False,
    "wifi_status" : True,
    "reset" : False,
    "error_code" : 0,
    "reserved_1" : 0,
    "reserved_2" : 0,
    "message_counter" : 0
}

message_pump = {
    "emergency" : False,
    "status" : False,
    "overpressure" : False,
    "below_level" : False,
    "full_tank" : False,
    "overheat" : False,
    "error_code" : 0,
    "water_level" : 0,
    "reserved" : 0,
    "message_counter" : 0
}

def pack_message(gateway_message):
    output = 0
    output = gateway_message["emergency"] << 0 | gateway_message["get_status"] << 1 | gateway_message["turn_on"] << 2 | gateway_message["turn_off"] << 3 | gateway_message["wifi_status"] << 4 | gateway_message["reset"] << 5
    output = output | gateway_message["error_code"] << 6
    output = output | gateway_message["reserved_1"] << 8
    output = output | gateway_message["reserved_2"] << 16
    output = output | gateway_message["message_counter"] << 24
    return output
    

def unpack_message(pump_message):
    pump = {
    "emergency" : bool(pump_message & (1 << 0)),
    "status" : bool(pump_message & (1 << 1)),
    "overpressure" : bool(pump_message & (1 << 2)),
    "below_level" : bool(pump_message & (1 << 3)),
    "full_tank" : bool(pump_message & (1 << 4)),
    "overheat" : bool(pump_message & (1 << 5)),
    "error_code" : (pump_message & (0b11 << 6)) >> 6,
    "water_level" : (pump_message & (0b11111111 << 8)) >> 8,
    "reserved" : (pump_message & (0b11111111 << 16)) >> 16,
    "message_counter" : (pump_message & (0b11111111 << 24)) >> 24
    }
    return pump

class radio_driver():
    
    payload = [0]
    
    def __init__(self, ce, csn, radio_number):
        self.radio = RF24(ce, csn)
        if not self.radio.begin():
            raise RuntimeError("radio hardware is not responding")
    
        self.address = [b"1Node", b"2Node"]
        
        self.radio.setPALevel(RF24_PA_LOW, True)
        self.radio.setDataRate(RF24_250KBPS)
        self.radio.setAutoAck(True)
        self.radio.setCRCLength(RF24_CRC_8)
        self.radio.payloadSize = 4
        
        self.radio.openWritingPipe(self.address[radio_number])
        self.radio.openReadingPipe(1, self.address[not radio_number])
        
        self.radio.startListening()
        print("NRF24 enabled")
        
    def read_buffer(self):
        self.radio.startListening()
        has_payload, pipe_number = self.radio.available_pipe()
        if has_payload:
            buffer = self.radio.read(self.radio.payloadSize)
            self.payload[0] = struct.unpack("<L", buffer[:4])[0]
            return self.payload[0]
        else:
            return None

    def send_message(self, message):
        self.radio.stopListening()
        buffer = struct.pack("<L", message)
        fails = 0
        while fails < 10:
            resoult = self.radio.write(buffer)
            if resoult:
                self.radio.startListening()
                return True
            else:
                fails = fails + 1
        self.radio.startListening()
        return False

    def debug(self):
        self.radio.print_details()     
        
sel = selectors.DefaultSelector()

def accept_wrapper(sock):
    conn, addr = sock.accept()  # Should be ready to read
    #print(f"Accepted connection from {addr}")
    conn.setblocking(False)
    data = types.SimpleNamespace(addr=addr, inb=b"", outb=b"")
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    sel.register(conn, events, data=data)

def service_connection(key, mask):
    sock = key.fileobj
    data = key.data
    if mask & selectors.EVENT_READ:
        recv_data = sock.recv(1024)  # Should be ready to read
        if recv_data:
            data.outb += recv_data
        else:
            #print(f"Recived {data.outb}")
            #print(f"Closing connection to {data.addr}")
            sel.unregister(sock)
            sock.close()
            return data.outb

host, port = "0.0.0.0", 2137
lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
lsock.bind((host, port))
lsock.listen()
print(f"Listening on {(host, port)}")
lsock.setblocking(False)
sel.register(lsock, selectors.EVENT_READ, data=None)

CSN_PIN = 0
CE_PIN = 22
rd = radio_driver(CE_PIN, CSN_PIN, 0)
#rd.debug()


try:
    while True:
        events = sel.select(timeout=1.0)
        recived = rd.read_buffer()
        if recived != None:
            message_pump = unpack_message(recived)
            
            with open("exchange.json", "r") as f:
                content = json.loads(f.readline())
                content.append({"time" : str(datetime.datetime.now().isoformat()),
                                "data" : message_pump})
            with open("exchange.json", "w") as f:
                f.write(json.dumps(content))
        
        for key, mask in events:
            if key.data is None:
                accept_wrapper(key.fileobj)
            else:
                output = str(service_connection(key, mask))[2:-3]
                if output != "":
                    message_gateway["get_status"] = False
                    message_gateway["reset"] = False 
                    message_gateway["get_status"] = False
                    match output:
                        case "emergency":
                            message_gateway["message_counter"] = message_gateway["message_counter"] + 1 
                            message_gateway["emergency"] = True
                            message_gateway["turn_on"] = False
                            message_gateway["turn_off"] = False
                        case "turn_on":
                            message_gateway["message_counter"] = message_gateway["message_counter"] + 1 
                            message_gateway["turn_on"] = True
                            message_gateway["turn_off"] = False
                        case "turn_off":
                            message_gateway["message_counter"] = message_gateway["message_counter"] + 1 
                            message_gateway["turn_on"] = False
                            message_gateway["turn_off"] = True
                        case "get_info":
                            message_gateway["message_counter"] = message_gateway["message_counter"] + 1 
                            message_gateway["turn_on"] = False
                            message_gateway["turn_off"] = False
                            message_gateway["get_status"] = True
                        case "reset":
                            message_gateway["message_counter"] = message_gateway["message_counter"] + 1
                            message_gateway["emergency"] = False 
                            message_gateway["turn_on"] = False
                            message_gateway["turn_off"] = False
                            message_gateway["reset"] = True 
                        case "error":
                            message_gateway["error_code"] = 2 
                    if message_gateway["message_counter"] > 255:
                        message_gateway["message_counter"] = 0
                    rd.send_message(pack_message(message_gateway))
                            
except KeyboardInterrupt:
    print("Caught keyboard interrupt, exiting")
finally:
    sel.close()
    
    
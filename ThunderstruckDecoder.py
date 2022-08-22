import serial
import serial.tools.list_ports
import time
import csv
import paho.mqtt.client as mqtt
import json


class ThunderstruckChargerDecoder:
    mqttClient = ''
    
    def __init__(self):
        print("self centered")
        self.mqttClient = mqtt.Client("zeva4") # Create a MQTT client object
        self.mqttClient.connect("localhost", 1883) # Connect to the test MQTT broker
        self.mqttClient.loop_start()


    def checkPorts(self):
        myports = [tuple(p) for p in list(serial.tools.list_ports.comports())]
        for port in myports:
            print(port[1]) #is the name of the port device, like "Keyspan USA-19H"
            if 'TTL-232R-AJ' in port[1]:
                #print("port is ",port[0])
                return(port[0])
        return("")


    def serialConnectToThunderstruck(self, thePort):
        packVoltage = 0
        chargeCurrent = 0.0
        chargeState = "Unknown"
        lastLoggedTime = 0

        print("Attempting serial connect")
        ser = serial.Serial(thePort,9600,timeout=.2)
        print(ser)
        # send "enter a couple of times, look for EVCC
        ser.write(b'\r\n\r\n')
        
        readstuffbuff = b''

        for i in range(100):
            while 1:
                readstuff = ser.readline()
                print("len of readstuff is ",len(readstuff))
                if len(readstuff) > 0:
                    readstuffbuff = readstuffbuff + readstuff
                else:
                    break

            print("READA:",readstuffbuff)
            if b'evcc>' in readstuffbuff:
                print("Got the prompt")
                ser.write(b'show\r\n') 
                break
            else:
                print("NOT the prompt")
                #write a single escape, wait half second
                ser.write(b'\x1B')
                time.sleep(1)


        while 1:
            readstuff = ser.readline()
            print("READB:",readstuff)

            if b'state    :' in readstuff:
                try:
                    chargeState = readstuff[13:len(readstuff)-2]
                    print("State is ", chargeState)
                except:
                    print("Failed to decode chargeState")

            if b'    voltage:' in readstuff:
                # convert the 125.2V to a float and store it
                try:
                    packVoltage = float(readstuff[13:len(readstuff) - 3])
                    print("Voltage is ", packVoltage)
                except:
                    print("Failed to decode voltage")

            if b'current:' in readstuff:
                try:
                    chargeCurrent = float(readstuff[13:len(readstuff) - 3])
                    print("Charge current:", chargeCurrent)
                except:
                    print("Failed to parse charge current")
            
            #last part of the message: sleep and ask for more data
            if b'  uptime   :' in readstuff:
                self.mqttClient.publish("chargeState", chargeState);
                self.mqttClient.publish("packVoltage", packVoltage);
                self.mqttClient.publish("chargeCurrent", chargeCurrent);
                time.sleep(2)
            
            ser.write(b'show\r\n')


tsd = ThunderstruckChargerDecoder()
thePort = tsd.checkPorts()
print("thePort is ",thePort)
if thePort != '':
    tsd.serialConnectToThunderstruck(thePort)


            
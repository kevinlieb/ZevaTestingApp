import can,cantools
from can import Listener
import sys,os
import traceback
import struct
import math
import array as arr
import csv
import serial
import time
from timeloop import Timeloop
from datetime import timedelta
import relay_ft245r

import paho.mqtt.client as mqtt
import json

import requests

do_can = True

vehicleSpeed = 0;

db = 0
bus = 0
relayboard = 0
dev_list = {}

config = {}
lastNotificationTime = 0

temperatures = []
previousVoltages = []
mqttClient = []
current = 0.0
fakeCurrent = 0
skipCounter = 0
elements = []
gps_lat = 0.0
gps_lon = 0.0
gps_speed = 0.0
gps_alt = 0.0
gps_course = 0
gps_sat_in_use = 0
gps_valid = 0

class BunchOfButtons():
    global db
    global dev_list
    global relayboard
    global bus
    global current
    global fakeCurrent
    global skipCounter
    global elements
    zillaTemperature = 0
    global gps_lat, gps_lon, gps_speed, gps_alt, gps_course, gps_sat_in_use, gps_valid

    def processMqttMessage(self, client, userdata, message):
        topic = str(message.topic)
        message = str(message.payload.decode("utf-8"))

        print("~~~~~>Got topic: ", topic)
        if(topic == 'zillaTemperature'):
            self.zillaTemperature = message
            print("Got zilla temperature of ",self.zillaTemperature)

    def mqttOnConnect(self, client, userdata, flags, rc):
        print("mqttOnConnect: userdata ",userdata," and flags ",flags, " and rc ",rc)
        mqttClient.subscribe("zillaTemperature")

    def mqttOnDisconnect(self, client, userdata,  rc):
        print("!!!! mqttOnDisconnect !!!!")

    def __init__(self, **kwargs):
        global db
        global bus
        global config
        global mqttClient
        global lastNotificationTime

        tl = Timeloop()

        with open('config.json') as f:
            config = json.load(f)

        relayboard = relay_ft245r.FT245R()
        dev_list = relayboard.list_dev()

        # list of FT245R devices are returned
        if len(dev_list) == 0:
            print('No FT245R devices found')
        else:
            dev = dev_list[0]
            print('Using device with serial number ' + str(dev.serial_number))
            #BMS loop on to allow charging
            relayboard.connect(dev_list[0])
            relayboard.switchon(1)

        print("Initialize elements")
        for n in range(32):
            elements.append(0)

        #connect to the CAN bus and set up the database 
        if(do_can):
            bus = can.interface.Bus(bustype='socketcan', channel='can0', bitrate=500000)
            print("just before self is ",self)
            notifier=can.Notifier(bus,[MessageListener(self)])

        mqttClient = mqtt.Client("zeva") # Create a MQTT client object
        mqttClient.connect("localhost", 1883) # Connect to the test MQTT broker
        mqttClient.on_connect = self.mqttOnConnect
        mqttClient.on_disconnect = self.mqttOnDisconnect
        mqttClient.on_message = self.processMqttMessage
        mqttClient.loop_start()

        def print_message(msg):
            """Regular callback function. Can also be a coroutine."""
            print("Message: ",msg)

        @tl.job(interval=timedelta(seconds=1)) 
        def everySecondCallback():
            print("Every Second: ", str(time.strftime("%Y-%m-%d %H:%M:%S")))
            global lastNotificationTime
            global previousVoltages
            global config

            timeasinteger = int(time.time())

            if(do_can):
                #16,104 is 4200
                #16,74 is 4170
                #16,0 is 4096
                #15,0 is 3840
                #14,0 is 3584
                #15,176 is 4016
                msg1 = can.Message(arbitration_id=300,data=[16,74],is_extended_id=False) 
                msg2 = can.Message(arbitration_id=310,data=[16,74],is_extended_id=False)
                msg3 = can.Message(arbitration_id=320,data=[16,74],is_extended_id=False)
   
                try:
                    bus.send(msg1)
                    bus.send(msg2)
                    bus.send(msg3)
                except:
                    print("Failed to send awake message")

            highestVoltage = 0
            highestVoltageCellNumber = 0

            lowestVoltage = 422
            lowestVoltageCellNumber = 0

            #if previous voltages is empty initialize it here 
            if(len(previousVoltages) == 0):
                print("initialize previousVoltages")
                for n in range(32):
                    previousVoltages.append(0)

            biggestDifference = 0
            whereBiggestDifference = 0

            for n in range(len(elements)):
                if(elements[n] > highestVoltage):
                    highestVoltage = elements[n]
                    highestVoltageCellNumber = n
                if(elements[n] < lowestVoltage):
                    lowestVoltage = elements[n]
                    lowestVoltageCellNumber = n

                #print("elem is ",elements[n]," and prev ", previousVoltages[n])
                #calculate the biggest change in any cell voltage betweeen last sample
                absoluteDifference = abs(elements[n] - previousVoltages[n])
                if(absoluteDifference > biggestDifference):
                    whereBiggestDifference = n
                    biggestDifference = absoluteDifference

            for n in range(len(elements)):
                previousVoltages[n] = elements[n]

            print("Highest voltage: " + str(highestVoltage))
            print("Lowest voltage: " + str(lowestVoltage))
            biggestDifferenceFormatted = round(biggestDifference, 4)
            print("biggest difference: " + str(biggestDifferenceFormatted) + " at " + str(whereBiggestDifference)) 

            #send a text if any voltage is higher than 4.22v
            if(highestVoltage > 422 and ((time.time() - lastNotificationTime) > 360)):
                lastNotificationTime = time.time()
                logString = "high voltage reached on cell " + str(highestVoltageCellNumber) + " at " + time.strftime('%l:%M%p %Z on %b %d, %Y')
                print(logString)
                data = { 'phone':config['phone_number'], 
                         'message':logString,
                         'key':config['textbelt_key']} 
                response = requests.post('https://textbelt.com/text',data=data)
                relayboard.connect(dev_list[0])
                relayboard.switchoff(1)

            # if any voltage goes back under 4.19v turn the BMS relay back on
            if(highestVoltage < 419):
                try:
                    relayboard.connect(dev_list[0])
                    relayboard.switchon(1)
                except:
                    print("Failed to activate USB relay")


            ampMeter = current

            #if no temperatures are set yet initialize them here 
            if(len(temperatures) == 0):
                for n in range(10):
                    temperatures.append(0.0)

            #only log if there has been a significant change between last logged point
            if(biggestDifference > 0.25 or gps_speed > 2):
                print("logging")
                with open('voltages.csv', mode='a') as voltages_file:
                    print("Logging zillaTemperature of ", self.zillaTemperature)
                    voltage_writer = csv.writer(voltages_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                    voltage_writer.writerow([timeasinteger,
                                            elements[0],
                                            elements[1],
                                            elements[2],
                                            elements[3],
                                            elements[4],
                                            elements[5],
                                            elements[6],
                                            elements[7],
                                            elements[8],
                                            elements[9],
                                            elements[10],
                                            elements[11],
                                            elements[12],
                                            elements[13],
                                            elements[14],
                                            elements[15],
                                            elements[16],
                                            elements[17],
                                            elements[18],
                                            elements[19],
                                            elements[20],
                                            elements[21],
                                            elements[22],
                                            elements[23],
                                            elements[24],
                                            elements[25],
                                            elements[26],
                                            elements[27],
                                            elements[28],
                                            elements[29],
                                            elements[30],
                                            elements[31],
                                            temperatures[0],
                                            current,
                                            gps_lat, gps_lon, gps_speed, gps_alt, gps_course, gps_sat_in_use, gps_valid,
                                            self.zillaTemperature])

            theElements = []
            for n in range(32):
                theElements.append(elements[n])
            mqttClient.publish("voltages",json.dumps(theElements))
            mqttClient.publish("current",current) 
            mqttClient.publish("temperatures",int(temperatures[0])) 
            mqttClient.publish("speed",int(gps_speed)) 


        #theGrid = GridLayout(cols=4, rows=16, width=the_grid_width, size_hint=(None, 1), spacing=[5,5])

        #super(BunchOfButtons, self).__init__(**kwargs)
        #Clock.schedule_interval(everySecondCallback, 1)
        tl.start(block=True)


class ZevaApp():
    def run(self):
        #self.size=(800,600)        
        return BunchOfButtons()
        
class MessageListener(Listener):
    global bus
    global statusText

    def __init__(self, ecu):
        self.ecu = ecu
        print("in MessageListener self is ",self)


    def parseVoltageCAN(crap, elements, baseElement, msg, count, scaleFactor):
        for n in range(count):
            elements[baseElement + n] = ((msg.data[0 + (n * 2)] << 8) + msg.data[(n * 2) + 1]) / scaleFactor

    def parseCurrent(crap, msg):
        if(len(msg.data) >= 3):
            return( (msg.data[0] << 24) + (msg.data[1] << 16) | (msg.data[2] << 8) | msg.data[3])
        else:
            return 0.0


    def on_message_received(self, msg):
        global statusText
        global current
        global fakeCurrent
        global skipCounter
        global gps_lat, gps_lon, gps_speed, gps_alt, gps_course, gps_sat_in_use, gps_valid

        if msg.is_error_frame or msg.is_remote_frame:
            return

        message_decoded = False

        try:
            #self.ecu.notify(msg.arbitration_id, msg.data, msg.timestamp)
            #print("Got: ", msg)
            if(msg != None):
                scaleFactor = 10  #modified bars go from 0 to 450, and our voltages to show are 0v to 4.5

                if(msg.arbitration_id == 301):
                    self.parseVoltageCAN(elements, 0, msg, 4, scaleFactor)
                    message_decoded = True

                if(msg.arbitration_id == 302):
                    self.parseVoltageCAN(elements, 4, msg, 4, scaleFactor)
                    message_decoded = True

                if(msg.arbitration_id == 303):
                    self.parseVoltageCAN(elements, 8, msg, 4, scaleFactor)
                    message_decoded = True

                if(msg.arbitration_id == 311):      
                    self.parseVoltageCAN(elements, 12, msg, 4, scaleFactor)
                    message_decoded = True

                if(msg.arbitration_id == 312):
                    self.parseVoltageCAN(elements, 16, msg, 4, scaleFactor)
                    message_decoded = True

                if(msg.arbitration_id == 313):
                    #do nothing: there is no battery here
                    #self.parseVoltageCAN(elements, 20, msg, scaleFactor) 
                    message_decoded = True                    

                if(msg.arbitration_id == 321):      
                    self.parseVoltageCAN(elements, 20, msg, 4, scaleFactor)
                    message_decoded = True

                if(msg.arbitration_id == 322):
                    self.parseVoltageCAN(elements, 24, msg, 4, scaleFactor)
                    message_decoded = True

                if(msg.arbitration_id == 323):
                    self.parseVoltageCAN(elements, 28, msg, 4, scaleFactor)
                    message_decoded = True                    

                if(msg.arbitration_id == 304):
                    temperatures[0] = (msg.data[0] - 40)
                    temperatures[1] = (msg.data[1] - 40)
                    #print("Temp 1 is ", (msg.data[0] - 40))
                    #print("Temp 2 is ", (msg.data[1] - 40))
                    message_decoded = True

                if(msg.arbitration_id == 314):
                    #print("Got 314 temperature: ignore for now")
                    message_decoded = True

                if(msg.arbitration_id == 324):
                    #print("Got 324 temperature: ignore for now")
                    message_decoded = True

                #GPS location: 33.0987473926358, -117.25471634345958
                #         Lon:  3270148061      Lat:     1107585725  
                if(msg.arbitration_id == 0xA0000):
                    #print("GPS Location!")

                    lat_bytearray = bytearray([msg.data[3], msg.data[2], msg.data[1], msg.data[0]])
                    lon_bytearray = bytearray([msg.data[7], msg.data[6], msg.data[5], msg.data[4]])

                    gps_lat_raw = struct.unpack('<f', lat_bytearray)
                    gps_lon_raw = struct.unpack('<f', lon_bytearray)
                    gps_lat = gps_lat_raw[0]
                    gps_lon = gps_lon_raw[0]
                    #print("Lat: ", gps_lat, " Lon: ", gps_lon)
                    message_decoded = True

                #GPS speed / alt / heading / valid
                if(msg.arbitration_id == 0xA0001):
                    #print("GPS speed / alt / etc")
                    gps_speed_bytearray = bytearray([msg.data[1], msg.data[0]])
                    gps_alt_bytearray = bytearray([msg.data[3], msg.data[2]])
                    gps_course_bytearray = bytearray([msg.data[5], msg.data[4]])
                    gps_sat_in_use = msg.data[6]
                    gps_valid = msg.data[7]

                    gps_speed_raw = struct.unpack('<H',gps_speed_bytearray) #unsigned 2 byte short
                    gps_alt_raw = struct.unpack('<h', gps_alt_bytearray) #signed 2 byte short
                    gps_course_raw = struct.unpack('<H', gps_course_bytearray) #unsigned 2 byte short

                    gps_speed = gps_speed_raw[0] / 100
                    gps_alt = gps_alt_raw[0]
                    gps_course = gps_course_raw[0] / 100

                    #print("Speed: ", )
                    #print("Alt: ", gps_alt)
                    #print("Course", gps_course)
                    #print("Sats in use: ", gps_sat_in_use)
                    #print("Valid?: ", gps_valid)
                    mqttClient.publish("speed",int(gps_speed)) #send the speed every time you get it
                    message_decoded = True

                #GPS time
                if(msg.arbitration_id == 0xA0002):
                    #print("GPS time: toss for now")
                    message_decoded = True

                #GPS misc 1: don't know what it means
                if(msg.arbitration_id == 0xA0003):
                    #print("GPS misc 1")
                    message_decoded = True

                #GPS misc 2: don't know what it means
                if(msg.arbitration_id == 0xA0004):
                    #print("GPS misc 2")
                    message_decoded = True

                #current sensor
                if(msg.arbitration_id == 0x3C3):
                    current = self.parseCurrent(msg)
                    if (current > 2147483648):
                        current -= 2147483648;
                    else:
                        current = -(2147483648 - current);

                    current = current / 1000

                    #only update values every 100 samples
                    if(skipCounter == 100):
                        print("Current: ", current)
                        fakeCurrent = fakeCurrent + 10;
                        if(fakeCurrent > 4000):
                            fakeCurrent = -4000

                        skipCounter = 1;
                        ampMeter = current                        
                    else:
                        skipCounter = skipCounter + 1


                    message_decoded = True

            if(message_decoded == False):
                print("Unknown message: ", msg.arbitration_id)


        except Exception as e:
            print("shit broke")
            # Exceptions in any callbacks should not affect CAN processing

            traceback.print_exc()
            #print traceback.format_exc()
            #print traceback_template % traceback_details
            print(str(e))


if __name__ == '__main__':
    ZevaApp().run()

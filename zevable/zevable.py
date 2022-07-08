#!/usr/bin/python3

"""Copyright (c) 2019, Douglas Otwell

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import dbus

from advertisement import Advertisement
from service import Application, Service, Characteristic, Descriptor
from gpiozero import CPUTemperature
import paho.mqtt.client as mqtt
import time

current = 0
gps_speed = 0
temperatures = 0
lastMessageTime = 0
highestVoltage = 0
lowestVoltage = 500
zillaTemperature = 0

GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"
NOTIFY_TIMEOUT = 5000

def current_milli_time():
    return round(time.time() * 1000)

class ThermometerAdvertisement(Advertisement):
    def __init__(self, index):
        Advertisement.__init__(self, index, "peripheral")
        self.add_local_name("Zeva")
        self.include_tx_power = True

class ThermometerService(Service):
    THERMOMETER_SVC_UUID = "00000001-710e-4a5b-8d75-3e5b444bc3cf"

    def __init__(self, index):
        self.farenheit = True

        Service.__init__(self, index, self.THERMOMETER_SVC_UUID, True)
        self.add_characteristic(TempCharacteristic(self))
        self.add_characteristic(UnitCharacteristic(self))

    def is_farenheit(self):
        return self.farenheit

    def set_farenheit(self, farenheit):
        self.farenheit = farenheit

class TempCharacteristic(Characteristic):
    counter = 0
    TEMP_CHARACTERISTIC_UUID = "00000002-710e-4a5b-8d75-3e5b444bc3cf"

    def __init__(self, service):
        self.notifying = False

        Characteristic.__init__(
                self, self.TEMP_CHARACTERISTIC_UUID,
                ["notify", "read"], service)
        self.add_descriptor(TempDescriptor(self))

    def get_temperature(self):
        global globalMessage
        #global lastMessageTime

        print("in get_temperature")
        # print("current time ", current_milli_time())
        # print("lastMessageTime ", lastMessageTime)
        theFuckingMinus = (current_milli_time() - lastMessageTime)
        # print("the fucking minus is ", theFuckingMinus)

        if(theFuckingMinus > (10 * 1000)):
            value = [0,0,0,0,0,0]
        else:
            highByteHighestVoltage = (int(highestVoltage) & 0xff00) >> 8
            lowByteHighestVoltage  = (int(highestVoltage) & 0x00ff)

            highByteLowestVoltage = (int(lowestVoltage) & 0xff00) >> 8
            lowByteLowestVoltage  = (int(lowestVoltage) & 0x00ff)

            highByteCurrent = (int(float(current)) & 0xff00) >> 8
            lowByteCurrent  = (int(float(current)) & 0x00ff)

            value = [highByteHighestVoltage, lowByteHighestVoltage, highByteLowestVoltage, lowByteLowestVoltage, highByteCurrent, lowByteCurrent, temperatures, int(gps_speed)]

        print(value)
        return value

    def set_temperature_callback(self):
        global globalMessage
        if self.notifying:
            value = self.get_temperature()            
            self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": value}, [])
        return self.notifying

    def StartNotify(self):
        if self.notifying:
            return

        self.notifying = True

        value = self.get_temperature()
        self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": value}, [])
        self.add_timeout(NOTIFY_TIMEOUT, self.set_temperature_callback)

    def StopNotify(self):
        self.notifying = False

    def ReadValue(self, options):
        value = self.get_temperature()

        return value

class TempDescriptor(Descriptor):
    TEMP_DESCRIPTOR_UUID = "2901"
    TEMP_DESCRIPTOR_VALUE = "CPU Temperature"

    def __init__(self, characteristic):
        Descriptor.__init__(
                self, self.TEMP_DESCRIPTOR_UUID,
                ["read"],
                characteristic)

    def ReadValue(self, options):
        value = []
        desc = self.TEMP_DESCRIPTOR_VALUE

        for c in desc:
            value.append(dbus.Byte(c.encode()))

        return value

class UnitCharacteristic(Characteristic):
    UNIT_CHARACTERISTIC_UUID = "00000003-710e-4a5b-8d75-3e5b444bc3cf"

    def __init__(self, service):
        Characteristic.__init__(
                self, self.UNIT_CHARACTERISTIC_UUID,
                ["read", "write"], service)
        self.add_descriptor(UnitDescriptor(self))

    def WriteValue(self, value, options):
        val = str(value[0]).upper()
        if val == "C":
            self.service.set_farenheit(False)
        elif val == "F":
            self.service.set_farenheit(True)

    def ReadValue(self, options):
        value = []

        if self.service.is_farenheit(): val = "F"
        else: val = "C"
        value.append(dbus.Byte(val.encode()))

        return value

class UnitDescriptor(Descriptor):
    UNIT_DESCRIPTOR_UUID = "2901"
    UNIT_DESCRIPTOR_VALUE = "Temperature Units (F or C)"

    def __init__(self, characteristic):
        Descriptor.__init__(
                self, self.UNIT_DESCRIPTOR_UUID,
                ["read"],
                characteristic)

    def ReadValue(self, options):
        value = []
        desc = self.UNIT_DESCRIPTOR_VALUE

        for c in desc:
            value.append(dbus.Byte(c.encode()))

        return value

def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    #client.subscribe("$SYS/#")
    mqttClient.subscribe("voltages")
    mqttClient.subscribe("current")
    mqttClient.subscribe("temperatures")
    mqttClient.subscribe("speed")
    mqttClient.subscribe("zillaTemperature")

def on_disconnect(client, userdata, flags, rc):    
    print("on_disconnect called")

def processVoltages(client, userdata, message):
      global globalMessage
      global highestVoltage
      global lowestVoltage
      global lastMessageTime
      global current
      global gps_speed
      global temperatures
      global zillaTemperature

      print("Got a message")
      lastMessageTime = current_milli_time()

      topic = str(message.topic)
      message = str(message.payload.decode("utf-8"))
      print("Original message: ", topic, ":", message)
      if(topic == 'voltages'):
          message = message.replace("[","")
          message = message.replace("]","")
          digits = message.split(", ")
          print(digits)

          highestVoltage = 0.0
          lowestVoltage = 500.0
          for x in digits:
              if(float(x) > highestVoltage):
                  highestVoltage = float(x)
              if(float(x) < lowestVoltage):
                  lowestVoltage = float(x)
          globalMessage = message

      if(topic == 'current'):
          current = message      

      if(topic == 'speed'):
          gps_speed = message      

      if(topic == 'zillaTemperature'):
          zillaTemperature = message

      if(topic == 'temperatures'):
          print("Got temperatures of ", message)
          temperatures = int(message)
          if temperatures < 0:
            print("Bad Temperature!")
            temperatures = 1;
          

app = Application()
app.add_service(ThermometerService(0))
app.register()

adv = ThermometerAdvertisement(0)
adv.register()

try:
    mqttClient = mqtt.Client("zeva2")
    mqttClient.connect("localhost", 1883) # Connect to the test MQTT broker
    mqttClient.subscribe("#")
    mqttClient.on_message = processVoltages
    mqttClient.on_connect = on_connect
    mqttClient.on_disconnect = on_disconnect
    mqttClient.loop_start()


    app.run()
except KeyboardInterrupt:
    app.quit()

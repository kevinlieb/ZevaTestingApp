import kivy
import sys
import math
import array as arr
import csv
import time
import traceback

from kivy.app import App
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.spinner import Spinner
from kivy.graphics import Color, Rectangle
from kivy.modules import inspector
from kivy.uix.scrollview import ScrollView
#from speedmeter import SpeedMeter

import paho.mqtt.client as mqtt
import json

from Bar import Bar
import requests

window_width = 1800
window_height = 1600
the_grid_width = window_width

button_font_size = 12
buttonSize = ( (the_grid_width / 2), 40)

Window.size=(window_width,window_height)
Window.top=0
Window.left=0

#Window.fullscreen=True

use_speedmeter = False
vehicleSpeed = 0;


db = 0

config = {}
lastNotificationTime = 0

bluetooth_image = 0
statusText = 0
speedMeters = []
bars = []
temperatures = []
previousVoltages = []
meterLabels = []
mqttClient = []
current = 0.0
fakeCurrent = 0
skipCounter = 0
chargeState = ""
packVoltage = 0.0
chargeCurrent = 0.0
initialized = False
elements = []
highestVoltage = 500.0
lowestVoltage = 0.0

class BunchOfButtons(GridLayout):
    global db
    global dev_list
    global relayboard
    global speedMeters
    global temperatures
    global current
    global fakeCurrent
    global skipCounter
    global chargeState 
    global packVoltage
    global chargeCurrent
    global initialized
    global elements

    lastVoltagesTime = 0
    lastChargeStateTime = 0
    lastPackVoltageTime = 0
    lastChargeCurrentTime = 0


    grayColor = (1,1,1,1)
    redColor = (0,0.5,0,.85)

    def __init__(self, **kwargs):
        global db
        global config
        global initialized
        global elements

        global mqttClient
        global lastNotificationTime

        self.cols=1
        self.size_hint=(None,None)
        self.size=(window_width, window_height)
        self.pos=(0, 0)        

        with open('config.json') as f:
            config = json.load(f)

        def on_mqtt_connect(client, userdata, flags, rc):  # The callback for when the client connects to the broker
            print("Connected with result code {0}".format(str(rc)))  # Print result of connection attempt
            client.subscribe("voltages")  # Subscribe to the topic “voltages”
            client.subscribe("chargeState") 
            client.subscribe("packVoltage") 
            client.subscribe("chargeCurrent") 

        def on_mqtt_disconnect(client, userdata, rc):
            # if disconnect is detected clear out all the voltages to show something is wrong
            print("MQTT Disconnected!")

        def on_mqtt_message(client, userdata, msg):
            global elements
            global highestVoltage
            global lowestVoltage
            global chargeState
            global packVoltage
            global chargeCurrent

            print("Message received-> " + msg.topic + " " + str(msg.payload))
            if(msg.topic == 'voltages'):
                self.lastVoltagesTime = int(time.time()) 
                message = str(msg.payload.decode("utf-8"))
                message = message.replace("[","")
                message = message.replace("]","")
                digits = message.split(", ")
                print(digits)

                if(use_speedmeter):
                    elements = speedMeters
                else:
                    elements = bars;                

                try:
                    if(initialized == True):
                        print("Initialized is true")
                        n = 0
                        for x in digits:
                            elements[n].value = float(x)
                            if(float(x) > highestVoltage):
                                highestVoltage = float(x)
                            if(float(x) < lowestVoltage):
                                lowestVoltage = float(x)
                            meterLabels[n].text = "{:.2f}".format(elements[n].value / 100)
                            n = n + 1
                except:
                    print("Failed to do shit")
                    traceback.print_exc()
    

            if(msg.topic == 'chargeState'):
                self.lastChargeStateTime = int(time.time()) 
                chargeState = msg.payload.decode("utf-8")
                print("charge state: ",chargeState)

            if(msg.topic == 'packVoltage'):
                self.lastPackVoltageTime = int(time.time()) 
                packVoltage = msg.payload.decode("utf-8")

            if(msg.topic == 'chargeCurrent'):
                self.lastChargeCurrentTime = int(time.time()) 
                chargeCurrent = msg.payload.decode("utf-8")


        print("Starting MQTT")
        mqttClient = mqtt.Client("zevaclient") # Create a MQTT client object
        mqttClient.connect("hummbug2", 1883) # Connect to the test MQTT broker
        mqttClient.on_connect = on_mqtt_connect
        mqttClient.on_disconnect = on_mqtt_disconnect
        mqttClient.on_message = on_mqtt_message
        mqttClient.loop_start()


        def sliderCallback(instance, value):
            global vehicleSpeed
            vehicleSpeed = value
            speedLabel.text= str(value) + "kph"


        def print_message(msg):
            """Regular callback function. Can also be a coroutine."""
            print("Message: ",msg)


        def everySecondCallback(instance):
            print("Every Second")
            global lastNotificationTime
            global config
            global elements
            global highestVoltage
            global lowestVoltage
            global chargeState
            global packVoltage
            global chargeCurrent

            #print(Window.size)
            self.size=(Window.size[0], Window.size[1])

            timeasinteger = int(time.time())

            #click and clack test disabled
            # if(len(dev_list) > 0):
            #     #print("Device zero is ",dev_list[0])
            #     relayboard.connect(dev_list[0])
            #     if(timeasinteger % 2 == 0):
            #         relayboard.switchon(2)
            #     else:
            #         relayboard.switchoff(2)

            if(use_speedmeter):
                elements = speedMeters
            else:
                elements = bars;

            highestVoltage = 0
            highestVoltageCellNumber = 0

            lowestVoltage = 422
            lowestVoltageCellNumber = 0

            #if previous voltages is empty initialize it here 
            if(len(previousVoltages) == 0):
                for n in range(32):
                    previousVoltages.append(elements[n].value)

            biggestDifference = 0
            whereBiggestDifference = 0

            # if it has been more than 5 seconds since we saw a valid voltage message zero them out
            if(int(time.time()) - self.lastVoltagesTime > 5):
                for n in range(32):
                    elements[n].background_color = [1,1,1,1] #gray
                    elements[n].value = 3.0
                    meterLabels[n].text = "-.--"
            else:
                for n in range(32):
                    elements[n].background_color = [0,0,0,1]
                    if(elements[n].value > highestVoltage):
                        highestVoltage = elements[n].value
                        highestVoltageCellNumber = n
                    if(elements[n].value < lowestVoltage):
                        lowestVoltage = elements[n].value
                        lowestVoltageCellNumber = n

                    #calculate the biggest change in any cell voltage betweeen last sample
                    absoluteDifference = abs(elements[n].value - previousVoltages[n])
                    if(absoluteDifference > biggestDifference):
                        whereBiggestDifference = n
                        biggestDifference = absoluteDifference

                for n in range(32):
                    previousVoltages[n] = elements[n].value

                print("Highest volatage: " + str(highestVoltage))
                print("Lowest volatage: " + str(lowestVoltage))
                print("biggest difference: " + str(biggestDifference) + " at " + str(whereBiggestDifference))
                elements[highestVoltageCellNumber].background_color = [1,0,0,1]
                elements[lowestVoltageCellNumber].background_color = [0,0,1,1]

            #if no temperatures are set yet initialize them here 
            if(len(temperatures) == 0):
                temperatures.append(0.0)

            currentIntTime = int(time.time())
            if((currentIntTime - self.lastChargeStateTime > 120) or (currentIntTime - self.lastPackVoltageTime > 120)):
                statusText.text = "No charge data available"
            else:
                print("Charge state is ",chargeState)
                statusText.text = "Charge state: " + chargeState + " Pack: " + str(packVoltage) + " Current: " + str(chargeCurrent) + "A"


        theGrid = GridLayout(cols=4, rows=17, width=the_grid_width, size_hint=(None, 1), spacing=[5,5])

        super(BunchOfButtons, self).__init__(**kwargs)


        #speedMeter = SpeedMeter(max=4.2, tick=0.1, start_angle=-45, end_angle=120,subtick=0.05,label='V', value=3.66, cadran_color='#0f0f0f', needle_color='#ff0000', sectors=(0, '#ffffff'));
        for n in range(32):
            if(use_speedmeter):
                speedMeter = SpeedMeter()
                speedMeter.max = 42
                speedMeter.min = 2
                speedMeter.start_angle = -135
                speedMeter.end_angle = 135
                speedMeter.cadran_color = '#0f0f0f'
                speedMeter.needle_color = '#ff0000'
                speedMeters.append(speedMeter)
                innerGrid = GridLayout(cols=1,rows=2)
                innerLabel = Label(text='0.0',size_hint=(None, .6), text_size=(20,None), bold=True, color=[0,0,0,1])
                meterLabels.append(innerLabel)
                innerGrid.add_widget(speedMeter)
                innerGrid.add_widget(innerLabel)
                theGrid.add_widget(innerGrid)
            else:
                bar = Bar();
                bar.orientation = 'bt';
                bar.value = (n * 8)
                bar.color=[.4,.63,.01,1] #'#66a103' a nice green color
                bars.append(bar)
                innerGrid = GridLayout(cols=1,rows=2)
                innerLabel = Label(text='0.0',size_hint_y=.3,font_size='25sp',bold=True,color=[0,0,0,1])
                meterLabels.append(innerLabel)
                innerLabel.background_color=[.4,.63,.01,1]
                innerGrid.add_widget(bar)
                innerGrid.add_widget(innerLabel)
                theGrid.add_widget(innerGrid) 
        initialized = True
        print("set Initialized to true")

        with theGrid.canvas.before:
            Color(.8,.8,.8,1)
            self.rect = Rectangle(size=(the_grid_width,800), pos=theGrid.pos)

        def _update_rect(instance, value):
            self.rect.pos = instance.pos
            self.rect.size = instance.size

        theGrid.bind(pos=_update_rect, size=_update_rect)

        self.add_widget(theGrid)

        speedGrid = GridLayout(cols = 3, size_hint=(None, None), size=(the_grid_width, 50))
        speedSliderLabel = Label(text="Speed (kph)", size_hint=(None, None), size=((the_grid_width * (1/5)),10), font_size = button_font_size)
        speedGrid.add_widget(speedSliderLabel)

        speedSlider = Slider(min=0, max=100, size_hint=(None, None), step=1, size=((the_grid_width * (3/5)),25))
        speedSlider.bind(value=sliderCallback)
        speedGrid.add_widget(speedSlider)

        speedLabel = Label(text="0.0", size_hint=(None, None), size=((the_grid_width * (1/5)),25))
        speedGrid.add_widget(speedLabel)
        #theGrid.add_widget(speedGrid) //for future use

        statusText = Label(height=Window.size[1]*0.3, size_hint_y=.3,bold=True,color=[0,0,0,1])
        theGrid.add_widget(statusText)        

        Clock.schedule_interval(everySecondCallback, 1)


class ScrollableLabel(ScrollView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # ScrollView does not allow us to add more than one widget, so we need to trick it
        # by creating a layout and placing two widgets inside it
        # Layout is going to have one collumn and and size_hint_y set to None,
        # so height wo't default to any size (we are going to set it on our own)
        self.layout = GridLayout(cols=1, size_hint_y=None)
        self.add_widget(self.layout)

        # Now we need two wodgets - Label for chat history and 'artificial' widget below
        # so we can scroll to it every new message and keep new messages visible
        # We want to enable markup, so we can set colors for example
        self.history = Label(size_hint_y=None, markup=True)
        self.scroll_to_point = Label()

        # We add them to our layout
        self.layout.add_widget(self.history)
        self.layout.add_widget(self.scroll_to_point)

    def update_history(self, message):

        # First add new line and message itself
        self.history.text += '\n' + message

        # Set layout height to whatever height of chat history text is + 15 pixels
        # (adds a bit of space at teh bottom)
        # Set chat history label to whatever height of chat history text is
        # Set width of chat history text to 98 of the label width (adds small margins)
        self.layout.height = self.history.texture_size[1] + 15
        self.history.height = self.history.texture_size[1]
        self.history.text_size = (self.history.width * 0.98, None)

        # As we are updating above, text height, so also label and layout height are going to be bigger
        # than the area we have for this widget. ScrollView is going to add a scroll, but won't
        # scroll to the botton, nor there is a method that can do that.
        # That's why we want additional, empty wodget below whole text - just to be able to scroll to it,
        # so scroll to the bottom of the layout
        self.scroll_to(self.scroll_to_point)

class ZevaApp(App):
    def build(self):
        return BunchOfButtons()

class MessageListener():

    def __init__(self, ecu):
        self.ecu = ecu
        print("in MessageListener self is ",self)


    def on_message_received(self, msg):
        global bluetooth_image
        global statusText
        global speedMeters
        global bars
        global temperatures
        global meterLabels
        global current
        global fakeCurrent
        global skipCounter



if __name__ == '__main__':
    ZevaApp().run()

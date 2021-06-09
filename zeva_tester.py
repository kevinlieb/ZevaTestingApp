import kivy
import can,cantools
from can import Listener
import sys
import math
import array as arr
import csv
import time

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
from kivy_garden.speedmeter import SpeedMeter

import paho.mqtt.client as mqtt
import json

from Bar import Bar
import requests

window_width = 800
window_height = 500
the_grid_width = window_width

button_font_size = 12
buttonSize = ( (the_grid_width / 2), 40)

Window.size=(window_width,window_height)
Window.top=0
Window.left=0

#Window.fullscreen=True

#set to false when testing without CAN, like on a PC or Mac
do_can = True
use_speedmeter = False

#cruiseEnabledState = "OFF"
#cruiseEngagedState = "OFF"
#absEnabledState = "OFF"
#absRearEnabledState = "OFF"
vehicleSpeed = 0;

lhcm_up = 0
lhcm_down = 0
lhcm_left = 0
lhcm_right = 0
lhcm_center = 0
lhcm_page = 0
lhcm_home = 0

pair_trigger_counter = 0
pair_trigger = False

db = 0
bus = 0
config = {}
lastNotificationTime = 0

bluetooth_image = 0
statusText = 0
bluetooth_image_size = (47,72)
speedMeters = []
bars = []
meterLabels = []
mqttClient = []

class BunchOfButtons(GridLayout):
    global db
    global bus
    global speedMeters

    grayColor = (1,1,1,1)
    redColor = (0,0.5,0,.85)

    def __init__(self, **kwargs):
        global db
        global bus
        global config

        global bluetooth_image, statusText
        global bluetooth_image_size

        global mqttClient

        global lastNotificationTime

        self.cols=1
        self.size_hint=(None,None)
        self.size=(window_width, window_height)
        self.pos=(0, 0)        

        with open('config.json') as f:
            config = json.load(f)


        #connect to the CAN bus and set up the database 
        if(do_can):
            bus = can.interface.Bus(bustype='socketcan', channel='can0', bitrate=500000)
            print("just before self is ",self)
            notifier=can.Notifier(bus,[MessageListener(self)])

        mqttClient = mqtt.Client("zeva") # Create a MQTT client object
        mqttClient.connect("localhost", 1883) # Connect to the test MQTT broker
        mqttClient.loop_start()


        def buttonCallback(instance):
            #global grayColor
            #global redColor

            global vehicleSpeed
            global pair_trigger_counter
            global pair_trigger

            print('The button <%s> is being pressed' % instance.text)

            if(instance.text == "Pair"):
                pair_trigger = True


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

            if(do_can):
                #16,104 is 4200
                #16,0 is 4096
                msg1 = can.Message(arbitration_id=300,data=[16,0],is_extended_id=False) #15,0 is 3840
                msg2 = can.Message(arbitration_id=310,data=[16,0],is_extended_id=False)
                msg3 = can.Message(arbitration_id=320,data=[16,0],is_extended_id=False)
   
                try:
                    bus.send(msg1)
                    bus.send(msg2)
                    bus.send(msg3)
                except:
                    print("Failed to send awake message")

            if(use_speedmeter):
                elements = speedMeters
            else:
                elements = bars;

            highestVoltage = 0
            cellNumber = 0

            for n in range(32):
                if(elements[n].value > highestVoltage):
                    highestVoltage = elements[n].value
                    cellNumber = n

            print("Highest volatage: " + str(highestVoltage))

            if(highestVoltage > 421 and ((time.time() - lastNotificationTime) > 360)):
                lastNotificationTime = time.time()
                logString = "high voltage reached on cell " + str(cellNumber) + " at " + str(time.time())
                print(logString)
                data = { 'phone':'6502015803', 
                         'message':logString,
                         'key':config['textbelt_key']} 
                response = requests.post('https://textbelt.com/text',data=data)


            with open('voltages.csv', mode='a') as voltages_file:
                timeasinteger = int(time.time())
                voltage_writer = csv.writer(voltages_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                voltage_writer.writerow([timeasinteger,
                                        elements[0].value,
                                        elements[1].value,
                                        elements[2].value,
                                        elements[3].value,
                                        elements[4].value,
                                        elements[5].value,
                                        elements[6].value,
                                        elements[7].value,
                                        elements[8].value,
                                        elements[9].value,
                                        elements[10].value,
                                        elements[11].value,
                                        elements[12].value,
                                        elements[13].value,
                                        elements[14].value,
                                        elements[15].value,
                                        elements[16].value,
                                        elements[17].value,
                                        elements[18].value,
                                        elements[19].value,
                                        elements[20].value,
                                        elements[21].value,
                                        elements[22].value,
                                        elements[23].value,
                                        elements[24].value,
                                        elements[25].value,
                                        elements[26].value,
                                        elements[27].value,
                                        elements[28].value,
                                        elements[29].value,
                                        elements[30].value,
                                        elements[31].value])

                theElements = []
                for n in range(31):
                    theElements.append(elements[n].value)
                mqttClient.publish("voltages",json.dumps(theElements))




        theGrid = GridLayout(cols=4, rows=12, width=the_grid_width, size_hint=(None, 1), spacing=[5,5])

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
                innerLabel = Label(text='0.0',size_hint=(None, .1), color=[0,0,0,1])
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
                innerLabel = Label(text='0.0',size_hint=(None, .1), color=[0,0,0,1])
                meterLabels.append(innerLabel)
                innerLabel.background_color=[.4,.63,.01,1]
                innerGrid.add_widget(bar)
                innerGrid.add_widget(innerLabel)
                theGrid.add_widget(innerGrid)                

        # if(use_speedmeter):
        #     for speedMeter in speedMeters:
        #         theGrid.add_widget(speedMeter)
        # else:
        #     for bar in bars:
        #         theGrid.add_widget(bar)



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

        statusText = ScrollableLabel(height=Window.size[1]*0.3, size_hint_y=None)
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
        self.size=(800,600)        
        return BunchOfButtons()

class MessageListener(Listener):
    global bus
    global statusText

    def __init__(self, ecu):
        self.ecu = ecu
        print("in MessageListener self is ",self)


    def parseVoltageCAN(crap, elements, baseElement, msg, count, scaleFactor):
        for n in range(count):
            elements[baseElement + n].value = ((msg.data[0 + (n * 2)] << 8) + msg.data[(n * 2) + 1]) / scaleFactor
        # elements[baseElement + 1].value = ((msg.data[2] << 8) + msg.data[3]) / scaleFactor
        # elements[baseElement + 2].value = ((msg.data[4] << 8) + msg.data[5]) / scaleFactor
        # elements[baseElement + 3].value = ((msg.data[6] << 8) + msg.data[7]) / scaleFactor


    def on_message_received(self, msg):
        global bluetooth_image
        global statusText
        global speedMeters
        global bars
        global meterLabels

        if msg.is_error_frame or msg.is_remote_frame:
            return

        message_decoded = False

        try:
            #self.ecu.notify(msg.arbitration_id, msg.data, msg.timestamp)
            #print("Got: ", msg)
            if(msg != None):
                #print("msg is: ", msg)
                if(use_speedmeter):
                    elements = speedMeters
                    scaleFactor = 100
                else:
                    elements = bars;
                    scaleFactor = 10  #modified bars go from 0 to 450, and our voltages to show are 0v to 4.5

                if(msg.arbitration_id == 301):
                    self.parseVoltageCAN(elements, 0, msg, 4, scaleFactor)
                    message_decoded = True

                if(msg.arbitration_id == 302):
                    self.parseVoltageCAN(elements, 4, msg, 4, scaleFactor)
                    print("element 4 is: " , msg.data[0] , msg.data[1])
                    message_decoded = True

                if(msg.arbitration_id == 303):
                    self.parseVoltageCAN(elements, 8, msg, 4, scaleFactor)
                    message_decoded = True

                if(msg.arbitration_id == 311):      
                    self.parseVoltageCAN(elements, 12, msg, 4, scaleFactor)
                    self.message_decoded = True

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
                    print("Got 304 temperature: ignore for now")
                    message_decoded = True

                if(msg.arbitration_id == 314):
                    print("Got 314 temperature: ignore for now")
                    message_decoded = True

                if(msg.arbitration_id == 324):
                    print("Got 324 temperature: ignore for now")
                    message_decoded = True
                for n in range(32):
                    meterLabels[n].text = "{:.2f}".format(elements[n].value / 100)

            if(message_decoded == False):
                print("Unknown message: ", msg.arbitration_id)


        except Exception as e:
            # Exceptions in any callbacks should not affect CAN processing
            print(str(e))




if __name__ == '__main__':
    ZevaApp().run()

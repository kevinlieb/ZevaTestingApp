import kivy
import can,cantools
from can import Listener
import sys
import math
import array as arr

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


bluetooth_image = 0
statusText = 0
bluetooth_image_size = (47,72)
speedMeters = []

class BunchOfButtons(GridLayout):
    global db
    global bus
    global speedMeters

    grayColor = (1,1,1,1)
    redColor = (0,0.5,0,.85)

    def __init__(self, **kwargs):
        global db
        global bus

        global bluetooth_image, statusText
        global bluetooth_image_size

        self.cols=1
        self.size_hint=(None,None)
        self.size=(window_width, window_height)
        self.pos=(0, 0)        


        #connect to the CAN bus and set up the database 
        if(do_can):
            bus = can.interface.Bus(bustype='socketcan', channel='can0', bitrate=500000)
            print("just before self is ",self)
            notifier=can.Notifier(bus,[MessageListener(self)])

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
            if(do_can):
                msg = can.Message(arbitration_id=300,data=[0,0],is_extended_id=False)
                try:
                    bus.send(msg)               
                except:
                    print("Failed to send awake message")


        theGrid = GridLayout(cols=6, rows=3, width=the_grid_width, size_hint=(None, 1))

        super(BunchOfButtons, self).__init__(**kwargs)


        #speedMeter = SpeedMeter(max=4.2, tick=0.1, start_angle=-45, end_angle=120,subtick=0.05,label='V', value=3.66, cadran_color='#0f0f0f', needle_color='#ff0000', sectors=(0, '#ffffff'));
        for n in range(12):
            speedMeter = SpeedMeter()
            speedMeter.max = 42
            speedMeter.min = 2
            speedMeter.start_angle = -135
            speedMeter.end_angle = 135
            speedMeter.cadran_color = '#0f0f0f'
            speedMeter.needle_color = '#ff0000'
            speedMeters.append(speedMeter)

        for speedMeter in speedMeters:
            theGrid.add_widget(speedMeter)


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



    def on_message_received(self, msg):
        global bluetooth_image
        global statusText
        global speedMeters

        if msg.is_error_frame or msg.is_remote_frame:
            return

        message_decoded = False

        try:
            #self.ecu.notify(msg.arbitration_id, msg.data, msg.timestamp)
            #print("Got: ", msg)
            if(msg != None):
                print("msg is: ", msg)
                if(msg.arbitration_id == 301):      
                    speedMeters[0].value = ((msg.data[0] << 8) + msg.data[1]) / 100
                    speedMeters[1].value = ((msg.data[2] << 8) + msg.data[3]) / 100
                    speedMeters[2].value = ((msg.data[4] << 8) + msg.data[5]) / 100
                    speedMeters[3].value = ((msg.data[6] << 8) + msg.data[7]) / 100
                    print("Got 301: ",speedMeters[0].value, speedMeters[1].value,speedMeters[2].value,speedMeters[3].value)
                    message_decoded = True

                if(msg.arbitration_id == 302):
                    speedMeters[4].value = ((msg.data[0] << 8) + msg.data[1]) / 100
                    speedMeters[5].value = ((msg.data[2] << 8) + msg.data[3]) / 100
                    speedMeters[6].value = ((msg.data[4] << 8) + msg.data[5]) / 100
                    speedMeters[7].value = ((msg.data[6] << 8) + msg.data[7]) / 100
                    #print("Got 302: " + speedMeters[4].value + speedMeters[5].value + speedMeters[6].value + speedMeters[7].value)
                    message_decoded = True

                if(msg.arbitration_id == 303):
                    speedMeters[8].value = ((msg.data[0] << 8) + msg.data[1]) / 100
                    speedMeters[9].value = ((msg.data[2] << 8) + msg.data[3]) / 100
                    speedMeters[10].value = ((msg.data[4] << 8) + msg.data[5]) / 100
                    speedMeters[11].value = ((msg.data[6] << 8) + msg.data[7]) / 100
                    #print("Got 303: " + speedMeters[8].value + speedMeters[9].value + speedMeters[10].value + speedMeters[11].value)
                    message_decoded = True

            if(message_decoded == False):
                print("Unknown message: ", msg.arbitration_id)



        except Exception as e:
            # Exceptions in any callbacks should not affect CAN processing
            print(str(e))



if __name__ == '__main__':
    ZevaApp().run()

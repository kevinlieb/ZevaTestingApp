Zeva BMS testing code in Python

other depedencies include Kivy but should get installed with speedmeter

You must first get https://github.com/kivy-garden/speedmeter
and pip install .

For MQTT:
sudo apt-get install mosquitto mosquitto-clients

pip3 install python-can
pip3 install timeloop
pip3 install cantools
pip3 install pyusb



Change the line do_can = False; to do_can = True if you want to use real data from CAN

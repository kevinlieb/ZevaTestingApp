import can,cantools
from can import Listener
import time

db = 0
bus = 0

class MessageListener(Listener):
	global db
	global bus
	global statusText

	def __init__(self, ecu):
		self.ecu = ecu
		print("in MessageListener self is ",self)


	def on_message_received(self, msg):
		if msg.is_error_frame or msg.is_remote_frame:
			return

		try:
			#self.ecu.notify(msg.arbitration_id, msg.data, msg.timestamp)
			#print("Got: ", msg)
			if(msg != None):
				print("msg: ", db.decode_message(msg.arbitration_id, msg.data))

		except Exception as e:
			# Exceptions in any callbaks should not affect CAN processing
			print(str(e))

class TestItOut:

	def __init__(self):
		global db
		global bus
		global statusText

		bus = can.interface.Bus(bustype='socketcan', channel='can0', bitrate=500000)


		notifier=can.Notifier(bus,[MessageListener(self)])
		db = cantools.database.load_file('zeva_bms_v0.3.dbc')


		bmsm0_request = db.get_message_by_name('BMSM0_Request')                    
		data = bmsm0_request.encode({'BMSM0_Req':4.10});

		print(data)

		try:
			while True:
				time.sleep(1)

		except KeyboardInterrupt:
			pass  # exit normally

if __name__ == '__main__':
	testItOut = TestItOut()

import serial
import serial.tools.list_ports
import time
import csv
import paho.mqtt.client as mqtt
import json


class ZillaDecoder:
    mqttClient = ''
    
    def __init__(self):
        print("self centered")
        self.mqttClient = mqtt.Client("zeva3") # Create a MQTT client object
        self.mqttClient.connect("localhost", 1883) # Connect to the test MQTT broker
        self.mqttClient.loop_start()


    def checkPorts(self):
        myports = [tuple(p) for p in list(serial.tools.list_ports.comports())]
        for port in myports:
            print(port[1]) #is the name of the port device, like "Keyspan USA-19H"
            if 'Keyspan' in port[1]:
                #print("port is ",port[0])
                return(port[0])
        return("")


    def serialConnectToZilla(self, thePort):
        lastLoggedTime = 0

        print("Attempting serial connect")
        ser = serial.Serial(thePort,9600,timeout=.2)
        print(ser)
        # send "enter, escape, escape", wait half a second, then do it again
        ser.write(b'\r\n\x1B\x1B')
        time.sleep(0.5)
        ser.write(b'\r\n\x1B\r1B')
        
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
            if b'How may I help you' in readstuffbuff:
                print("Got the prompt")
                ser.write(b'p') #special menu
                time.sleep(0.5)
                ser.write(b'Q1\r\n')
                break
            else:
                print("NOT the prompt")
                #write a single escape, wait half second
                ser.write(b'\x1B')
                time.sleep(1)


        while 1:
            readstuff = ser.readline()
            print("READB:",readstuff)
            thesplit = readstuff.decode("utf-8").split(" ", 11)
            print("len of split is ",len(thesplit))


            if len(thesplit) > 8:
                # example of "letters": SMFSV
                print("Letters: ", thesplit[10])

                #O means main contactor on, vehicle is on, so log temperatures
                if "O" in thesplit[10]:
                    print("Main contactor OK")

                    temperature = self.tempoidsToDegreesC(int(thesplit[6],16))
                    print("Temperature: ", temperature)

                    timeasinteger = int(time.time())

                    # only log once per second
                    if timeasinteger != lastLoggedTime:
                        lastLoggedTime = timeasinteger
                        self.mqttClient.publish("zillaTemperature",temperature);
                        with open('temperature.csv', mode='a') as temperatures_file:
                            temperature_writer = csv.writer(temperatures_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                            temperature_writer.writerow([timeasinteger,
                                                        temperature])


    def tempoidsToDegreesC(self, tempoids):
        switcher = {
            26:1374,
            27:1431,
            28:1488,
            29:1545,
            30:1602,
            31:1659,
            32:1716,
            33:1773,
            34:1830,
            35:1887,
            36:1944,
            37:2001,
            38: 2058,
            39: 2115,
            40: 2173,
            41: 2230,
            42: 2288,
            43: 2346,
            44: 2403,
            45: 2461,
            46: 2518,
            47: 2576,
            48: 2633,
            49: 2691,
            50: 2749,
            51: 2806,
            52: 2864,
            53: 2921,
            54: 2979,
            55: 3036,
            56: 3094,
            57: 3152,
            58: 3209,
            59: 3267,
            60: 3324,
            61: 3382,
            62: 3439,
            63: 3497,
            64: 3555,
            65: 3612,
            66: 3670,
            67: 3727,
            68: 3785,
            69: 3842,
            70: 3900,
            71: 3958,
            72: 4015,
            73: 4073,
            74: 4130,
            75: 4188,
            76: 4245,
            77: 4303,
            78: 4361,
            79: 4418,
            80: 4476,
            81: 4533,
            82: 4591,
            83: 4648,
            84: 4706,
            85: 4763,
            86: 4821,
            87: 4879,
            88: 4936,
            89: 4994,
            90: 5051,
            91: 5109,
            92: 5166,
            93: 5224,
            94: 5282,
            95: 5339,
            96: 5397,
            97: 5454,
            98: 5512,
            99: 5569,
            100: 5627,
            101: 5685,
            102: 5742,
            103: 5800,
            104: 5857,
            105: 5915,
            106: 5972,
            107: 6030,
            108: 6088,
            109: 6145,
            110: 6203,
            111: 6260,
            112: 6318,
            113: 6375,
            114: 6433,
            115: 6491,
            116: 6548,
            117: 6606,
            118: 6663,
            119: 6721,
            120: 6778,
            121: 6836,
            122: 6894,
            123: 6951,
            124: 7009,
            125: 7066,
            126: 7124,
            127: 7181,
            128: 7239,
            129: 7297,
            130: 7354,
            131: 7412,
            132: 7469,
            133: 7527,
            134: 7584,
            135: 7642,
            136: 7700,
            137: 7757,
            138: 7815,
            139: 7872,
            140: 7930,
            141: 7987,
            142: 8045,
            143: 8103,
            144: 8160,
            145: 8218,
            146: 8275,
            147: 8333,
            148: 8390,
            149: 8448,
            150: 8506,
            151: 8563,
            152: 8621,
            153: 8678,
            154: 8736,
            155: 8793,
            156: 8851,
            157: 8909,
            158: 8966,
            159: 9024,
            160: 9081,
            161: 9139,
            162: 9196,
            163: 9254,
            164: 9312,
            165: 9369,
            166: 9427,
            167: 9484,
            168: 9542,
            169: 9599,
            170: 9657,
            171: 9715,
            172: 9772,
            173: 9830,
            174: 9887,
            175: 9945,
            176: 10000
            }

        return switcher.get(tempoids, 0)

zd = ZillaDecoder()
thePort = zd.checkPorts()
print("thePort is ",thePort)
if thePort != '':
    zd.serialConnectToZilla(thePort)
# print("27 is ",zd.tempoidsToDegreesC(27))
# print("37 is ",zd.tempoidsToDegreesC(37))
# print("47 is ",zd.tempoidsToDegreesC(47))



            
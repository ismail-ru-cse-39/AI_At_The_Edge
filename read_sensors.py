from sense_hat import SenseHat

sense = SenseHat()
sense.low_light = True
try:
    temperature = sense.get_temperature()
    humidity = sense.get_humidity()
    pressure = sense.get_pressure()
    print(f"Temperature: {temperature:.2f} degrees Celsius")
    print(f"Relative humidity: {humidity:.2f} %")
    print(f"Pressure: {pressure:.2f} hPa")
    sense.show_letter("W")
    input("Look for W on the matrix. Press Enter to finish. ")
finally:
    sense.clear()
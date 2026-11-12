# Raspberry Pi Environmental Monitoring Station

**Name:** Md Ismail Hossain  
**Student ID:** C00328703

## Project overview

This project uses a Raspberry Pi and Sense HAT to collect environmental readings, store them locally, and share them with a computer for analysis. It also explores how to interpret sensor data, run a small forecasting model on the Pi, and present results through a web dashboard and the LED matrix.

The system is designed to treat invalid or missing measurements as unavailable rather than turning them into zero. It continues recording locally when the network is unavailable, and the model operates in the background without controlling alerts.

## Skills developed

- Setting up and handling Raspberry Pi hardware safely
- Collecting sensor readings and checking whether they are valid
- Saving data in SQLite and applying a retention policy
- Transferring observations with MQTT
- Handling network interruptions and replaying stored readings
- Converting measurements into understandable states
- Training a model on a computer and running it on the Pi
- Measuring performance and memory use on edge hardware
- Creating an accessible LED display and web dashboard
- Writing unit tests and considering privacy, security, fairness, and data retention

## Project development

### Week 1: Raspberry Pi setup

I assembled the Raspberry Pi and Sense HAT, prepared the microSD card, connected the device to the network, and updated the operating system. I also created the project folders and Python environment, then ran a basic program to confirm the setup was working.

I practised safe shutdown and backup procedures. A device should be fully shut down before removing power or the card, because background processes may still be saving data. A backup should also be stored separately from the original card so that a card failure does not destroy both copies.

### Week 2: Sensor readings and local storage

I developed a program to collect temperature, humidity, and pressure readings. Configuration settings are kept separately from the sensor and storage logic, with an additional configuration file available for simulated readings.

Each observation includes its measurement units, a UTC timestamp, and validation checks. Values that fail validation are recorded as unavailable with an explanation. The station stores readings in a local SQLite database, and a separate utility lets me inspect the saved data.

I added tests for invalid measurements, timestamps, duplicate records, and data retention.

### Week 3: Sending data to a computer

The Raspberry Pi sends observations to a computer using MQTT through a Mosquitto broker. The receiving program checks the incoming data and saves valid readings to a central archive.

The station writes each observation to its own database before attempting to send it. This allows data collection to continue during a network outage. A replay utility can resend stored observations later to help fill gaps.

The broker used for this demonstration has no encryption or authentication, so it is suitable only for a controlled demo environment.

### Week 4: Interpreting measurements

I added processing to calculate features from recent valid readings. The feature window resets when the input is invalid or there is a long gap, preventing old or unreliable measurements from influencing current results.

The station assigns each reading a state such as “warming up,” “normal,” “attention,” or “unknown,” and provides a reason for the state. Hysteresis helps prevent the status from rapidly switching when readings hover near a threshold. I also included a heat-index estimate that is omitted when the inputs fall outside its valid range.

Tests cover feature windows, gaps in readings, status changes, and calculation limits.

### Week 5: Forecasting on the Raspberry Pi

I trained a Ridge regression model on a computer to estimate the sensor temperature one minute ahead. The training process uses chronological data splits and compares the model with a simple “no change” forecast.

The model is exported in a lightweight format and run directly on the Raspberry Pi. It declines to produce a prediction when the inputs are incompatible or outside supported bounds. The model runs in shadow mode, so its output does not control the station’s alerts.

The training data is simulated, so the model does not make reliable predictions from real sensor readings. Performance measurements describe execution speed and memory use only; they do not indicate energy consumption.

On the test device, the model file was about 1.5 KB, and the process used approximately 13.8 MiB of peak memory. A prediction took a median of roughly 6 microseconds. A complete local sampling cycle took a median of about 45 milliseconds, including sensor reading, processing, database storage, and other enabled local actions.

### Week 6: User interface

The Sense HAT LED matrix displays a simple symbol to communicate the station’s current state. A local web dashboard presents readings and clearly identifies data that is stale or unavailable, including the reason when known.

The dashboard’s update pause and the LED alert pause are separate from sensing, so pausing either display does not stop data collection. The interface also uses symbols alongside colour, supports keyboard focus, and includes a fallback for browsers without JavaScript.

### Week 7: Responsible data use

I reviewed how data moves through the system and considered privacy, security, reliability, accessibility, and transparency. The project includes documentation describing the data flow, retention period, privacy information, and identified legal and ethical concerns.

Deleting retained messages from the broker does not remove copies already stored in the station’s local database or the computer’s archive. Those copies must be managed separately.

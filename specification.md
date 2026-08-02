# Specification: poproaster_brain Firmware

## 1. General Idea
`poproaster_brain` is the control firmware for a coffee roasting machine running on a Raspberry Pi Pico microcontroller. 
It interfaces actors (actuators/controls) and sensors of the roaster with coffee roasting software (specifically Artisan) via Modbus RTU over USB.
The firmware is designed with modularity in mind, allowing the set of connected actors and sensors to grow and be defined via a configuration file. Furthermore, every connected actor and sensor has a dedicated physical OLED display driven by the Pico to present real-time telemetry, names, and historic trend diagrams.

## 2. Actors
Actors represent controllable hardware output devices on the coffee roaster.
* **Initial Actors**:
  1. **Fan**: Driven via PWM.
  2. **Heating Device**: Driven via PWM.
* **PWM Requirements**:
  * Different actors have distinct PWM frequencies.
  * Duty cycles range from 0% to 100%, controllable via Modbus RTU from Artisan.
* **Extensibility**: The system must support adding additional actors (e.g., agitator motor, cooling fan) dynamically via configuration.

## 3. Sensors
Sensors monitor physical state metrics of the roasting process.
* **Initial Sensor**:
  1. **Temperature Sensor**: Single thermocouple driven by a MAX6675 SPI IC.
* **Extensibility**: The system must support adding additional temperature or environmental sensors in future development.

## 4. Displays
Every actor and every sensor is paired with its own dedicated physical display to provide local visual feedback.
* **Hardware**: SSD1306 OLED displays operating over SPI interface.
* **Actor Display Content**:
  * **Actor Name**: As defined in the configuration file.
  * **Current Value**: Displayed as an exact percentage (0–100%).
  * **Diagram Over Time**: Real-time graphical plot showing the trend of the duty cycle percentage over time.
* **Sensor Display Content**:
  * **Sensor Name**: As defined in the configuration file.
  * **Current Value**: Displayed as the live measured temperature value.
  * **Diagram Over Time**: Real-time graphical plot showing the trend of the temperature measurements over time.

## 5. Configuration
* The firmware uses a configuration file/structure to define all connected actors and sensors.
* Configuration includes component names, pin assignments, PWM frequencies, sensor types, and communication parameters.
* Designed to easily add or reconfigure hardware without rewriting core application logic.

---

## Appendix: Open Questions List
*(This list collects technical and design questions to be answered together later in our planning process.)*

1. **Programming Language & Framework**: C/C++ Pico SDK vs. MicroPython vs. Rust?
2. **Configuration Storage & Parsing**: Compile-time config (e.g., `config.h`) vs. Runtime Flash config file (e.g., `config.json` via LittleFS)?
3. **Modbus RTU Specifications**:
   - Target Modbus Slave ID (default `1`)?
   - Register mapping scheme for Artisan (holding registers for controls, input registers for sensors, data scaling)?
4. **PWM Frequency Details**:
   - Target PWM frequency for the Fan (e.g., 25 kHz)?
   - Target PWM frequency for the Heating Device (e.g., low-frequency SSR PWM)?
5. **MAX6675 SPI & Pin Allocation**:
   - Hardware SPI port assignment and GPIO pinout for MAX6675 chip(s).
6. **SSD1306 Displays Setup**:
   - Display resolution (e.g., 128x64 or 128x32)?
   - SPI topology: Shared SPI bus for all OLEDs and MAX6675 with dedicated Chip Select (`CS`), Data/Command (`DC`), and Reset (`RES`) lines?
7. **Trend Diagram Window**:
   - Time window (e.g., 60 seconds) and plot update rate for the real-time diagram on the OLEDs.

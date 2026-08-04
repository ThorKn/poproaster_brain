# Specification: poproaster_brain Firmware

## 1. General Idea
`poproaster_brain` is the control firmware for a coffee roasting machine running on a Raspberry Pi Pico microcontroller. 
It interfaces actors (actuators/controls) and sensors of the roaster with coffee roasting software (specifically Artisan) via Modbus RTU over USB.
The firmware is designed with modularity in mind, allowing the set of connected actors and sensors to grow and be defined via a configuration file. Furthermore, every connected actor and sensor has a dedicated physical OLED display driven by the Pico to present real-time telemetry, names, and historic trend diagrams.

## 2. Hardware

### 2.1. Raspi Pico
* **Microcontroller**: Raspberry Pi Pico (RP2040).
* **Pinout & Wiring**:
  * Defines all GPIO pin allocations, SPI bus assignments (shared/dedicated buses for MAX6675 sensors and SSD1306 displays), hardware PWM output pins (for actors), Chip Select (`CS`) lines, Data/Command (`DC`), Reset (`RES`), and USB CDC communication.
  * Wiring details will be specified as pin choices and hardware interfaces are finalized.

### 2.2. Actors
Actors represent controllable hardware output devices on the coffee roaster.
* **Initial Actors**:
  1. **Fan**: Driven via PWM.
  2. **Heating Device**: Driven via PWM.
* **PWM Requirements**:
  * Different actors have distinct PWM frequencies.
  * Duty cycles range from 0% to 100%, controllable via Modbus RTU from Artisan.
* **Extensibility**: The system must support adding additional actors (e.g., agitator motor, cooling fan) dynamically via configuration.

### 2.3. Sensors
Sensors monitor physical state metrics of the roasting process.
* **Initial Sensor**:
  1. **Temperature Sensor**: Single thermocouple driven by a MAX6675 SPI IC.
* **Extensibility**: The system must support adding additional temperature or environmental sensors in future development.

### 2.4. Displays
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

## 3. Software

### 3.1. Framework
* **Environment & Toolchain**: Raspberry Pi Pico C/C++ SDK.
* **Language Standard**: C++17 / C11.
* **Core Microcontroller Capabilities**:
  * Hardware PWM slice management for actor output control (Fan & Heating Device).
  * Hardware SPI master controller for MAX6675 temperature sensors and SSD1306 OLED displays.
  * Hardware timers for periodic sensor sampling, display refresh, and control loop execution.
  * Flash memory interface for persistent configuration storage (if flash-based).
* **Software Modules**:
  * **Modbus RTU Stack**: Embedded Modbus RTU slave protocol handler operating over the USB serial stream.
  * **SSD1306 Graphics & Plotting Library**: 1-bit monochrome graphics engine for SSD1306 OLEDs over SPI (text rendering, font bitmaps, and real-time trend graphing).
* **USB Connectivity**:
  * **Target Host**: Laptop running Artisan roasting software connected via standard USB cable.
  * **Interface Type**: USB Virtual COM Port (CDC - Communication Device Class), enabling direct serial Modbus RTU communication over USB without requiring external hardware converters.
* **Execution & Memory Architecture**:
  * Dual-core RP2040 processing (Core 0 allocated for USB CDC / Modbus communication; Core 1 allocated for SPI sensor polling and OLED rendering).
  * Static memory allocation strategy for system stability during real-time roasting operations.

### 3.2. Configuration
* **Format & Storage**: The system configuration is defined in a `config.json` file.
* **Build-Time Processing**: The `config.json` file is parsed at **pre-compile / build time** (via a generator script during the build process). This creates static C++ configuration data structures embedded directly into firmware memory, avoiding runtime JSON parsing overhead and dynamic memory allocation on the Pico.
* **Configuration Scope**:
  * **System Settings**: Device identifier, Modbus Slave ID.
  * **Actors Definition**: Name, ID, hardware PWM GPIO pin, target PWM frequency (Hz), Modbus holding register mapping, and paired OLED display configuration.
  * **Sensors Definition**: Name, ID, sensor chip type (e.g. MAX6675), SPI bus & pin assignments (SCK, SO, CS), Modbus input register mapping, and paired OLED display configuration.
  * **Displays Definition**: Display resolution, shared SPI bus pins (SCK, MOSI, D/C, RESET), and individual CS pin assignments for each actor/sensor screen.
* **Configuration Example**: See [Appendix B](#appendix-b-configuration-example-configjson) for a complete `config.json` example schema.

---

## Appendix A: Open Questions List
*(This list collects technical and design questions to be answered together later in our planning process.)*

1. **Programming Language & Framework**: **[Decided]** Raspberry Pi Pico C/C++ SDK.
2. **Configuration Format & Parsing**: **[Decided]** `config.json` file parsed at pre-compile/build time into static C++ configuration structures.
3. **Modbus RTU Specifications**:
   - Target Modbus Slave ID (default `1`)?
   - Register mapping scheme for Artisan (holding registers for controls, input registers for sensors, data scaling)?
4. **Raspi Pico Pinout & Wiring (Chapter 2.1)**:
   - What GPIO pins will be allocated for the PWM actor outputs (Fan and Heating Device)?
   - What SPI peripheral (SPI0 vs. SPI1) and GPIO pins will be assigned for the MAX6675 thermocouple amplifier (SCK, SO/MISO, CS)?
   - What SPI peripheral and GPIO pins will be assigned for the SSD1306 OLED displays (SCK, MOSI, CS per display, shared DC & RESET)?
   - What power rails (3.3V vs. 5V VBUS/VREG) will supply power to the OLED displays and MAX6675 module?
5. **PWM Frequency Details**:
   - Target PWM frequency for the Fan (e.g., 25 kHz)?
   - Target PWM frequency for the Heating Device (e.g., low-frequency SSR PWM)?
6. **SSD1306 Displays Setup**:
   - Display resolution (e.g., 128x64 or 128x32)?
   - SPI topology: Shared SPI bus for all OLEDs and MAX6675 with dedicated Chip Select (`CS`), Data/Command (`DC`), and Reset (`RES`) lines?
7. **Trend Diagram Window**:
   - Time window (e.g., 60 seconds) and plot update rate for the real-time diagram on the OLEDs.

---

## Appendix B: Configuration Example (`config.json`)
Below is a sample `config.json` configuration file demonstrating the structure for system settings, shared SPI buses, display defaults, actors (fan and heater), and sensors (MAX6675 thermocouple):

```json
{
  "system": {
    "device_name": "PopRoaster Brain",
    "modbus_slave_id": 1
  },
  "spi_buses": [
    {
      "bus_id": 0,
      "sck_pin": 18,
      "mosi_pin": 19,
      "miso_pin": 16
    }
  ],
  "display_defaults": {
    "resolution": "128x64",
    "dc_pin": 20,
    "reset_pin": 21,
    "update_rate_ms": 100,
    "graph_time_window_s": 60
  },
  "actors": [
    {
      "id": "fan",
      "name": "FAN",
      "pin": 15,
      "pwm_frequency_hz": 25000,
      "modbus_register": 0,
      "display": {
        "spi_bus": 0,
        "cs_pin": 17
      }
    },
    {
      "id": "heater",
      "name": "HEATER",
      "pin": 14,
      "pwm_frequency_hz": 10,
      "modbus_register": 1,
      "display": {
        "spi_bus": 0,
        "cs_pin": 13
      }
    }
  ],
  "sensors": [
    {
      "id": "temp_bean",
      "name": "BEAN TEMP",
      "type": "MAX6675",
      "spi_bus": 0,
      "cs_pin": 12,
      "modbus_register": 0,
      "display": {
        "spi_bus": 0,
        "cs_pin": 11
      }
    }
  ]
}
```

### Key Elements of this Configuration:
1. **`system`**: Defines global parameters including device name and Modbus Slave ID.
2. **`spi_buses`**: Centralizes shared SPI bus hardware definitions (SCK, MOSI, MISO pin assignments) for referenced `bus_id`s.
3. **`display_defaults`**: Establishes common display parameters (resolution, shared Data/Command `dc_pin`, Reset `reset_pin`, refresh rate, and graph time window) so each component only specifies its Chip Select (`cs_pin`).
4. **`actors`**: Defines output components with their name, GPIO pin, PWM frequency, Modbus holding register index, and paired display `cs_pin`.
5. **`sensors`**: Defines input devices with their name, IC type (`MAX6675`), SPI bus & CS pin, Modbus input register index, and paired display `cs_pin`.


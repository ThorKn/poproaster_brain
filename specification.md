# Specification: poproaster_brain Firmware

## 1. General Idea
`poproaster_brain` is the control firmware for a coffee roasting machine running on a Raspberry Pi Pico microcontroller. 
It interfaces actors (actuators/controls) and sensors of the roaster with coffee roasting software (specifically Artisan) via Modbus RTU over USB.
The firmware is designed with modularity in mind, allowing the set of connected actors and sensors to grow and be defined via a configuration file. Furthermore, every connected actor and sensor has a dedicated physical OLED display driven by the Pico to present real-time telemetry, names, and historic trend diagrams.

## 2. Hardware

### 2.1. Raspi Pico
* **Microcontroller**: Raspberry Pi Pico (RP2040).
* **Pinout & Wiring**:
  * All GPIO pin allocations—including hardware PWM outputs for actors, SPI bus assignments (SCK, MOSI, MISO), individual Chip Select (`CS`) lines for sensors and displays, Data/Command (`D/C`), and Reset (`RESET`) pins—are defined in `config.json` and parsed at build time.

### 2.2. Actors
Actors represent controllable hardware output devices on the coffee roaster.
* **Initial Actors**:
  1. **Fan**: Driven via high-frequency hardware PWM (Default frequency: `25000` Hz / 25 kHz).
  2. **Heating Device**: Driven via low-frequency hardware PWM (Default frequency: `2` Hz, e.g. for SSR control).
* **PWM Requirements**:
  * Each actor's target PWM frequency (`pwm_frequency_hz`) is defined in `config.json` and parsed at build time.
  * Duty cycles range from 0% to 100%, controllable via Modbus RTU holding registers from Artisan.
* **Heating Indicator LED (`status_led_pin`)**:
  * An optional GPIO output pin can be configured for the Heating Device to drive a physical status LED.
  * **Solid ON**: Heating duty cycle is > 0%.
  * **OFF**: Heating duty cycle is 0%.
  * **Slow Blinking**: Modbus communication watchdog warning phase (when serial commands cease, prior to 5-second emergency shutdown).
* **Extensibility**: The system must support adding additional actors (e.g., agitator motor, cooling fan) dynamically via configuration.

### 2.3. Sensors
Sensors monitor physical state metrics of the roasting process.
* **Initial Sensor**:
  1. **Temperature Sensor**: Single thermocouple driven by a MAX6675 SPI IC.
* **Fault & Error Handling**:
  * **Thermocouple Disconnect Detection**: The MAX6675 chip detects open thermocouple circuits (Bit D2 = 1).
  * **OLED Display**: Shows `"ERR"` instead of numerical temperature when a fault occurs.
  * **Modbus Telemetry**: Transmits sentinel value `-1` (represented as `-10` in x10 fixed-point format) to indicate invalid/error state to Artisan.
  * **Thermal Safety Interlock**: If the Bean Temperature sensor enters an error state, the firmware automatically forces the Heating Device to `0%` duty cycle.
* **Error Recovery Procedure**:
  * **Self-Healing Polling**: The Pico continues polling the MAX6675 at the configured interval (`sensor_defaults.poll_interval_ms`).
  * **Automatic Restoration**: When a valid thermocouple connection is re-established and 2 consecutive valid temperature readings are confirmed:
    1. The OLED display clears `"ERR"` and resumes live numerical temperature readings and trend graphing.
    2. Modbus input registers resume transmitting valid temperature telemetry.
    3. The thermal safety interlock disengages, enabling the Heating Device to accept duty cycle commands again via Modbus.
* **Extensibility**: The system must support adding additional temperature or environmental sensors in future development.

### 2.4. Displays
Every actor and every sensor is paired with its own dedicated physical display to provide local visual feedback.
* **Hardware & Resolution**: SSD1306 OLED displays operating over SPI interface with a fixed resolution of **128x64 pixels**.
* **Configuration & Bus Parameters**: SPI bus assignments, CS pin per display, shared Data/Command (`dc_pin`), Reset (`reset_pin`), display refresh rate (`update_rate_ms`), and diagram time window (`graph_time_window_s`) are defined in `config.json` and parsed at build time.
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
  * **System Settings**: Device identifier, Modbus Slave ID (`modbus_slave_id`), and Watchdog timeout (`modbus_timeout_ms`).
  * **Actors Definition**: Name, ID, hardware PWM GPIO pin, target PWM frequency (Hz), optional status LED pin (`status_led_pin`), Modbus holding register assignment (`modbus_holding_reg`), and paired OLED display Chip Select pin (`display_cs_pin`).
  * **Sensors Definition**: Name, ID, sensor chip type (e.g. MAX6675), SPI bus & pin assignments (SCK, SO, CS), Modbus input register assignment (`modbus_input_reg`), global polling interval (`sensor_defaults.poll_interval_ms`), and paired OLED display Chip Select pin (`display_cs_pin`).
  * **Displays Definition**: Shared SPI bus pins (SCK, MOSI, D/C, RESET), update rates (`update_rate_ms`), trend diagram time window (`graph_time_window_s`), display orientation (`rotation`), and individual CS pin assignments for each actor/sensor screen (`display_cs_pin`, fixed 128x64 resolution).
* **Configuration Example**: See [Appendix](#appendix-configuration-example-configjson) for a complete `config.json` example schema.

### 3.3. Modbus Communication & Watchdog Safety
* **Transport**: Modbus RTU protocol over Pico USB CDC virtual serial stream connected to host laptop.
* **Slave Address**: Parsed dynamically from `config.json` (`system.modbus_slave_id`, default `1`).
* **Register Architecture**:
  * **Holding Registers (`modbus_holding_reg`)**: Read/Write registers mapped to **Actors** for Artisan control. Values represent duty cycle percentages (`0` to `100` %).
  * **Input Registers (`modbus_input_reg`)**: Read-only registers mapped to **Sensors** for Artisan telemetry polling.
* **Data Scaling Strategy**: Fixed-point 1 decimal place (Scale factor `x10`). Temperature readings (e.g., `204.5°C`) are transmitted as signed 16-bit integer values (e.g., `2045`). Artisan applies divisor `/10`.
* **Communication Watchdog Timeout (`modbus_timeout_ms`)**:
  * Configured in `system` (Default: `5000` ms / 5 seconds).
  * If no Modbus read/write frame is received from Artisan within 5 seconds:
    1. **Warning Phase**: Heater Status LED blinks slowly to signal impending timeout.
    2. **Emergency Shutdown**: Heating Device duty cycle is automatically forced to `0%`.
    3. **LED Shutdown**: Heater Status LED turns OFF once shutdown completes.
* **Watchdog Recovery Procedure**:
  * **Automatic Resumption**: Upon receiving a new valid Modbus read or write frame from Artisan, the watchdog timer resets immediately.
  * **Safe Restart Policy**: To prevent sudden unexpected heating surges upon USB reconnection, all actor holding registers remain at `0%` until Artisan sends an explicit new write command. Slow LED blinking clears immediately, returning the status LED to solid OFF (until a non-zero duty cycle is commanded).

### 3.4. Configuration Validation (Compile-Time Test Cases)
To guarantee error-free firmware execution and hardware safety, the pre-compile configuration generator script validates `config.json` against the following rules before building the binary:

1. **GPIO Collision Test**: Verify that every assigned GPIO pin (SPI SCK, MOSI, MISO, D/C, RESET, `display_cs_pin` values, actor PWM pins, and `status_led_pin`) is unique across the entire configuration.
2. **GPIO Range Test**: Ensure all GPIO pin numbers fall within the valid RP2040 hardware GPIO range (`0` to `29`).
3. **PWM Slice Conflict Test**: Verify that any two actors sharing the same RP2040 hardware PWM slice have matching PWM frequencies (`pwm_frequency_hz`), preventing frequency register collisions on shared PWM hardware slices.
4. **Modbus Holding Register Uniqueness Test**: Ensure all `modbus_holding_reg` indices are unique across all actors and non-negative.
5. **Modbus Input Register Uniqueness Test**: Ensure all `modbus_input_reg` indices are unique across all sensors and non-negative.
6. **SPI Bus Assignment Test**: Verify that all `spi_bus` references match a declared `bus_id` in `spi_buses`.
7. **Display CS Assignment Test**: Verify that every actor and sensor has a valid, non-null `display_cs_pin` declared for its dedicated SSD1306 OLED display.
8. **Required Fields & Timeout Test**: Ensure all obligatory fields (`system.device_name`, `system.modbus_slave_id`, `system.modbus_timeout_ms`, `spi_buses`, `display_defaults`, `actors`, `sensors`) are present, non-empty, and valid.

---

## Appendix: Configuration Example (`config.json`)
Below is a sample `config.json` configuration file (stored in [config.json](file:///home/moss/Documents/hardware/popRoaster/poproaster_brain/config.json)) demonstrating the structure for system settings, shared SPI buses, display defaults, sensor defaults, actors (fan and heater with status LED), and sensors (MAX6675 thermocouple):

```json
{
  "system": {
    "device_name": "PopRoaster Brain",
    "modbus_slave_id": 1,
    "modbus_timeout_ms": 5000
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
    "dc_pin": 20,
    "reset_pin": 21,
    "update_rate_ms": 100,
    "graph_time_window_s": 60,
    "rotation": 0
  },
  "sensor_defaults": {
    "poll_interval_ms": 250
  },
  "actors": [
    {
      "id": "fan",
      "name": "FAN",
      "pin": 15,
      "pwm_frequency_hz": 25000,
      "modbus_holding_reg": 0,
      "display_cs_pin": 17
    },
    {
      "id": "heater",
      "name": "HEATER",
      "pin": 14,
      "pwm_frequency_hz": 2,
      "status_led_pin": 22,
      "modbus_holding_reg": 1,
      "display_cs_pin": 13
    }
  ],
  "sensors": [
    {
      "id": "temp_bean",
      "name": "BEAN TEMP",
      "type": "MAX6675",
      "spi_bus": 0,
      "cs_pin": 12,
      "modbus_input_reg": 0,
      "display_cs_pin": 11
    }
  ]
}
```

### Key Elements of this Configuration:
1. **`system`**: Defines global parameters including device name, Modbus Slave ID (`modbus_slave_id`), and Watchdog timeout (`modbus_timeout_ms`).
2. **`spi_buses`**: Centralizes shared SPI bus hardware definitions (SCK, MOSI, MISO pin assignments) for referenced `bus_id`s.
3. **`display_defaults`**: Establishes common display parameters (shared Data/Command `dc_pin`, Reset `reset_pin`, refresh rate, graph time window, and orientation) so each component only specifies its Chip Select pin (`display_cs_pin`).
4. **`sensor_defaults`**: Establishes global polling interval (`poll_interval_ms`) for sensor reading loops.
5. **`actors`**: Defines output components with their name, GPIO pin, PWM frequency, optional `status_led_pin`, Modbus holding register index (`modbus_holding_reg`), and paired display CS pin (`display_cs_pin`).
6. **`sensors`**: Defines input devices with their name, IC type (`MAX6675`), SPI bus & CS pin, Modbus input register index (`modbus_input_reg`), and paired display CS pin (`display_cs_pin`).



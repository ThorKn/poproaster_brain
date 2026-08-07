# Specification: PopRoaster App

## 1. General Overview
The **PopRoaster App** is a Python desktop application that runs on a laptop to test, monitor, and control the `poproaster_brain` Pi Pico firmware over USB Modbus RTU.
It acts as a lightweight, custom test suite (a mini-Artisan alternative) specifically tailored to the `poproaster_brain` hardware setup.

## 2. Dynamic Configuration Integration
* **Single Source of Truth**: Reads and parses the same root `config.json` file used by the Pi Pico firmware build process.
* **Auto-Generated User Interface**:
  * **Actor Controls**: Automatically generates UI control elements (sliders, numerical spinboxes, and duty cycle % indicators) for each actor defined in `config.json`, mapping commands to its `modbus_holding_reg`.
  * **Sensor Telemetry**: Automatically generates live numerical readouts and real-time temperature trend graphs for each sensor defined in `config.json`, periodically polling its `modbus_input_reg`.

## 3. Technology Stack & Dependencies
* **Language**: Python 3 (3.10+).
* **GUI Framework**: PyQt6 (version `qt6 <= 6.7`).
* **Plotting Engine**: `pyqtgraph` (or Matplotlib Qt backend) for smooth real-time telemetry line graphs.
* **Modbus Communication Library**: `pymodbus` or `minimalmodbus` over `pyserial` (supporting `/dev/ttyACM*` on Linux, `COMx` on Windows, `/dev/cu.usbmodem*` on macOS).

## 4. User Interface & GUI Design Layout

### 4.1. Header Panel (Connection & Accessible Status)
* **Serial Connection Controls**: COM port dropdown selector (`/dev/ttyACM*`, `COMx`), **Refresh Ports** button, Modbus Slave ID field, and Connect/Disconnect toggle button.
* **Accessible Connection Status Badge**:
  * **Color-Blind Accessible Design**: Combines **text status words**, **symbols/icons**, and **background colors** so status is never conveyed by color alone:
    * 🟢 **Connected**: `[✓] CONNECTED` (Green background).
    * 🟡 **Warning**: `[⚠] WARNING (TIMEOUT)` (Yellow background).
    * 🔴 **Disconnected**: `[✗] DISCONNECTED` (Red background).

### 4.2. Control & Telemetry Panels (Auto-Generated from `config.json`)
* **Actor Controls**:
  * Auto-generated card per actor (e.g. `FAN`, `HEATER`).
  * Continuous slider (`0`–`100`%), numerical spinbox (`0`–`100`%), and quick-action mute/full power buttons.
  * **Heater Status LED Indicator**: Dedicated visual icon showing solid ON when duty cycle > 0%, OFF when 0%, and slow blinking during watchdog warning phase.
* **Sensor Monitoring**:
  * Auto-generated card per sensor (e.g. `BEAN TEMP`).
  * Large digital readout displaying temperature in °C (decoded from x10 fixed-point Modbus registers).
  * Accessible sensor state badge (`[✓] NORMAL`, `[⚠] FAULT / OPEN`).

### 4.3. Real-Time Telemetry Graphing
* **Engine**: Built with `pyqtgraph` for hardware-accelerated 60 FPS graph rendering.
* **Axes**:
  * **X-Axis**: Elapsed roast time formatted as `MM:SS`.
  * **Y-Axis (Primary / Left)**: Temperature in °C.
  * **Y-Axis (Secondary / Right)**: Actor power / duty cycle percentages (0–100%).
* **Interactive Features**: Auto-scroll to current time, Pan/Zoom, Legend toggle, and **Reset View** button.

### 4.4. Modbus Packet Inspector & Console
* **Collapsible Log Drawer**: Bottom console detailing real-time serial Modbus traffic:
  * Timestamps, Modbus Function Codes (`0x03`, `0x04`, `0x06`), raw hexadecimal packet buffers, response latency (ms), and CRC check status.
  * **Log Controls**: Clear Console, Pause Auto-scroll, Filter (Errors Only / All), and **Export Log** to `.log` / `.txt` file.

### 4.5. Application Preferences & Persistence
* Uses PyQt `QSettings` (`config.ini`) to persist user settings across sessions:
  * Last connected serial port.
  * Main window geometry and splitter panel proportions.
  * Graph time window and Modern Dark Mode color scheme.

## 5. Software Architecture & Directory Layout
* **Repository Location**: Separated into its own directory inside the project repository (e.g. [host_app/](file:///home/moss/Documents/hardware/popRoaster/poproaster_brain/host_app/)).
* **Core Application Modules**:
  1. `main.py`: Entry point and Application lifecycle management.
  2. `config_loader.py`: Parses `config.json` and builds dynamic UI widgets & register maps.
  3. `modbus_worker.py`: Background `QThread` executing Modbus RTU serial polling and watchdog heartbeats without blocking the PyQt UI thread.
  4. `gui_main_window.py`: PyQt6 Main Window assembling Header, Control Sidebar, Telemetry Graph, and Packet Inspector.

## 6. Error Handling & Safety Simulation
* **Connection Watchdog Simulation**: Periodic polling maintains the 5-second Pico watchdog heartbeat.
* **Modbus Exception Resilience**: Captures CRC errors, timeout exceptions, and serial disconnects gracefully with visual status alerts.

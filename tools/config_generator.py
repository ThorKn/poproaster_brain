#!/usr/bin/env python3
"""
PopRoaster Brain - Pre-Compile Configuration Generator & Validator
Reads config.json, runs 8 compile-time validation test cases, and outputs
include/generated_config.h for zero-overhead firmware compilation.
"""

import json
import sys
import os

def rp2040_pwm_slice(gpio_pin):
    """RP2040 GPIO pin to PWM slice mapping: Slice = (pin >> 1) % 8"""
    return (gpio_pin >> 1) & 0x07

def validate_config(config):
    errors = []

    # 1. Required Fields Test
    required_system = ["device_name", "modbus_slave_id", "modbus_timeout_ms"]
    if "system" not in config:
        errors.append("Missing required top-level key: 'system'")
    else:
        for field in required_system:
            if field not in config["system"]:
                errors.append(f"Missing required field in system config: '{field}'")

    if "spi_buses" not in config or not isinstance(config["spi_buses"], list):
        errors.append("Missing or invalid 'spi_buses' list")

    if "display_defaults" not in config:
        errors.append("Missing required top-level key: 'display_defaults'")

    if "actors" not in config or not isinstance(config["actors"], list):
        errors.append("Missing or invalid 'actors' list")

    if "sensors" not in config or not isinstance(config["sensors"], list):
        errors.append("Missing or invalid 'sensors' list")

    if errors:
        return errors

    # 2. GPIO Pins Collection & Range Test
    assigned_gpios = {}

    def claim_gpio(pin, usage_desc):
        if not isinstance(pin, int) or pin < 0 or pin > 29:
            errors.append(f"GPIO pin out of range (0-29): {pin} for '{usage_desc}'")
            return
        if pin in assigned_gpios:
            errors.append(f"GPIO collision on Pin {pin}: Assigned to both '{assigned_gpios[pin]}' and '{usage_desc}'")
        else:
            assigned_gpios[pin] = usage_desc

    # Claim SPI Pins
    valid_bus_ids = set()
    for bus in config.get("spi_buses", []):
        bus_id = bus.get("bus_id")
        if bus_id is None:
            errors.append("SPI bus missing 'bus_id'")
            continue
        valid_bus_ids.add(bus_id)
        claim_gpio(bus.get("sck_pin"), f"SPI Bus {bus_id} SCK")
        claim_gpio(bus.get("mosi_pin"), f"SPI Bus {bus_id} MOSI")
        claim_gpio(bus.get("miso_pin"), f"SPI Bus {bus_id} MISO")

    # Claim Display Defaults Pins
    display_def = config.get("display_defaults", {})
    claim_gpio(display_def.get("dc_pin"), "Display Shared D/C")
    claim_gpio(display_def.get("reset_pin"), "Display Shared RESET")

    # 3. Actor Validation & PWM Slice Conflict Test
    holding_regs = {}
    pwm_slice_freqs = {}

    for actor in config.get("actors", []):
        actor_id = actor.get("id", "unknown")
        pin = actor.get("pin")
        claim_gpio(pin, f"Actor '{actor_id}' PWM Pin")

        status_led = actor.get("status_led_pin")
        if status_led is not None:
            claim_gpio(status_led, f"Actor '{actor_id}' Status LED Pin")

        display_cs = actor.get("display_cs_pin")
        if display_cs is None:
            errors.append(f"Actor '{actor_id}' missing 'display_cs_pin'")
        else:
            claim_gpio(display_cs, f"Actor '{actor_id}' Display CS Pin")

        # Modbus Holding Register Uniqueness Test
        h_reg = actor.get("modbus_holding_reg")
        if h_reg is None or not isinstance(h_reg, int) or h_reg < 0:
            errors.append(f"Actor '{actor_id}' has invalid 'modbus_holding_reg'")
        elif h_reg in holding_regs:
            errors.append(f"Modbus holding register collision on index {h_reg}: '{holding_regs[h_reg]}' and '{actor_id}'")
        else:
            holding_regs[h_reg] = actor_id

        # PWM Slice Conflict Check
        freq = actor.get("pwm_frequency_hz")
        if freq is None or not isinstance(freq, (int, float)) or freq <= 0:
            errors.append(f"Actor '{actor_id}' has invalid 'pwm_frequency_hz'")
        elif pin is not None and isinstance(pin, int) and 0 <= pin <= 29:
            slice_num = rp2040_pwm_slice(pin)
            if slice_num in pwm_slice_freqs:
                existing_freq, existing_actor = pwm_slice_freqs[slice_num]
                if existing_freq != freq:
                    errors.append(
                        f"PWM Slice {slice_num} frequency collision: Actor '{existing_actor}' uses {existing_freq} Hz "
                        f"while Actor '{actor_id}' on pin {pin} attempts to use {freq} Hz. Slices share hardware clocks!"
                    )
            else:
                pwm_slice_freqs[slice_num] = (freq, actor_id)

    # 4. Sensor Validation
    input_regs = {}
    for sensor in config.get("sensors", []):
        sensor_id = sensor.get("id", "unknown")
        spi_bus = sensor.get("spi_bus", 0)

        if spi_bus not in valid_bus_ids:
            errors.append(f"Sensor '{sensor_id}' references invalid SPI bus_id '{spi_bus}'")

        cs_pin = sensor.get("cs_pin")
        if cs_pin is None:
            errors.append(f"Sensor '{sensor_id}' missing 'cs_pin'")
        else:
            claim_gpio(cs_pin, f"Sensor '{sensor_id}' CS Pin")

        display_cs = sensor.get("display_cs_pin")
        if display_cs is None:
            errors.append(f"Sensor '{sensor_id}' missing 'display_cs_pin'")
        else:
            claim_gpio(display_cs, f"Sensor '{sensor_id}' Display CS Pin")

        # Modbus Input Register Uniqueness Test
        i_reg = sensor.get("modbus_input_reg")
        if i_reg is None or not isinstance(i_reg, int) or i_reg < 0:
            errors.append(f"Sensor '{sensor_id}' has invalid 'modbus_input_reg'")
        elif i_reg in input_regs:
            errors.append(f"Modbus input register collision on index {i_reg}: '{input_regs[i_reg]}' and '{sensor_id}'")
        else:
            input_regs[i_reg] = sensor_id

    return errors

def generate_cpp_header(config, header_path):
    system = config["system"]
    disp_def = config["display_defaults"]
    sens_def = config.get("sensor_defaults", {"poll_interval_ms": 250})
    spi_buses = config.get("spi_buses", [])
    actors = config.get("actors", [])
    sensors = config.get("sensors", [])

    lines = [
        "// AUTO-GENERATED BY tools/config_generator.py - DO NOT EDIT MANUALLY",
        "#ifndef GENERATED_CONFIG_H",
        "#define GENERATED_CONFIG_H",
        "",
        "#include <cstdint>",
        "",
        "namespace Config {",
        "",
        "// System Settings",
        f'constexpr const char* DEVICE_NAME = "{system.get("device_name", "PopRoaster Brain")}";',
        f'constexpr uint8_t MODBUS_SLAVE_ID = {system.get("modbus_slave_id", 1)};',
        f'constexpr uint32_t MODBUS_TIMEOUT_MS = {system.get("modbus_timeout_ms", 5000)};',
        "",
        "// Display Defaults",
        f'constexpr uint8_t DISPLAY_DC_PIN = {disp_def.get("dc_pin", 20)};',
        f'constexpr uint8_t DISPLAY_RESET_PIN = {disp_def.get("reset_pin", 21)};',
        f'constexpr uint32_t DISPLAY_UPDATE_RATE_MS = {disp_def.get("update_rate_ms", 100)};',
        f'constexpr uint32_t DISPLAY_GRAPH_TIME_WINDOW_S = {disp_def.get("graph_time_window_s", 60)};',
        f'constexpr uint8_t DISPLAY_ROTATION = {disp_def.get("rotation", 0)};',
        "",
        "// Sensor Defaults",
        f'constexpr uint32_t SENSOR_POLL_INTERVAL_MS = {sens_def.get("poll_interval_ms", 250)};',
        "",
        "// SPI Bus Definitions",
        f"constexpr size_t SPI_BUS_COUNT = {len(spi_buses)};",
        "struct SpiBusConfig {",
        "    uint8_t bus_id;",
        "    uint8_t sck_pin;",
        "    uint8_t mosi_pin;",
        "    uint8_t miso_pin;",
        "};",
        "constexpr SpiBusConfig SPI_BUSES[] = {"
    ]

    for bus in spi_buses:
        lines.append(f'    {{{bus["bus_id"]}, {bus["sck_pin"]}, {bus["mosi_pin"]}, {bus["miso_pin"]}}},')
    lines.append("};")
    lines.append("")

    lines.extend([
        "// Actor Definitions",
        f"constexpr size_t ACTOR_COUNT = {len(actors)};",
        "struct ActorConfig {",
        "    const char* id;",
        "    const char* name;",
        "    uint8_t pin;",
        "    uint32_t pwm_frequency_hz;",
        "    int8_t status_led_pin; // -1 if unused",
        "    uint16_t modbus_holding_reg;",
        "    uint8_t display_cs_pin;",
        "};",
        "constexpr ActorConfig ACTORS[] = {"
    ])

    for a in actors:
        led_pin = a.get("status_led_pin", -1)
        if led_pin is None:
            led_pin = -1
        lines.append(
            f'    {{"{a["id"]}", "{a["name"]}", {a["pin"]}, {a["pwm_frequency_hz"]}, '
            f'{led_pin}, {a["modbus_holding_reg"]}, {a["display_cs_pin"]}}},'
        )
    lines.append("};")
    lines.append("")

    lines.extend([
        "// Sensor Definitions",
        f"constexpr size_t SENSOR_COUNT = {len(sensors)};",
        "struct SensorConfig {",
        "    const char* id;",
        "    const char* name;",
        "    const char* type;",
        "    uint8_t spi_bus;",
        "    uint8_t cs_pin;",
        "    uint16_t modbus_input_reg;",
        "    uint8_t display_cs_pin;",
        "};",
        "constexpr SensorConfig SENSORS[] = {"
    ])

    for s in sensors:
        lines.append(
            f'    {{"{s["id"]}", "{s["name"]}", "{s["type"]}", {s.get("spi_bus", 0)}, '
            f'{s["cs_pin"]}, {s["modbus_input_reg"]}, {s["display_cs_pin"]}}},'
        )
    lines.append("};")
    lines.append("")

    lines.extend([
        "} // namespace Config",
        "",
        "#endif // GENERATED_CONFIG_H",
        ""
    ])

    os.makedirs(os.path.dirname(header_path), exist_ok=True)
    with open(header_path, "w") as f:
        f.write("\n".join(lines))

def main():
    if len(sys.argv) < 3:
        print("Usage: config_generator.py <path/to/config.json> <path/to/output_header.h>")
        sys.exit(1)

    config_path = sys.argv[1]
    header_path = sys.argv[2]

    if not os.path.exists(config_path):
        print(f"Error: Config file not found at '{config_path}'")
        sys.exit(1)

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except Exception as e:
        print(f"Error reading JSON from '{config_path}': {e}")
        sys.exit(1)

    errors = validate_config(config)
    if errors:
        print("==================================================")
        print("CONFIG VALIDATION FAILED - Compile-Time Errors:")
        for err in errors:
            print(f"  ❌ {err}")
        print("==================================================")
        sys.exit(1)

    print(f"✅ Config validation passed! Generating C++ header at '{header_path}'")
    generate_cpp_header(config, header_path)

if __name__ == "__main__":
    main()

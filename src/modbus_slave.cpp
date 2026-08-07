#include "modbus_slave.h"
#include "generated_config.h"
#include "pwm_actors.h"
#include "max6675_sensor.h"
#include "pico/stdlib.h"
#include "pico/stdio.h"
#include <cstdio>

uint32_t ModbusSlave::s_last_valid_frame_time_ms = 0;
uint8_t ModbusSlave::s_rx_buf[256] = {0};
size_t ModbusSlave::s_rx_index = 0;

void ModbusSlave::init() {
    s_rx_index = 0;
    s_last_valid_frame_time_ms = to_ms_since_boot(get_absolute_time());
}

uint16_t ModbusSlave::calculate_crc16(const uint8_t* buffer, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t pos = 0; pos < len; pos++) {
        crc ^= (uint16_t)buffer[pos];
        for (int i = 8; i != 0; i--) {
            if ((crc & 0x0001) != 0) {
                crc >>= 1;
                crc ^= 0xA001;
            } else {
                crc >>= 1;
            }
        }
    }
    return crc;
}

void ModbusSlave::send_response(const uint8_t* response, size_t len) {
    for (size_t i = 0; i < len; ++i) {
        putchar_raw(response[i]);
    }
    stdio_flush();
}

void ModbusSlave::send_exception(uint8_t slave_id, uint8_t func, uint8_t exception_code) {
    uint8_t frame[5];
    frame[0] = slave_id;
    frame[1] = func | 0x80;
    frame[2] = exception_code;

    uint16_t crc = calculate_crc16(frame, 3);
    frame[3] = crc & 0xFF;
    frame[4] = (crc >> 8) & 0xFF;

    send_response(frame, 5);
}

void ModbusSlave::process_frame(const uint8_t* frame, size_t len) {
    if (len < 4) return;

    uint8_t slave_id = frame[0];
    if (slave_id != Config::MODBUS_SLAVE_ID && slave_id != 0) return; // Ignore frames for other slaves

    uint16_t crc_received = frame[len - 2] | (frame[len - 1] << 8);
    uint16_t crc_calculated = calculate_crc16(frame, len - 2);

    if (crc_received != crc_calculated) return; // Bad CRC, drop frame

    // Reset Watchdog Timer on valid frame
    reset_watchdog();

    uint8_t func = frame[1];

    // Function 0x03: Read Holding Registers (Actors)
    if (func == 0x03) {
        if (len < 8) return;
        uint16_t reg_addr = (frame[2] << 8) | frame[3];
        uint16_t reg_count = (frame[4] << 8) | frame[5];

        if (reg_addr + reg_count > Config::ACTOR_COUNT) {
            send_exception(slave_id, func, 0x02); // Illegal Data Address
            return;
        }

        uint8_t resp[256];
        resp[0] = slave_id;
        resp[1] = func;
        resp[2] = reg_count * 2;

        size_t idx = 3;
        for (uint16_t r = 0; r < reg_count; ++r) {
            uint16_t val = PwmActors::get_duty_cycle(reg_addr + r);
            resp[idx++] = (val >> 8) & 0xFF;
            resp[idx++] = val & 0xFF;
        }

        uint16_t crc = calculate_crc16(resp, idx);
        resp[idx++] = crc & 0xFF;
        resp[idx++] = (crc >> 8) & 0xFF;

        send_response(resp, idx);
    }
    // Function 0x04: Read Input Registers (Sensors)
    else if (func == 0x04) {
        if (len < 8) return;
        uint16_t reg_addr = (frame[2] << 8) | frame[3];
        uint16_t reg_count = (frame[4] << 8) | frame[5];

        if (reg_addr + reg_count > Config::SENSOR_COUNT) {
            send_exception(slave_id, func, 0x02); // Illegal Data Address
            return;
        }

        uint8_t resp[256];
        resp[0] = slave_id;
        resp[1] = func;
        resp[2] = reg_count * 2;

        size_t idx = 3;
        for (uint16_t r = 0; r < reg_count; ++r) {
            SensorData data = Max6675Sensor::get_data(reg_addr + r);
            int16_t val = data.is_fault ? -10 : data.temperature_x10;
            resp[idx++] = (val >> 8) & 0xFF;
            resp[idx++] = val & 0xFF;
        }

        uint16_t crc = calculate_crc16(resp, idx);
        resp[idx++] = crc & 0xFF;
        resp[idx++] = (crc >> 8) & 0xFF;

        send_response(resp, idx);
    }
    // Function 0x06: Write Single Holding Register (Actor Duty Cycle)
    else if (func == 0x06) {
        if (len < 8) return;
        uint16_t reg_addr = (frame[2] << 8) | frame[3];
        uint16_t reg_val = (frame[4] << 8) | frame[5];

        if (reg_addr >= Config::ACTOR_COUNT) {
            send_exception(slave_id, func, 0x02);
            return;
        }

        // Thermal safety interlock: if sensor in fault state, lock heater to 0%
        if (Max6675Sensor::is_any_fault() && reg_addr == 1) {
            reg_val = 0;
        }

        PwmActors::set_duty_cycle(reg_addr, (uint8_t)reg_val);

        // Echo response for FC 0x06
        send_response(frame, 8);
    }
    // Function 0x10: Write Multiple Holding Registers
    else if (func == 0x10) {
        if (len < 9) return;
        uint16_t reg_addr = (frame[2] << 8) | frame[3];
        uint16_t reg_count = (frame[4] << 8) | frame[5];

        if (reg_addr + reg_count > Config::ACTOR_COUNT) {
            send_exception(slave_id, func, 0x02);
            return;
        }

        size_t data_idx = 7;
        for (uint16_t r = 0; r < reg_count; ++r) {
            uint16_t val = (frame[data_idx] << 8) | frame[data_idx + 1];
            data_idx += 2;

            if (Max6675Sensor::is_any_fault() && (reg_addr + r) == 1) {
                val = 0;
            }
            PwmActors::set_duty_cycle(reg_addr + r, (uint8_t)val);
        }

        uint8_t resp[8];
        resp[0] = slave_id;
        resp[1] = func;
        resp[2] = (reg_addr >> 8) & 0xFF;
        resp[3] = reg_addr & 0xFF;
        resp[4] = (reg_count >> 8) & 0xFF;
        resp[5] = reg_count & 0xFF;

        uint16_t crc = calculate_crc16(resp, 6);
        resp[6] = crc & 0xFF;
        resp[7] = (crc >> 8) & 0xFF;

        send_response(resp, 8);
    } else {
        send_exception(slave_id, func, 0x01); // Illegal Function
    }
}

void ModbusSlave::poll() {
    int c = getchar_timeout_us(0);
    while (c != PICO_ERROR_TIMEOUT) {
        if (s_rx_index < sizeof(s_rx_buf)) {
            s_rx_buf[s_rx_index++] = (uint8_t)c;
        } else {
            s_rx_index = 0; // Overflow reset
        }
        c = getchar_timeout_us(0);
    }

    if (s_rx_index > 0) {
        // Frame boundary check: process when at least 8 bytes received
        if (s_rx_index >= 8) {
            process_frame(s_rx_buf, s_rx_index);
            s_rx_index = 0;
        }
    }
}

void ModbusSlave::reset_watchdog() {
    s_last_valid_frame_time_ms = to_ms_since_boot(get_absolute_time());
}

bool ModbusSlave::is_watchdog_warning() {
    uint32_t elapsed = to_ms_since_boot(get_absolute_time()) - s_last_valid_frame_time_ms;
    return elapsed >= (Config::MODBUS_TIMEOUT_MS / 2) && elapsed < Config::MODBUS_TIMEOUT_MS;
}

bool ModbusSlave::is_watchdog_expired() {
    uint32_t elapsed = to_ms_since_boot(get_absolute_time()) - s_last_valid_frame_time_ms;
    return elapsed >= Config::MODBUS_TIMEOUT_MS;
}

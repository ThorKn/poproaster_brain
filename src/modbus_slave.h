#ifndef MODBUS_SLAVE_H
#define MODBUS_SLAVE_H

#include <cstdint>
#include <cstddef>

class ModbusSlave {
public:
    static void init();
    static void poll();
    static bool is_watchdog_expired();
    static bool is_watchdog_warning();
    static void reset_watchdog();

private:
    static uint32_t s_last_valid_frame_time_ms;
    static uint8_t s_rx_buf[256];
    static size_t s_rx_index;

    static uint16_t calculate_crc16(const uint8_t* buffer, size_t len);
    static void process_frame(const uint8_t* frame, size_t len);
    static void send_response(const uint8_t* response, size_t len);
    static void send_exception(uint8_t slave_id, uint8_t func, uint8_t exception_code);
};

#endif // MODBUS_SLAVE_H

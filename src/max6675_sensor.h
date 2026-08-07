#ifndef MAX6675_SENSOR_H
#define MAX6675_SENSOR_H

#include <cstdint>
#include <cstddef>
#include "generated_config.h"

struct SensorData {
    int16_t temperature_x10; // Temperature in fixed-point x10 format (e.g. 2045 = 204.5 deg C)
    bool is_fault;           // Open thermocouple fault flag
};

class Max6675Sensor {
public:
    static void init();
    static void poll_all();
    static SensorData get_data(size_t sensor_index);
    static bool is_any_fault();

private:
    static SensorData s_data[Config::SENSOR_COUNT];
    static uint8_t s_consecutive_valid[Config::SENSOR_COUNT];
};

#endif // MAX6675_SENSOR_H

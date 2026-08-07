#include "max6675_sensor.h"
#include "pico/stdlib.h"
#include "hardware/spi.h"

SensorData Max6675Sensor::s_data[Config::SENSOR_COUNT] = {};
uint8_t Max6675Sensor::s_consecutive_valid[Config::SENSOR_COUNT] = {0};

static spi_inst_t* get_spi_inst(uint8_t bus_id) {
    return (bus_id == 0) ? spi0 : spi1;
}

void Max6675Sensor::init() {
    for (size_t b = 0; b < Config::SPI_BUS_COUNT; ++b) {
        const auto& bus = Config::SPI_BUSES[b];
        spi_inst_t* spi = get_spi_inst(bus.bus_id);

        spi_init(spi, 1000000); // 1 MHz SPI clock for MAX6675 & SSD1306
        gpio_set_function(bus.sck_pin, GPIO_FUNC_SPI);
        gpio_set_function(bus.mosi_pin, GPIO_FUNC_SPI);
        gpio_set_function(bus.miso_pin, GPIO_FUNC_SPI);
    }

    for (size_t i = 0; i < Config::SENSOR_COUNT; ++i) {
        const auto& cfg = Config::SENSORS[i];
        s_data[i] = {-10, true}; // Initialized to fault state
        s_consecutive_valid[i] = 0;

        gpio_init(cfg.cs_pin);
        gpio_set_dir(cfg.cs_pin, GPIO_OUT);
        gpio_put(cfg.cs_pin, 1); // CS active low, start HIGH
    }
}

void Max6675Sensor::poll_all() {
    for (size_t i = 0; i < Config::SENSOR_COUNT; ++i) {
        const auto& cfg = Config::SENSORS[i];
        spi_inst_t* spi = get_spi_inst(cfg.spi_bus);

        // Select MAX6675 chip (CS LOW)
        gpio_put(cfg.cs_pin, 0);
        sleep_us(1);

        uint8_t buffer[2] = {0, 0};
        spi_read_blocking(spi, 0, buffer, 2);

        gpio_put(cfg.cs_pin, 1);
        sleep_us(1);

        uint16_t raw = (buffer[0] << 8) | buffer[1];

        // Bit D2 indicates thermocouple open circuit fault
        bool open_circuit = (raw & 0x04) != 0;

        if (open_circuit) {
            s_consecutive_valid[i] = 0;
            s_data[i].is_fault = true;
            s_data[i].temperature_x10 = -10; // -1.0 deg C sentinel for error
        } else {
            // Extract 12-bit temperature value (bits 14..3)
            uint16_t temp_raw = (raw >> 3) & 0x0FFF;
            // 0.25 deg C resolution -> scale by 10 => temp_raw * 2.5
            int16_t temp_x10 = (int16_t)((temp_raw * 10) / 4);

            if (s_consecutive_valid[i] < 2) {
                s_consecutive_valid[i]++;
            }

            // Self-healing recovery requires 2 consecutive valid readings
            if (s_consecutive_valid[i] >= 2) {
                s_data[i].is_fault = false;
                s_data[i].temperature_x10 = temp_x10;
            }
        }
    }
}

SensorData Max6675Sensor::get_data(size_t sensor_index) {
    if (sensor_index >= Config::SENSOR_COUNT) {
        return {-10, true};
    }
    return s_data[sensor_index];
}

bool Max6675Sensor::is_any_fault() {
    for (size_t i = 0; i < Config::SENSOR_COUNT; ++i) {
        if (s_data[i].is_fault) return true;
    }
    return false;
}

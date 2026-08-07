#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "generated_config.h"
#include "pwm_actors.h"
#include "max6675_sensor.h"
#include "ssd1306_display.h"
#include "modbus_slave.h"

// Core 1 entry point: Handles SPI Sensor Polling & OLED Display Rendering
void core1_main() {
    uint32_t last_sensor_poll = 0;
    uint32_t last_display_update = 0;

    while (true) {
        uint32_t now = to_ms_since_boot(get_absolute_time());

        // 1. Poll MAX6675 Sensors at configured interval (e.g. 250 ms)
        if (now - last_sensor_poll >= Config::SENSOR_POLL_INTERVAL_MS) {
            last_sensor_poll = now;
            Max6675Sensor::poll_all();
        }

        // 2. Refresh SSD1306 OLED Displays at configured rate (e.g. 100 ms)
        if (now - last_display_update >= Config::DISPLAY_UPDATE_RATE_MS) {
            last_display_update = now;

            for (size_t a = 0; a < Config::ACTOR_COUNT; ++a) {
                uint8_t duty = PwmActors::get_duty_cycle(a);
                Ssd1306Display::render_actor(a, duty);
            }

            for (size_t s = 0; s < Config::SENSOR_COUNT; ++s) {
                SensorData data = Max6675Sensor::get_data(s);
                Ssd1306Display::render_sensor(s, data.temperature_x10, data.is_fault);
            }
        }

        sleep_ms(10);
    }
}

// Core 0 main: Handles USB CDC Modbus RTU & Watchdog Timeout Safety Loop
int main() {
    stdio_init_all();

    PwmActors::init();
    Max6675Sensor::init();
    Ssd1306Display::init();
    ModbusSlave::init();

    // Launch Core 1 for SPI tasks
    multicore_launch_core1(core1_main);

    while (true) {
        // Poll incoming Modbus RTU commands over USB CDC
        ModbusSlave::poll();

        bool warning = ModbusSlave::is_watchdog_warning();
        bool expired = ModbusSlave::is_watchdog_expired();

        // 5-second Watchdog Emergency Shutdown
        if (expired) {
            PwmActors::set_all_duty_cycles(0);
        }

        // Thermal safety interlock: shut off heater if Bean Temp sensor fault occurs
        if (Max6675Sensor::is_any_fault()) {
            PwmActors::set_duty_cycle(1, 0); // Lock Heater (index 1) to 0%
        }

        // Update Heater status LED (Solid ON, OFF, or slow blinking)
        PwmActors::update(warning && !expired);

        sleep_ms(1);
    }

    return 0;
}

#ifndef SSD1306_DISPLAY_H
#define SSD1306_DISPLAY_H

#include <cstdint>
#include <cstddef>
#include "generated_config.h"

class Ssd1306Display {
public:
    static void init();
    static void render_actor(size_t actor_index, uint8_t duty_percent);
    static void render_sensor(size_t sensor_index, int16_t temp_x10, bool is_fault);
    static void update_all();

private:
    static constexpr size_t WIDTH = 128;
    static constexpr size_t HEIGHT = 64;
    static constexpr size_t BUFFER_SIZE = (WIDTH * HEIGHT) / 8;
    static constexpr size_t HISTORY_LEN = 128;

    static uint8_t s_framebuffer[BUFFER_SIZE];
    static uint8_t s_actor_history[Config::ACTOR_COUNT][HISTORY_LEN];
    static int16_t s_sensor_history[Config::SENSOR_COUNT][HISTORY_LEN];

    static void send_command(uint8_t cs_pin, uint8_t cmd);
    static void send_data(uint8_t cs_pin, const uint8_t* data, size_t len);
    static void init_display(uint8_t cs_pin);
    static void clear_framebuffer();
    static void flush_framebuffer(uint8_t cs_pin);

    static void draw_pixel(int x, int y, bool color);
    static void draw_line(int x0, int y0, int x1, int y1, bool color);
    static void draw_string(int x, int y, const char* str, bool color, int scale = 1);
    static void draw_char(int x, int y, char c, bool color, int scale = 1);
};

#endif // SSD1306_DISPLAY_H

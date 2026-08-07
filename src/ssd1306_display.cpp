#include "ssd1306_display.h"
#include "pico/stdlib.h"
#include "hardware/spi.h"
#include <cstring>
#include <cstdio>

uint8_t Ssd1306Display::s_framebuffer[BUFFER_SIZE] = {0};
uint8_t Ssd1306Display::s_actor_history[Config::ACTOR_COUNT][HISTORY_LEN] = {};
int16_t Ssd1306Display::s_sensor_history[Config::SENSOR_COUNT][HISTORY_LEN] = {};

// Minimal 5x7 ASCII font bitmap
static const uint8_t font5x7[][5] = {
    {0x00, 0x00, 0x00, 0x00, 0x00}, // ' ' (space)
    {0x00, 0x00, 0x5F, 0x00, 0x00}, // '!'
    {0x00, 0x07, 0x00, 0x07, 0x00}, // '"'
    {0x14, 0x7F, 0x14, 0x7F, 0x14}, // '#'
    {0x24, 0x2A, 0x7F, 0x2A, 0x12}, // '$'
    {0x23, 0x13, 0x08, 0x64, 0x62}, // '%'
    {0x36, 0x49, 0x55, 0x22, 0x50}, // '&'
    {0x00, 0x05, 0x03, 0x00, 0x00}, // '\''
    {0x00, 0x1C, 0x22, 0x41, 0x00}, // '('
    {0x00, 0x41, 0x22, 0x1C, 0x00}, // ')'
    {0x14, 0x08, 0x3E, 0x08, 0x14}, // '*'
    {0x08, 0x08, 0x3E, 0x08, 0x08}, // '+'
    {0x00, 0x50, 0x30, 0x00, 0x00}, // ','
    {0x08, 0x08, 0x08, 0x08, 0x08}, // '-'
    {0x00, 0x60, 0x60, 0x00, 0x00}, // '.'
    {0x20, 0x10, 0x08, 0x04, 0x02}, // '/'
    {0x3E, 0x51, 0x49, 0x45, 0x3E}, // '0'
    {0x00, 0x42, 0x7F, 0x40, 0x00}, // '1'
    {0x42, 0x61, 0x51, 0x49, 0x46}, // '2'
    {0x21, 0x41, 0x45, 0x4B, 0x31}, // '3'
    {0x18, 0x14, 0x12, 0x7F, 0x10}, // '4'
    {0x27, 0x45, 0x45, 0x45, 0x39}, // '5'
    {0x3C, 0x4A, 0x49, 0x49, 0x30}, // '6'
    {0x01, 0x71, 0x09, 0x05, 0x03}, // '7'
    {0x36, 0x49, 0x49, 0x49, 0x36}, // '8'
    {0x06, 0x49, 0x49, 0x29, 0x1E}, // '9'
    {0x00, 0x36, 0x36, 0x00, 0x00}, // ':'
    {0x00, 0x56, 0x36, 0x00, 0x00}, // ';'
    {0x08, 0x14, 0x22, 0x41, 0x00}, // '<'
    {0x14, 0x14, 0x14, 0x14, 0x14}, // '='
    {0x00, 0x41, 0x22, 0x14, 0x08}, // '>'
    {0x02, 0x01, 0x51, 0x09, 0x06}, // '?'
    {0x32, 0x49, 0x79, 0x41, 0x3E}, // '@'
    {0x7E, 0x11, 0x11, 0x11, 0x7E}, // 'A'
    {0x7F, 0x49, 0x49, 0x49, 0x36}, // 'B'
    {0x3E, 0x41, 0x41, 0x41, 0x22}, // 'C'
    {0x7F, 0x41, 0x41, 0x22, 0x1C}, // 'D'
    {0x7F, 0x49, 0x49, 0x49, 0x41}, // 'E'
    {0x7F, 0x09, 0x09, 0x09, 0x01}, // 'F'
    {0x3E, 0x41, 0x49, 0x49, 0x7A}, // 'G'
    {0x7F, 0x08, 0x08, 0x08, 0x7F}, // 'H'
    {0x00, 0x41, 0x7F, 0x41, 0x00}, // 'I'
    {0x20, 0x40, 0x41, 0x3F, 0x01}, // 'J'
    {0x7F, 0x08, 0x14, 0x22, 0x41}, // 'K'
    {0x7F, 0x40, 0x40, 0x40, 0x40}, // 'L'
    {0x7F, 0x02, 0x0C, 0x02, 0x7F}, // 'M'
    {0x7F, 0x04, 0x08, 0x10, 0x7F}, // 'N'
    {0x3E, 0x41, 0x41, 0x41, 0x3E}, // 'O'
    {0x7F, 0x09, 0x09, 0x09, 0x06}, // 'P'
    {0x3E, 0x41, 0x51, 0x21, 0x5E}, // 'Q'
    {0x7F, 0x09, 0x19, 0x29, 0x46}, // 'R'
    {0x46, 0x49, 0x49, 0x49, 0x31}, // 'S'
    {0x01, 0x01, 0x7F, 0x01, 0x01}, // 'T'
    {0x3F, 0x40, 0x40, 0x40, 0x3F}, // 'U'
    {0x1F, 0x20, 0x40, 0x20, 0x1F}, // 'V'
    {0x3F, 0x40, 0x38, 0x40, 0x3F}, // 'W'
    {0x63, 0x14, 0x08, 0x14, 0x63}, // 'X'
    {0x07, 0x08, 0x70, 0x08, 0x07}, // 'Y'
    {0x61, 0x51, 0x49, 0x45, 0x43}, // 'Z'
};

static spi_inst_t* get_spi_inst(uint8_t bus_id) {
    return (bus_id == 0) ? spi0 : spi1;
}

void Ssd1306Display::send_command(uint8_t cs_pin, uint8_t cmd) {
    gpio_put(Config::DISPLAY_DC_PIN, 0); // Command mode
    gpio_put(cs_pin, 0);
    spi_write_blocking(get_spi_inst(0), &cmd, 1);
    gpio_put(cs_pin, 1);
}

void Ssd1306Display::send_data(uint8_t cs_pin, const uint8_t* data, size_t len) {
    gpio_put(Config::DISPLAY_DC_PIN, 1); // Data mode
    gpio_put(cs_pin, 0);
    spi_write_blocking(get_spi_inst(0), data, len);
    gpio_put(cs_pin, 1);
}

void Ssd1306Display::init_display(uint8_t cs_pin) {
    gpio_init(cs_pin);
    gpio_set_dir(cs_pin, GPIO_OUT);
    gpio_put(cs_pin, 1);

    // Standard SSD1306 128x64 initialization sequence
    send_command(cs_pin, 0xAE); // Display OFF
    send_command(cs_pin, 0xD5); // Set Display Clock Divide Ratio
    send_command(cs_pin, 0x80);
    send_command(cs_pin, 0xA8); // Set Multiplex Ratio
    send_command(cs_pin, 0x3F); // 1/64 duty
    send_command(cs_pin, 0xD3); // Set Display Offset
    send_command(cs_pin, 0x00);
    send_command(cs_pin, 0x40); // Set Start Line 0
    send_command(cs_pin, 0x8D); // Charge Pump
    send_command(cs_pin, 0x14); // Enable Charge Pump
    send_command(cs_pin, 0x20); // Memory Addressing Mode
    send_command(cs_pin, 0x00); // Horizontal Addressing Mode
    send_command(cs_pin, 0xA1); // Segment Re-map
    send_command(cs_pin, 0xC8); // COM Output Scan Direction
    send_command(cs_pin, 0xDA); // Set COM Pins Hardware Config
    send_command(cs_pin, 0x12);
    send_command(cs_pin, 0x81); // Set Contrast Control
    send_command(cs_pin, 0xCF);
    send_command(cs_pin, 0xD9); // Set Pre-charge Period
    send_command(cs_pin, 0xF1);
    send_command(cs_pin, 0xDB); // Set VCOMH Deselect Level
    send_command(cs_pin, 0x40);
    send_command(cs_pin, 0xA4); // Entire Display ON (Resume)
    send_command(cs_pin, 0xA6); // Normal Display (non-inverted)
    send_command(cs_pin, 0xAF); // Display ON
}

void Ssd1306Display::init() {
    gpio_init(Config::DISPLAY_DC_PIN);
    gpio_set_dir(Config::DISPLAY_DC_PIN, GPIO_OUT);

    gpio_init(Config::DISPLAY_RESET_PIN);
    gpio_set_dir(Config::DISPLAY_RESET_PIN, GPIO_OUT);

    // Hardware reset pulse
    gpio_put(Config::DISPLAY_RESET_PIN, 0);
    sleep_ms(10);
    gpio_put(Config::DISPLAY_RESET_PIN, 1);
    sleep_ms(10);

    for (size_t i = 0; i < Config::ACTOR_COUNT; ++i) {
        init_display(Config::ACTORS[i].display_cs_pin);
    }
    for (size_t i = 0; i < Config::SENSOR_COUNT; ++i) {
        init_display(Config::SENSORS[i].display_cs_pin);
    }
}

void Ssd1306Display::clear_framebuffer() {
    std::memset(s_framebuffer, 0, BUFFER_SIZE);
}

void Ssd1306Display::flush_framebuffer(uint8_t cs_pin) {
    send_command(cs_pin, 0x21); // Column Address
    send_command(cs_pin, 0);
    send_command(cs_pin, 127);
    send_command(cs_pin, 0x22); // Page Address
    send_command(cs_pin, 0);
    send_command(cs_pin, 7);

    send_data(cs_pin, s_framebuffer, BUFFER_SIZE);
}

void Ssd1306Display::draw_pixel(int x, int y, bool color) {
    if (x < 0 || x >= (int)WIDTH || y < 0 || y >= (int)HEIGHT) return;
    if (color) {
        s_framebuffer[x + (y / 8) * WIDTH] |= (1 << (y % 8));
    } else {
        s_framebuffer[x + (y / 8) * WIDTH] &= ~(1 << (y % 8));
    }
}

void Ssd1306Display::draw_line(int x0, int y0, int x1, int y1, bool color) {
    int dx = (x1 > x0) ? (x1 - x0) : (x0 - x1);
    int dy = (y1 > y0) ? (y1 - y0) : (y0 - y1);
    int sx = (x0 < x1) ? 1 : -1;
    int sy = (y0 < y1) ? 1 : -1;
    int err = dx - dy;

    while (true) {
        draw_pixel(x0, y0, color);
        if (x0 == x1 && y0 == y1) break;
        int e2 = 2 * err;
        if (e2 > -dy) { err -= dy; x0 += sx; }
        if (e2 < dx) { err += dx; y0 += sy; }
    }
}

void Ssd1306Display::draw_char(int x, int y, char c, bool color, int scale) {
    if (c < ' ' || c > 'Z') c = '?';
    int idx = c - ' ';

    for (int col = 0; col < 5; ++col) {
        uint8_t bits = font5x7[idx][col];
        for (int row = 0; row < 7; ++row) {
            if (bits & (1 << row)) {
                for (int sx = 0; sx < scale; ++sx) {
                    for (int sy = 0; sy < scale; ++sy) {
                        draw_pixel(x + col * scale + sx, y + row * scale + sy, color);
                    }
                }
            }
        }
    }
}

void Ssd1306Display::draw_string(int x, int y, const char* str, bool color, int scale) {
    int cur_x = x;
    while (*str) {
        draw_char(cur_x, y, *str, color, scale);
        cur_x += 6 * scale;
        str++;
    }
}

void Ssd1306Display::render_actor(size_t actor_index, uint8_t duty_percent) {
    if (actor_index >= Config::ACTOR_COUNT) return;
    const auto& cfg = Config::ACTORS[actor_index];

    // Shift history left
    std::memmove(&s_actor_history[actor_index][0], &s_actor_history[actor_index][1], HISTORY_LEN - 1);
    s_actor_history[actor_index][HISTORY_LEN - 1] = duty_percent;

    clear_framebuffer();

    // 1. Draw Title Header
    draw_string(2, 2, cfg.name, true, 1);

    // 2. Draw Large Duty Cycle Percentage Value (Scale 2)
    char buf[16];
    std::snprintf(buf, sizeof(buf), "%3d%%", duty_percent);
    draw_string(70, 2, buf, true, 2);

    // Separator line
    draw_line(0, 20, 127, 20, true);

    // 3. Draw Trend Line Plot (y range: 63 to 22)
    for (int x = 0; x < 127; ++x) {
        uint8_t val0 = s_actor_history[actor_index][x];
        uint8_t val1 = s_actor_history[actor_index][x + 1];

        int y0 = 63 - (val0 * 41) / 100;
        int y1 = 63 - (val1 * 41) / 100;
        draw_line(x, y0, x + 1, y1, true);
    }

    flush_framebuffer(cfg.display_cs_pin);
}

void Ssd1306Display::render_sensor(size_t sensor_index, int16_t temp_x10, bool is_fault) {
    if (sensor_index >= Config::SENSOR_COUNT) return;
    const auto& cfg = Config::SENSORS[sensor_index];

    // Shift history left
    std::memmove(&s_sensor_history[sensor_index][0], &s_sensor_history[sensor_index][1], (HISTORY_LEN - 1) * sizeof(int16_t));
    s_sensor_history[sensor_index][HISTORY_LEN - 1] = is_fault ? -10 : temp_x10;

    clear_framebuffer();

    // 1. Draw Title Header
    draw_string(2, 2, cfg.name, true, 1);

    // 2. Draw Value Readout or ERR
    char buf[16];
    if (is_fault) {
        draw_string(75, 2, "ERR", true, 2);
    } else {
        int whole = temp_x10 / 10;
        int frac = temp_x10 % 10;
        if (frac < 0) frac = -frac;
        std::snprintf(buf, sizeof(buf), "%3d.%1d C", whole, frac);
        draw_string(45, 2, buf, true, 1);
    }

    // Separator line
    draw_line(0, 20, 127, 20, true);

    // 3. Draw Trend Line Plot (scaling 0 to 300 deg C across 41 pixels)
    for (int x = 0; x < 127; ++x) {
        int16_t t0 = s_sensor_history[sensor_index][x];
        int16_t t1 = s_sensor_history[sensor_index][x + 1];

        if (t0 < 0) t0 = 0;
        if (t1 < 0) t1 = 0;

        int y0 = 63 - (t0 * 41) / 3000;
        int y1 = 63 - (t1 * 41) / 3000;
        if (y0 < 22) y0 = 22; if (y0 > 63) y0 = 63;
        if (y1 < 22) y1 = 22; if (y1 > 63) y1 = 63;

        draw_line(x, y0, x + 1, y1, true);
    }

    flush_framebuffer(cfg.display_cs_pin);
}

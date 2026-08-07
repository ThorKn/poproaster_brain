#include "pwm_actors.h"
#include "pico/stdlib.h"
#include "hardware/pwm.h"
#include "hardware/clocks.h"

uint8_t PwmActors::s_duty_cycles[Config::ACTOR_COUNT] = {0};
uint32_t PwmActors::s_last_blink_time_ms = 0;
bool PwmActors::s_blink_state = false;

void PwmActors::init() {
    uint32_t sys_clk = clock_get_hz(clk_sys);

    for (size_t i = 0; i < Config::ACTOR_COUNT; ++i) {
        const auto& cfg = Config::ACTORS[i];
        s_duty_cycles[i] = 0;

        // Configure PWM pin
        gpio_set_function(cfg.pin, GPIO_FUNC_PWM);
        uint slice_num = pwm_gpio_to_slice_num(cfg.pin);
        uint chan = pwm_gpio_to_channel(cfg.pin);

        // Calculate wrap and divider for desired frequency
        uint32_t target_freq = cfg.pwm_frequency_hz;
        if (target_freq == 0) target_freq = 1000;

        // Wrap count = 10000 for high resolution
        uint32_t wrap = 10000;
        float div = (float)sys_clk / (target_freq * wrap);

        if (div < 1.0f) {
            div = 1.0f;
            wrap = sys_clk / target_freq;
        } else if (div > 255.0f) {
            div = 255.0f;
            wrap = sys_clk / (target_freq * div);
        }

        pwm_config pwm_cfg = pwm_get_default_config();
        pwm_config_set_clkdiv(&pwm_cfg, div);
        pwm_config_set_wrap(&pwm_cfg, wrap);

        pwm_init(slice_num, &pwm_cfg, true);
        pwm_set_chan_level(slice_num, chan, 0);

        // Configure status LED pin if assigned
        if (cfg.status_led_pin >= 0) {
            gpio_init(cfg.status_led_pin);
            gpio_set_dir(cfg.status_led_pin, GPIO_OUT);
            gpio_put(cfg.status_led_pin, 0);
        }
    }
}

void PwmActors::set_duty_cycle(size_t actor_index, uint8_t duty_percent) {
    if (actor_index >= Config::ACTOR_COUNT) return;
    if (duty_percent > 100) duty_percent = 100;

    s_duty_cycles[actor_index] = duty_percent;
    const auto& cfg = Config::ACTORS[actor_index];

    uint slice_num = pwm_gpio_to_slice_num(cfg.pin);
    uint chan = pwm_gpio_to_channel(cfg.pin);
    uint16_t wrap = pwm_hw->slice[slice_num].top;

    uint32_t level = (wrap * duty_percent) / 100;
    pwm_set_chan_level(slice_num, chan, level);
}

uint8_t PwmActors::get_duty_cycle(size_t actor_index) {
    if (actor_index >= Config::ACTOR_COUNT) return 0;
    return s_duty_cycles[actor_index];
}

void PwmActors::set_all_duty_cycles(uint8_t duty_percent) {
    for (size_t i = 0; i < Config::ACTOR_COUNT; ++i) {
        set_duty_cycle(i, duty_percent);
    }
}

void PwmActors::update(bool watchdog_warning) {
    uint32_t now = to_ms_since_boot(get_absolute_time());

    if (now - s_last_blink_time_ms >= 500) {
        s_last_blink_time_ms = now;
        s_blink_state = !s_blink_state;
    }

    for (size_t i = 0; i < Config::ACTOR_COUNT; ++i) {
        const auto& cfg = Config::ACTORS[i];
        if (cfg.status_led_pin < 0) continue;

        if (watchdog_warning) {
            // Blinking phase during 5s watchdog warning
            gpio_put(cfg.status_led_pin, s_blink_state ? 1 : 0);
        } else {
            // Solid ON when duty > 0%, OFF when 0%
            bool is_on = (s_duty_cycles[i] > 0);
            gpio_put(cfg.status_led_pin, is_on ? 1 : 0);
        }
    }
}

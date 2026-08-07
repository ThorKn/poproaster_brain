#ifndef PWM_ACTORS_H
#define PWM_ACTORS_H

#include <cstdint>
#include <cstddef>
#include "generated_config.h"

class PwmActors {
public:
    static void init();
    static void set_duty_cycle(size_t actor_index, uint8_t duty_percent);
    static uint8_t get_duty_cycle(size_t actor_index);
    static void set_all_duty_cycles(uint8_t duty_percent);
    static void update(bool watchdog_warning);

private:
    static uint8_t s_duty_cycles[Config::ACTOR_COUNT];
    static uint32_t s_last_blink_time_ms;
    static bool s_blink_state;
};

#endif // PWM_ACTORS_H

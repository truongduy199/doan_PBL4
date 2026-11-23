#include "actuator_controller.h"
#include "pins.h"
#include "config.example.h"
#include "driver/ledc.h"

static bool entryOpenState = false;
static bool exitOpenState = false;

// Match the tested 1000..2000 us mapping; timer 0/channel 0 remain for camera XCLK.
static uint32_t angleToDuty14Bit(int angle) {
    angle = constrain(angle, 0, 180);
    uint32_t pulseUs = SERVO_MIN_PULSE_US +
        (uint32_t)(SERVO_MAX_PULSE_US - SERVO_MIN_PULSE_US) * angle / 180UL;
    return pulseUs * 16383UL / 20000UL;
}

static void writeServoAngle(uint8_t channel, int angle) {
    ledc_set_duty(LEDC_LOW_SPEED_MODE, (ledc_channel_t)channel, angleToDuty14Bit(angle));
    ledc_update_duty(LEDC_LOW_SPEED_MODE, (ledc_channel_t)channel);
}

void initActuators() {
#if BOARD_ROLE == BOARD_ROLE_PLATE_CTRL
    ledc_timer_config_t timer = {};
    timer.speed_mode = LEDC_LOW_SPEED_MODE;
    timer.duty_resolution = LEDC_TIMER_14_BIT;
    timer.timer_num = (ledc_timer_t)SERVO_LEDC_TIMER;
    timer.freq_hz = SERVO_PWM_FREQ_HZ;
    timer.clk_cfg = LEDC_AUTO_CLK;
    ledc_timer_config(&timer);
    const int pins[] = {PIN_SERVO_IN, PIN_SERVO_OUT};
    const int channels[] = {SERVO_IN_LEDC_CHANNEL, SERVO_OUT_LEDC_CHANNEL};
    for (int i = 0; i < 2; ++i) {
        ledc_channel_config_t channel = {};
        channel.gpio_num = pins[i];
        channel.speed_mode = LEDC_LOW_SPEED_MODE;
        channel.channel = (ledc_channel_t)channels[i];
        channel.timer_sel = (ledc_timer_t)SERVO_LEDC_TIMER;
        channel.duty = angleToDuty14Bit(SERVO_ANGLE_CLOSED);
        ledc_channel_config(&channel);
    }
    closeEntryBarrier();
    closeExitBarrier();
#endif
}

void openEntryBarrier() {
#if BOARD_ROLE == BOARD_ROLE_PLATE_CTRL
    writeServoAngle(SERVO_IN_LEDC_CHANNEL, SERVO_ANGLE_OPEN);
    entryOpenState = true;
#endif
}
void closeEntryBarrier() {
#if BOARD_ROLE == BOARD_ROLE_PLATE_CTRL
    writeServoAngle(SERVO_IN_LEDC_CHANNEL, SERVO_ANGLE_CLOSED);
    entryOpenState = false;
#endif
}
void openExitBarrier() {
#if BOARD_ROLE == BOARD_ROLE_PLATE_CTRL
    writeServoAngle(SERVO_OUT_LEDC_CHANNEL, SERVO_ANGLE_OPEN);
    exitOpenState = true;
#endif
}
void closeExitBarrier() {
#if BOARD_ROLE == BOARD_ROLE_PLATE_CTRL
    writeServoAngle(SERVO_OUT_LEDC_CHANNEL, SERVO_ANGLE_CLOSED);
    exitOpenState = false;
#endif
}
bool isEntryBarrierOpenCommanded() { return entryOpenState; }
bool isExitBarrierOpenCommanded() { return exitOpenState; }

#include "actuator_controller.h"
#include "pins.h"
#include "config.example.h"

/**
 * Điều khiển 2 Servo Barie (GPIO38, GPIO39) và Còi MH-FMD (GPIO20)
 * - Dùng LEDC 14-bit, 50Hz trên kênh 2 và 3 (Timer 1) để tách hoàn toàn khỏi Timer 0 của Camera OV5640.
 * - Còi MH-FMD kích mức LOW bật / HIGH tắt, điều khiển bất đồng bộ không dùng delay() chặn đọc IR.
 */

static bool entryOpenState = false;
static bool exitOpenState = false;

static bool buzzerActive = false;
static uint8_t remainingBeeps = 0;
static bool buzzerPhaseOn = false;
static unsigned long buzzerPhaseStartMs = 0;
static unsigned long buzzerOnDurationMs = 100;
static unsigned long buzzerOffDurationMs = 80;

static uint32_t angleToDuty14Bit(int angle) {
    if (angle < 0) angle = 0;
    if (angle > 180) angle = 180;
    uint32_t pulseUs = SERVO_MIN_PULSE_US +
        ((uint32_t)(SERVO_MAX_PULSE_US - SERVO_MIN_PULSE_US) * (uint32_t)angle) / 180UL;
    // Chu kỳ 50Hz = 20000us, độ phân giải 14-bit = 16384 mức
    return (pulseUs * 16384UL) / 20000UL;
}

static void writeServoAngle(uint8_t pin, uint8_t channel, int angle) {
    uint32_t duty = angleToDuty14Bit(angle);
#if defined(ESP_ARDUINO_VERSION_MAJOR) && (ESP_ARDUINO_VERSION_MAJOR >= 3)
    ledcWriteChannel(channel, duty);
#else
    (void)pin;
    ledcWrite(channel, duty);
#endif
}

static void setBuzzerRaw(bool turnOn) {
    digitalWrite(PIN_BUZZER, turnOn ? BUZZER_ON_LEVEL : BUZZER_OFF_LEVEL);
}

void initActuators() {
#if (BOARD_ROLE == BOARD_ROLE_PLATE_CTRL)
    pinMode(PIN_BUZZER, OUTPUT);
    setBuzzerRaw(false);

#if defined(ESP_ARDUINO_VERSION_MAJOR) && (ESP_ARDUINO_VERSION_MAJOR >= 3)
    ledcAttachChannel(PIN_SERVO_IN, SERVO_PWM_FREQ_HZ, SERVO_PWM_RES_BITS, SERVO_IN_LEDC_CHANNEL);
    ledcAttachChannel(PIN_SERVO_OUT, SERVO_PWM_FREQ_HZ, SERVO_PWM_RES_BITS, SERVO_OUT_LEDC_CHANNEL);
#else
    ledcSetup(SERVO_IN_LEDC_CHANNEL, SERVO_PWM_FREQ_HZ, SERVO_PWM_RES_BITS);
    ledcAttachPin(PIN_SERVO_IN, SERVO_IN_LEDC_CHANNEL);
    ledcSetup(SERVO_OUT_LEDC_CHANNEL, SERVO_PWM_FREQ_HZ, SERVO_PWM_RES_BITS);
    ledcAttachPin(PIN_SERVO_OUT, SERVO_OUT_LEDC_CHANNEL);
#endif

    closeEntryBarrier();
    closeExitBarrier();
#endif
}

void openEntryBarrier() {
#if (BOARD_ROLE == BOARD_ROLE_PLATE_CTRL)
    writeServoAngle(PIN_SERVO_IN, SERVO_IN_LEDC_CHANNEL, SERVO_ANGLE_OPEN);
    entryOpenState = true;
#endif
}

void closeEntryBarrier() {
#if (BOARD_ROLE == BOARD_ROLE_PLATE_CTRL)
    writeServoAngle(PIN_SERVO_IN, SERVO_IN_LEDC_CHANNEL, SERVO_ANGLE_CLOSED);
    entryOpenState = false;
#endif
}

void openExitBarrier() {
#if (BOARD_ROLE == BOARD_ROLE_PLATE_CTRL)
    writeServoAngle(PIN_SERVO_OUT, SERVO_OUT_LEDC_CHANNEL, SERVO_ANGLE_OPEN);
    exitOpenState = true;
#endif
}

void closeExitBarrier() {
#if (BOARD_ROLE == BOARD_ROLE_PLATE_CTRL)
    writeServoAngle(PIN_SERVO_OUT, SERVO_OUT_LEDC_CHANNEL, SERVO_ANGLE_CLOSED);
    exitOpenState = false;
#endif
}

bool isEntryBarrierOpenCommanded() {
    return entryOpenState;
}

bool isExitBarrierOpenCommanded() {
    return exitOpenState;
}

void triggerBuzzer(unsigned long durationMs) {
    triggerBuzzerPattern(1, durationMs, 0);
}

void triggerBuzzerPattern(uint8_t beeps, unsigned long onMs, unsigned long offMs) {
#if (BOARD_ROLE == BOARD_ROLE_PLATE_CTRL)
    if (beeps == 0 || onMs == 0) return;
    remainingBeeps = beeps;
    buzzerOnDurationMs = onMs;
    buzzerOffDurationMs = offMs;
    buzzerActive = true;
    buzzerPhaseOn = true;
    buzzerPhaseStartMs = millis();
    setBuzzerRaw(true);
#endif
}

void updateActuators() {
#if (BOARD_ROLE == BOARD_ROLE_PLATE_CTRL)
    if (!buzzerActive) return;
    unsigned long nowMs = millis();

    if (buzzerPhaseOn) {
        if ((nowMs - buzzerPhaseStartMs) >= buzzerOnDurationMs) {
            setBuzzerRaw(false);
            if (remainingBeeps > 1) {
                remainingBeeps--;
                buzzerPhaseOn = false;
                buzzerPhaseStartMs = nowMs;
            } else {
                remainingBeeps = 0;
                buzzerActive = false;
            }
        }
    } else {
        if ((nowMs - buzzerPhaseStartMs) >= buzzerOffDurationMs) {
            buzzerPhaseOn = true;
            buzzerPhaseStartMs = nowMs;
            setBuzzerRaw(true);
        }
    }
#endif
}

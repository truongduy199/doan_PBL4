#include "protocol.h"
#include "pins.h"
#include "config.example.h"
#include "sensor_manager.h"
#include "gate_state_machine.h"
#include "display_controller.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <ESPmDNS.h>
#include <Preferences.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/task.h>
#if ENABLE_OV5640_CAMERA
#include "esp_camera.h"
#endif

// The loop task owns sensors, gates, actuators and OLED. Only networkTask owns
// WiFi/MQTT/HTTP/camera. Queues pass immutable copies across the task boundary.
static char bootId[32] = "boot-0";
static uint32_t sequenceCounter = 0;
static unsigned long lastSnapshotMs = 0, lastHeartbeatMs = 0;
static volatile bool cameraInitialized = false;
static volatile uint32_t queueDrops = 0;
struct Outbound { char topic[96]; char json[1200]; bool reliable; unsigned long queuedAt; };
struct GateCommand {
    char commandId[64], eventId[40], gateId[8], action[24], slot[12];
    unsigned long deadline;
    int available;
};
struct CaptureRequest { char eventId[40], gateId[8], roi[24], frameId[96]; uint64_t expiresAt; };
static QueueHandle_t outboundQueue, commandQueue, captureQueue;
static WiFiClient mqttSocket;
static PubSubClient mqttClient(mqttSocket);
static String backendHost;
static uint64_t epochBaseMs = 0;
static int64_t clockSyncUs = 0;
static unsigned long lastClockAttempt = 0;
struct PendingEvent { bool used; Outbound message; uint32_t sequence; unsigned long lastSent; };
static PendingEvent pendingEvents[16] = {};

const char* getBootId() { return bootId; }
uint32_t nextSequenceNumber() { return ++sequenceCounter; }
static uint64_t serverNowMs() {
    return epochBaseMs ? epochBaseMs + (esp_timer_get_time() - clockSyncUs) / 1000ULL : 0;
}
static void queueJson(const char* topic, JsonDocument& doc, bool reliable = false) {
    Outbound item = {};
    strlcpy(item.topic, topic, sizeof(item.topic));
    if (measureJson(doc) >= sizeof(item.json)) { ++queueDrops; return; }
    serializeJson(doc, item.json, sizeof(item.json));
    item.reliable = reliable;
    item.queuedAt = millis();
    if (!outboundQueue || xQueueSend(outboundQueue, &item, 0) != pdTRUE) ++queueDrops;
}
static void envelope(JsonDocument& doc) {
    doc["device_id"] = DEVICE_ID;
    doc["boot_id"] = bootId;
    doc["sequence"] = nextSequenceNumber();
}
void publishCommandAck(const char* commandId, const char* eventId, const char* gateId,
                       bool accepted, bool servoIssued, const char* reason) {
    JsonDocument doc; envelope(doc);
    doc["command_id"] = commandId; doc["event_id"] = eventId; doc["gate_id"] = gateId;
    doc["ack_received"] = true; doc["accepted"] = accepted;
    doc["servo_command_issued"] = servoIssued; doc["reason"] = reason;
    char topic[96]; snprintf(topic, sizeof(topic), TOPIC_DEVICE_ACK_FMT, DEVICE_ID);
    queueJson(topic, doc);
}
void publishGateDetectedEvent(const char* gateId, const char* eventId, const char* eventStatus, bool irPresent) {
    JsonDocument doc; envelope(doc);
    doc["event_id"] = eventId; doc["gate_id"] = gateId;
    doc["event_type"] = eventStatus; doc["ir_stable_detected"] = irPresent;
    queueJson(strcmp(gateId, "IN") == 0 ? TOPIC_GATE_IN_DETECTED : TOPIC_GATE_OUT_DETECTED, doc, true);
}
void publishGatePassageConfirmed(const char* gateId, const char* eventId) {
    publishGateDetectedEvent(gateId, eventId, "PASSAGE_CONFIRMED", false);
}
void publishSlotsSnapshot(bool forceImmediate) {
#if BOARD_ROLE == BOARD_ROLE_PLATE_CTRL
    unsigned long now = millis();
    if (!forceImmediate && now - lastSnapshotMs < SNAPSHOT_INTERVAL_MS) return;
    lastSnapshotMs = now;
    JsonDocument doc; envelope(doc);
    JsonArray sensors = doc["sensors"].to<JsonArray>();
    for (int i = 0; i < SLOT_COUNT; ++i) {
        SlotIndex slot = (SlotIndex)i;
        doc["slots"][getSlotIdName(slot)] = getSlotPhysicalStatusString(slot);
        JsonObject sensor = sensors.add<JsonObject>();
        sensor["slot_id"] = getSlotIdName(slot);
        sensor["sensor_id"] = getSlotSensorIdName(slot);
        sensor["raw_level"] = getSlotIrRawLevel(slot);
        sensor["stable_state"] = getSlotPhysicalStatusString(slot);
    }
    queueJson(TOPIC_SLOTS_SNAPSHOT, doc);
#else
    (void)forceImmediate;
#endif
}
void publishDeviceHeartbeat() {
    unsigned long now = millis();
    if (now - lastHeartbeatMs < HEARTBEAT_INTERVAL_MS) return;
    lastHeartbeatMs = now;
    JsonDocument doc; envelope(doc);
    doc["online"] = true; doc["camera_ready"] = cameraInitialized;
    doc["queue_drops"] = (uint32_t)queueDrops;
#if BOARD_ROLE == BOARD_ROLE_PLATE_CTRL
    const GateContext& in = getGateContext(GATE_IDX_IN);
    const GateContext& out = getGateContext(GATE_IDX_OUT);
    doc["gate_in_state"] = gateStateToString(in.state); doc["gate_in_event_id"] = in.currentEventId;
    doc["gate_out_state"] = gateStateToString(out.state); doc["gate_out_event_id"] = out.currentEventId;
#else
    doc["role"] = "face_camera";
#endif
    char topic[96]; snprintf(topic, sizeof(topic), TOPIC_DEVICE_STATUS_FMT, DEVICE_ID);
    queueJson(topic, doc);
}
static bool syncClock() {
    WiFiClient socket; HTTPClient http;
    http.setConnectTimeout(1200); http.setTimeout(1200);
    http.begin(socket, String("http://") + backendHost + ":" + BACKEND_HTTP_PORT + "/api/device/time");
    http.addHeader("X-Device-Key", DEVICE_API_KEY);
    int64_t started = esp_timer_get_time();
    int code = http.GET();
    JsonDocument doc;
    bool ok = code == 200 && !deserializeJson(doc, http.getString()) && doc["epoch_ms"].is<uint64_t>();
    if (ok && esp_timer_get_time() - started < 2000000) {
        epochBaseMs = doc["epoch_ms"].as<uint64_t>();
        clockSyncUs = esp_timer_get_time();
    } else { ok = false; }
    http.end(); return ok;
}
static void initCameraDriver() {
#if ENABLE_OV5640_CAMERA
    camera_config_t config = {};
    config.ledc_channel = LEDC_CHANNEL_0; config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = CAM_PIN_D0; config.pin_d1 = CAM_PIN_D1;
    config.pin_d2 = CAM_PIN_D2; config.pin_d3 = CAM_PIN_D3;
    config.pin_d4 = CAM_PIN_D4; config.pin_d5 = CAM_PIN_D5;
    config.pin_d6 = CAM_PIN_D6; config.pin_d7 = CAM_PIN_D7;
    config.pin_xclk = CAM_PIN_XCLK; config.pin_pclk = CAM_PIN_PCLK;
    config.pin_vsync = CAM_PIN_VSYNC; config.pin_href = CAM_PIN_HREF;
    config.pin_sccb_sda = CAM_PIN_SIOD; config.pin_sccb_scl = CAM_PIN_SIOC;
    config.pin_pwdn = CAM_PIN_PWDN; config.pin_reset = CAM_PIN_RESET;
    config.xclk_freq_hz = 20000000; config.pixel_format = PIXFORMAT_JPEG;
    config.grab_mode = CAMERA_GRAB_LATEST;
    config.frame_size = psramFound() ? FRAMESIZE_VGA : FRAMESIZE_HVGA;
    config.jpeg_quality = 12; config.fb_count = psramFound() ? 2 : 1;
    config.fb_location = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
    cameraInitialized = esp_camera_init(&config) == ESP_OK;
    Serial.printf("[CAM] ready=%d PSRAM=%d\n", cameraInitialized, psramFound());
#endif
}
bool captureAndUploadImageHttp(const char* eventId, const char* gateId, const char* roi, const char* frameId) {
#if ENABLE_OV5640_CAMERA
    if (!cameraInitialized || !WiFi.isConnected()) return false;
    // Discard one buffered frame, then obtain a frame captured after this request.
    for (int i = 0; i < 2; ++i) {
        camera_fb_t* stale = esp_camera_fb_get();
        if (stale) esp_camera_fb_return(stale);
    }
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) return false;
    WiFiClient socket; HTTPClient http;
    http.setConnectTimeout(1000); http.setTimeout(3000);
    http.begin(socket, String("http://") + backendHost + ":" + BACKEND_HTTP_PORT + BACKEND_IMAGE_PATH);
    http.addHeader("Content-Type", "image/jpeg"); http.addHeader("X-Device-Key", DEVICE_API_KEY);
    http.addHeader("X-Device-Id", DEVICE_ID); http.addHeader("X-Camera-Id", CAMERA_ID);
    http.addHeader("X-Event-Id", eventId); http.addHeader("X-Gate-Id", gateId);
    http.addHeader("X-ROI", roi); http.addHeader("X-Frame-Id", frameId);
    int code = http.POST(fb->buf, fb->len);
    esp_camera_fb_return(fb); http.end();
    Serial.printf("[IMAGE] event=%s HTTP=%d\n", eventId, code);
    return code >= 200 && code < 300;
#else
    (void)eventId; (void)gateId; (void)roi; (void)frameId;
    return false;
#endif
}
static bool unexpired(JsonDocument& doc, uint64_t maximumMs) {
    uint64_t now = serverNowMs();
    uint64_t deadline = doc["expires_at_ms"] | 0ULL;
    return now != 0 && deadline > now && deadline - now <= maximumMs;
}
static void mqttCallback(char* topic, byte* payload, unsigned int length) {
    JsonDocument doc;
    if (deserializeJson(doc, payload, length)) return;
    String ackTopic = String("parking/devices/") + DEVICE_ID + "/event_ack";
    if (ackTopic == topic) {
        uint32_t seq = doc["sequence"] | 0U;
        if (String(doc["boot_id"] | "") != bootId) return;
        for (auto& pending : pendingEvents) if (pending.used && pending.sequence == seq) pending.used = false;
        return;
    }
#if BOARD_ROLE == BOARD_ROLE_PLATE_CTRL
    if (strcmp(topic, "parking/display/status") == 0) {
        if (!unexpired(doc, 15000)) return;
        GateCommand display = {};
        strlcpy(display.action, "DISPLAY", sizeof(display.action));
        display.available = doc["available_slots"] | -1;
        xQueueSend(commandQueue, &display, 0);
        return;
    }
#endif
    if (strcmp(topic, TOPIC_CAM_CAPTURE) == 0) {
        if (!unexpired(doc, 15000)) return;
        CaptureRequest req = {};
        strlcpy(req.eventId, doc["event_id"] | "", sizeof(req.eventId));
        strlcpy(req.gateId, doc["gate_id"] | "", sizeof(req.gateId));
        strlcpy(req.roi, doc["roi"] | "", sizeof(req.roi));
        strlcpy(req.frameId, doc["frame_id"] | "", sizeof(req.frameId));
        req.expiresAt = doc["expires_at_ms"].as<uint64_t>();
        if (req.eventId[0] && req.frameId[0] && xQueueSend(captureQueue, &req, 0) != pdTRUE) ++queueDrops;
        return;
    }
#if BOARD_ROLE == BOARD_ROLE_PLATE_CTRL
    if (strcmp(topic, TOPIC_GATE_IN_COMMAND) && strcmp(topic, TOPIC_GATE_OUT_COMMAND)) return;
    if (!unexpired(doc, 15000)) return;
    const char* expectedGate = strcmp(topic, TOPIC_GATE_IN_COMMAND) == 0 ? "IN" : "OUT";
    if (strcmp(doc["gate_id"] | "", expectedGate) != 0) return;
    GateCommand cmd = {};
    strlcpy(cmd.commandId, doc["command_id"] | "", sizeof(cmd.commandId));
    strlcpy(cmd.eventId, doc["event_id"] | "", sizeof(cmd.eventId));
    strlcpy(cmd.gateId, expectedGate, sizeof(cmd.gateId));
    strlcpy(cmd.action, doc["action"] | "", sizeof(cmd.action));
    strlcpy(cmd.slot, doc["assigned_slot_id"] | "", sizeof(cmd.slot));
    uint64_t nowEpoch = serverNowMs();
    uint64_t expires = doc["expires_at_ms"].as<uint64_t>();
    cmd.deadline = millis() + (unsigned long)(expires > nowEpoch ? expires - nowEpoch : 0);
    cmd.available = doc["available_slots"] | -1;
    if (xQueueSend(commandQueue, &cmd, 0) != pdTRUE) ++queueDrops;
#endif
}
static void resolveBackend() {
    Preferences prefs;
    prefs.begin("pbl4", false);
    backendHost = prefs.getString("backend_host", BACKEND_HOST);
    if (MDNS.begin(BOARD_ROLE == BOARD_ROLE_PLATE_CTRL ? "pbl4-plate" : "pbl4-face")) {
        IPAddress address = MDNS.queryHost(BACKEND_MDNS_HOSTNAME, 1000);
        if (address != IPAddress(0,0,0,0)) backendHost = address.toString();
    }
    prefs.putString("backend_host", backendHost);
    prefs.end();
    mqttClient.setServer(backendHost.c_str(), MQTT_BROKER_PORT);
    syncClock();
}
static void networkTask(void*) {
    initCameraDriver();
    WiFi.mode(WIFI_STA); WiFi.setAutoReconnect(true); WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    mqttClient.setCallback(mqttCallback); mqttClient.setBufferSize(2048); mqttClient.setSocketTimeout(1);
    bool wasConnected = false;
    unsigned long lastRetry = 0;
    for (;;) {
        bool wifi = WiFi.isConnected();
        if (wifi && !wasConnected) resolveBackend();
        wasConnected = wifi;
        unsigned long now = millis();
        if (wifi && !mqttClient.connected() && now - lastRetry >= 3000) {
            lastRetry = now;
            if (strlen(MQTT_USERNAME) && strlen(MQTT_PASSWORD) && strlen(DEVICE_API_KEY)) {
                String clientId = String(DEVICE_ID) + "-" + bootId;
                if (mqttClient.connect(clientId.c_str(), MQTT_USERNAME, MQTT_PASSWORD)) {
                    mqttClient.subscribe(TOPIC_CAM_CAPTURE, 1);
                    String ackTopic = String("parking/devices/") + DEVICE_ID + "/event_ack";
                    mqttClient.subscribe(ackTopic.c_str(), 1);
#if BOARD_ROLE == BOARD_ROLE_PLATE_CTRL
                    mqttClient.subscribe(TOPIC_GATE_IN_COMMAND, 1); mqttClient.subscribe(TOPIC_GATE_OUT_COMMAND, 1);
                    mqttClient.subscribe("parking/display/status", 1);
#endif
                }
            }
        }
        if (wifi && now - lastClockAttempt >= 30000) { lastClockAttempt = now; syncClock(); }
        if (mqttClient.connected()) mqttClient.loop();
        Outbound item;
        if (mqttClient.connected() && xQueueReceive(outboundQueue, &item, 0) == pdTRUE) {
            if (item.reliable) {
                bool stored = false;
                for (auto& pending : pendingEvents) if (!pending.used) {
                    JsonDocument doc; deserializeJson(doc, item.json);
                    doc["occurred_at_ms"] = serverNowMs() - (unsigned long)(millis() - item.queuedAt);
                    serializeJson(doc, item.json, sizeof(item.json));
                    pending = {}; pending.used = true; pending.message = item;
                    pending.sequence = doc["sequence"] | 0U; stored = true; break;
                }
                if (!stored) ++queueDrops;
            } else mqttClient.publish(item.topic, item.json, false);
        }
        for (auto& pending : pendingEvents) if (pending.used && mqttClient.connected() && now - pending.lastSent >= 2000) {
            mqttClient.publish(pending.message.topic, pending.message.json, false); pending.lastSent = now;
        }
        CaptureRequest req;
        if (xQueueReceive(captureQueue, &req, 0) == pdTRUE && serverNowMs() < req.expiresAt)
            captureAndUploadImageHttp(req.eventId, req.gateId, req.roi, req.frameId);
        vTaskDelay(pdMS_TO_TICKS(2));
    }
}
void initNetworkAndProtocol() {
    snprintf(bootId, sizeof(bootId), "b%08lx", (unsigned long)esp_random());
    outboundQueue = xQueueCreate(32, sizeof(Outbound));
    commandQueue = xQueueCreate(8, sizeof(GateCommand));
    captureQueue = xQueueCreate(2, sizeof(CaptureRequest));
    if (!outboundQueue || !commandQueue || !captureQueue ||
        xTaskCreate(networkTask, "pbl4-network", 12288, nullptr, 1, nullptr) != pdPASS) {
        Serial.println("[ERROR] Network worker allocation failed; gates remain locally controlled/closed.");
    }
}
void updateNetworkAndProtocol() {
    GateCommand cmd;
    while (commandQueue && xQueueReceive(commandQueue, &cmd, 0) == pdTRUE) {
        if (strcmp(cmd.action, "DISPLAY") == 0) {
            updateOledDashboard(gateStateToString(getGateContext(GATE_IDX_IN).state),
                                gateStateToString(getGateContext(GATE_IDX_OUT).state),
                                getGateContext(GATE_IDX_IN).assignedSlotId, cmd.available);
            continue;
        }
        String reason;
        long remaining = (long)(cmd.deadline - millis());
        bool accepted = applyBackendGateCommand(cmd.gateId, cmd.commandId, cmd.eventId,
                                                cmd.action, cmd.slot, remaining, reason);
        publishCommandAck(cmd.commandId, cmd.eventId, cmd.gateId, accepted, reason == "SERVO_OPEN_ISSUED", reason.c_str());
        if (accepted && cmd.available >= 0) updateOledDashboard(
            gateStateToString(getGateContext(GATE_IDX_IN).state), gateStateToString(getGateContext(GATE_IDX_OUT).state),
            getGateContext(GATE_IDX_IN).assignedSlotId, cmd.available);
    }
    bool changed = consumeSlotStateChangedFlag();
    publishSlotsSnapshot(changed);
    if (changed) updateOledDashboard(gateStateToString(getGateContext(GATE_IDX_IN).state),
                                    gateStateToString(getGateContext(GATE_IDX_OUT).state),
                                    getGateContext(GATE_IDX_IN).assignedSlotId, -1);
    publishDeviceHeartbeat();
}

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
// Read-only diagnostic values: the control task never calls network APIs.
static volatile unsigned networkPhase = 0;
static volatile int networkWifiStatus = -1;
static volatile bool networkMqttConnected = false;
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
static WiFiClient mjpegSocket;
static PubSubClient mqttClient(mqttSocket);
static String backendHost;
static uint64_t epochBaseMs = 0;
static int64_t clockSyncUs = 0;
static unsigned long lastClockAttempt = 0;
struct PendingEvent { bool used; Outbound message; uint32_t sequence; unsigned long lastSent; };
static PendingEvent pendingEvents[16] = {};
struct StreamSession {
    char eventId[40], gateId[8], roi[24], streamId[40];
    uint64_t expiresAt;
    unsigned long lastFrameMs;
    uint32_t sequence;
    uint8_t failures;
};
static StreamSession streamSession = {};
static volatile bool streamActive = false;
static volatile uint32_t streamFramesSent = 0;

void printNetworkDiagnostics() {
    Serial.printf("[STATUS] uptime=%lu phase=%u wifi=%d mqtt=%d camera=%d drops=%lu\n",
                  millis(), networkPhase, networkWifiStatus, networkMqttConnected,
                  cameraInitialized, (unsigned long)queueDrops);
}

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
    doc["stream_supported"] = true;
    doc["stream_transport"] = "mjpeg";
    doc["streaming"] = streamActive;
    doc["stream_frames_sent"] = (uint32_t)streamFramesSent;
#if BOARD_ROLE == BOARD_ROLE_PLATE_CTRL
    const GateContext& in = getGateContext(GATE_IDX_IN);
    const GateContext& out = getGateContext(GATE_IDX_OUT);
    doc["gate_in_state"] = gateStateToString(in.state); doc["gate_in_event_id"] = in.currentEventId;
    doc["gate_out_state"] = gateStateToString(out.state); doc["gate_out_event_id"] = out.currentEventId;
    doc["oled_ready"] = isDisplayReady();
    doc["servo_min_us"] = SERVO_MIN_PULSE_US;
    doc["servo_max_us"] = SERVO_MAX_PULSE_US;
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
    config.frame_size = psramFound() ? CAMERA_AI_FRAME_SIZE : FRAMESIZE_HVGA;
    config.jpeg_quality = 12; config.fb_count = psramFound() ? 2 : 1;
    config.fb_location = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
    cameraInitialized = esp_camera_init(&config) == ESP_OK;
#if CAMERA_FLIP_VERTICAL || CAMERA_FLIP_HORIZONTAL
    if (cameraInitialized) {
        sensor_t* sensor = esp_camera_sensor_get();
        if (sensor && sensor->set_hmirror && sensor->set_vflip) {
            const int hmirror = CAMERA_FLIP_HORIZONTAL ? !sensor->status.hmirror : sensor->status.hmirror;
            const int vflip = CAMERA_FLIP_VERTICAL ? !sensor->status.vflip : sensor->status.vflip;
            const int mirrorResult = sensor->set_hmirror(sensor, hmirror);
            const int flipResult = sensor->set_vflip(sensor, vflip);
            cameraInitialized = mirrorResult == 0 && flipResult == 0;
            Serial.printf("[CAM] orientation hmirror=%d vflip=%d ready=%d\n",
                          hmirror, vflip, cameraInitialized);
        } else {
            cameraInitialized = false;
            Serial.println("[CAM] Sensor orientation controls unavailable");
        }
    }
#endif
    if (cameraInitialized && psramFound()) {
        sensor_t* sensor = esp_camera_sensor_get();
        cameraInitialized = sensor && sensor->set_framesize(sensor, CAMERA_LIVE_FRAME_SIZE) == 0;
    }
    Serial.printf("[CAM] ready=%d PSRAM=%d\n", cameraInitialized, psramFound());
#endif
}
bool captureAndUploadImageHttp(const char* eventId, const char* gateId, const char* roi, const char* frameId, bool streamFrame) {
#if ENABLE_OV5640_CAMERA
    if (!cameraInitialized || !WiFi.isConnected()) return false;
    sensor_t* sensor = esp_camera_sensor_get();
    const bool highResolution = !streamFrame && psramFound();
    if (highResolution && (!sensor || sensor->set_framesize(sensor, CAMERA_AI_FRAME_SIZE) != 0)) return false;
    // Discard one buffered frame, then obtain a frame captured after this request.
    for (int i = 0; i < 2; ++i) {
        camera_fb_t* stale = esp_camera_fb_get();
        if (stale) esp_camera_fb_return(stale);
    }
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) {
        if (highResolution) sensor->set_framesize(sensor, CAMERA_LIVE_FRAME_SIZE);
        return false;
    }
    WiFiClient socket; HTTPClient http;
    http.setConnectTimeout(streamFrame ? 500 : 1000); http.setTimeout(streamFrame ? 800 : 3000);
    http.begin(socket, String("http://") + backendHost + ":" + BACKEND_HTTP_PORT +
               (streamFrame ? "/api/device/stream" : BACKEND_IMAGE_PATH));
    http.addHeader("Content-Type", "image/jpeg"); http.addHeader("X-Device-Key", DEVICE_API_KEY);
    http.addHeader("X-Device-Id", DEVICE_ID); http.addHeader("X-Camera-Id", CAMERA_ID);
    http.addHeader("X-Event-Id", eventId); http.addHeader("X-Gate-Id", gateId);
    http.addHeader("X-ROI", roi); http.addHeader("X-Frame-Id", frameId);
    int code = http.POST(fb->buf, fb->len);
    esp_camera_fb_return(fb); http.end();
    if (highResolution) sensor->set_framesize(sensor, CAMERA_LIVE_FRAME_SIZE);
    Serial.printf("[IMAGE] event=%s HTTP=%d\n", eventId, code);
    return code >= 200 && code < 300;
#else
    (void)eventId; (void)gateId; (void)roi; (void)frameId; (void)streamFrame;
    return false;
#endif
}
static bool writeMjpegChunk(const uint8_t* data, size_t size) {
    char chunkSize[24];
    int n = snprintf(chunkSize, sizeof(chunkSize), "%x\r\n", (unsigned)size);
    return mjpegSocket.write((const uint8_t*)chunkSize, n) == (size_t)n &&
           mjpegSocket.write(data, size) == size && mjpegSocket.print("\r\n") == 2;
}
static void closeMjpeg() {
    if (mjpegSocket.connected()) {
        const char* ending = "--frame--\r\n";
        writeMjpegChunk((const uint8_t*)ending, strlen(ending));
        mjpegSocket.print("0\r\n\r\n");
    }
    mjpegSocket.stop();
}
static bool sendMjpegFrame(const char* frameId) {
#if ENABLE_OV5640_CAMERA
    if (!cameraInitialized || !WiFi.isConnected()) return false;
    // An early response means the server rejected/closed this upload.
    if (mjpegSocket.available()) mjpegSocket.stop();
    if (!mjpegSocket.connected()) {
        mjpegSocket.stop();
        if (!mjpegSocket.connect(backendHost.c_str(), BACKEND_HTTP_PORT, 700)) return false;
        mjpegSocket.setNoDelay(true);
        mjpegSocket.setTimeout(1);
        String headers = String("POST /api/device/mjpeg HTTP/1.1\r\nHost: ") + backendHost + ":" + BACKEND_HTTP_PORT +
            "\r\nContent-Type: multipart/x-mixed-replace; boundary=frame\r\nTransfer-Encoding: chunked\r\nConnection: close\r\nX-Device-Key: " + DEVICE_API_KEY +
            "\r\nX-Device-Id: " + DEVICE_ID + "\r\nX-Camera-Id: " + CAMERA_ID +
            "\r\nX-Event-Id: " + streamSession.eventId + "\r\nX-Stream-Id: " + streamSession.streamId +
            "\r\nX-Gate-Id: " + streamSession.gateId + "\r\nX-ROI: " + streamSession.roi + "\r\n\r\n";
        if (mjpegSocket.print(headers) != headers.length()) { mjpegSocket.stop(); return false; }
    }
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) return false;
    char part[192], chunkSize[24];
    int length = snprintf(part, sizeof(part), "--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\nX-Frame-Id: %s\r\n\r\n",
                          (unsigned)fb->len, frameId);
    int n = snprintf(chunkSize, sizeof(chunkSize), "%x\r\n", (unsigned)(length + fb->len + 2));
    bool ok = length > 0 && length < (int)sizeof(part) &&
        mjpegSocket.write((const uint8_t*)chunkSize, n) == (size_t)n &&
        mjpegSocket.write((const uint8_t*)part, length) == (size_t)length &&
        mjpegSocket.write(fb->buf, fb->len) == fb->len && mjpegSocket.print("\r\n\r\n") == 4;
    esp_camera_fb_return(fb);
    if (!ok) mjpegSocket.stop();
    return ok;
#else
    (void)frameId; return false;
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
    if (strcmp(topic, TOPIC_CAM_STREAM) == 0) {
        const char* action = doc["action"] | "";
        const char* streamId = doc["stream_id"] | "";
        const char* eventId = doc["event_id"] | "";
        if (strcmp(action, "STOP") == 0) {
            if (strcmp(streamSession.streamId, streamId) == 0 && strcmp(streamSession.eventId, eventId) == 0) {
                streamActive = false;
                closeMjpeg();
            }
            return;
        }
        // HTTP clock sync can lag the server by its round-trip time. Allow that
        // bounded skew when validating a full 30-second lease, then cap locally.
        if (strcmp(action, "START") || !unexpired(doc, CAMERA_STREAM_MAX_DURATION_MS + 2000UL) ||
            !streamId[0] || strlen(streamId) >= sizeof(streamSession.streamId) ||
            !eventId[0] || strlen(eventId) >= sizeof(streamSession.eventId)) return;
        const char* gate = doc["gate_id"] | "";
        const char* roi = doc["roi"] | "";
        if ((strcmp(gate, "IN") && strcmp(gate, "OUT")) ||
            (strcmp(roi, "ROI_IN") && strcmp(roi, "ROI_OUT"))) return;
        bool same = strcmp(streamSession.streamId, streamId) == 0 && strcmp(streamSession.eventId, eventId) == 0;
        if (!same) { closeMjpeg(); streamSession = {}; }
        strlcpy(streamSession.streamId, streamId, sizeof(streamSession.streamId));
        strlcpy(streamSession.eventId, eventId, sizeof(streamSession.eventId));
        strlcpy(streamSession.gateId, gate, sizeof(streamSession.gateId));
        strlcpy(streamSession.roi, roi, sizeof(streamSession.roi));
        streamSession.expiresAt = doc["expires_at_ms"].as<uint64_t>();
        const uint64_t localLimit = serverNowMs() + CAMERA_STREAM_MAX_DURATION_MS;
        if (streamSession.expiresAt > localLimit) streamSession.expiresAt = localLimit;
        streamSession.failures = 0;
        streamActive = true;
        return;
    }
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
    networkPhase = 1;
    Serial.println("[NET] camera init"); initCameraDriver();
    networkPhase = 2;
    Serial.println("[NET] Wi-Fi begin");
    WiFi.mode(WIFI_STA); WiFi.setAutoReconnect(true); WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    mqttClient.setCallback(mqttCallback); mqttClient.setBufferSize(2048); mqttClient.setSocketTimeout(1);
    bool wasConnected = false;
    unsigned long lastRetry = 0;
    for (;;) {
        networkWifiStatus = WiFi.status();
        bool wifi = WiFi.isConnected();
        if (wifi && !wasConnected) {
            networkPhase = 3;
            Serial.printf("[NET] Wi-Fi IP=%s\n", WiFi.localIP().toString().c_str());
            resolveBackend();
            Serial.printf("[NET] backend=%s\n", backendHost.c_str());
        }
        wasConnected = wifi;
        networkPhase = 4;
        unsigned long now = millis();
        if (wifi && !mqttClient.connected() && now - lastRetry >= 3000) {
            lastRetry = now;
            if (strlen(MQTT_USERNAME) && strlen(MQTT_PASSWORD) && strlen(DEVICE_API_KEY)) {
                String clientId = String(DEVICE_ID) + "-" + bootId;
                if (mqttClient.connect(clientId.c_str(), MQTT_USERNAME, MQTT_PASSWORD)) {
                    Serial.println("[NET] MQTT connected");
                    mqttClient.subscribe(TOPIC_CAM_CAPTURE, 1);
                    mqttClient.subscribe(TOPIC_CAM_STREAM, 1);
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
        networkMqttConnected = mqttClient.connected();
        static unsigned long lastNetworkLogMs = 0;
        if (Serial && now - lastNetworkLogMs >= 10000UL) {
            lastNetworkLogMs = now;
            Serial.printf("[NET] host=%s ip=%s mqtt_state=%d\n", backendHost.c_str(),
                          WiFi.localIP().toString().c_str(), mqttClient.state());
        }
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
        bool hasCapture = xQueueReceive(captureQueue, &req, 0) == pdTRUE;
        if (hasCapture && serverNowMs() < req.expiresAt)
            captureAndUploadImageHttp(req.eventId, req.gateId, req.roi, req.frameId);
        if (streamActive && (!wifi || !mqttClient.connected() || serverNowMs() >= streamSession.expiresAt))
            streamActive = false;
        if (!streamActive && mjpegSocket.connected()) closeMjpeg();
        if (!hasCapture && streamActive && millis() - streamSession.lastFrameMs >= CAMERA_STREAM_INTERVAL_MS) {
            streamSession.lastFrameMs = millis();
            char frameId[96];
            snprintf(frameId, sizeof(frameId), "live-%s-%s-%lu", streamSession.streamId,
                     BOARD_ROLE == BOARD_ROLE_PLATE_CTRL ? "plate" : "face", (unsigned long)++streamSession.sequence);
            bool ok = sendMjpegFrame(frameId);
            if (ok) { ++streamFramesSent; streamSession.failures = 0; }
            else if (++streamSession.failures >= 3) streamActive = false;
        }
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

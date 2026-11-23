#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <Arduino.h>

void initNetworkAndProtocol();
void updateNetworkAndProtocol();
void printNetworkDiagnostics();

const char* getBootId();
uint32_t nextSequenceNumber();

// Các hàm phát bản tin MQTT từ S3 điều khiển lên Backend (Mục VIII.2)
void publishGateDetectedEvent(const char* gateId, const char* eventId, const char* eventStatus, bool irPresent);
void publishGatePassageConfirmed(const char* gateId, const char* eventId);
void publishSlotsSnapshot(bool forceImmediate);
void publishDeviceHeartbeat();
void publishCommandAck(
    const char* commandId,
    const char* eventId,
    const char* gateId,
    bool accepted,
    bool servoIssued,
    const char* reason
);

// Chụp ảnh OV5640 và gửi HTTP POST /api/device/images kèm metadata
bool captureAndUploadImageHttp(
    const char* eventId,
    const char* gateId,
    const char* roi,
    const char* requestId,
    bool streamFrame = false
);

#endif // PROTOCOL_H

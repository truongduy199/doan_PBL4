#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <Arduino.h>

void parseIncomingMessage(const String& jsonStr);
void sendEvent(const char* eventType, const char* payloadJson);

#endif // PROTOCOL_H
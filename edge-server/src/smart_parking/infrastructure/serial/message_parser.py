"""Message Parser."""
import json

class MessageParser:
    @staticmethod
    def parse(line: str) -> dict:
        return json.loads(line)
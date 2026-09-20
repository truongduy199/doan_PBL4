"""Firebase Realtime Database Client."""
from smart_parking.application.ports.cloud_port import CloudPort

class FirebaseClient(CloudPort):
    def sync_session(self, session_data: dict) -> None:
        pass

    def sync_slot(self, slot_data: dict) -> None:
        pass
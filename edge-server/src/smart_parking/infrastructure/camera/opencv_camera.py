"""OpenCV Camera Adapter."""
import cv2
from smart_parking.application.ports.camera_port import CameraPort

class OpenCVCamera(CameraPort):
    def __init__(self, camera_index: int):
        self.camera_index = camera_index
        self.cap = None

    def capture_frame(self, camera_id: int):
        if self.cap is None:
            self.cap = cv2.VideoCapture(camera_id)
        ret, frame = self.cap.read()
        return frame if ret else None
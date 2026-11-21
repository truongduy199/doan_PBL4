import React from "react";
import { EmptyState } from "../../shared/components/ui";

interface CameraDrawerProps {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  cameraStatusText: string;
  onSimulateCapture?: () => void;
}

// Preview streams are optional; device status does not imply that a live stream exists.
export const CameraDrawer: React.FC<CameraDrawerProps> = ({ isOpen, setIsOpen, cameraStatusText }) => {
  if (!isOpen) return <button className="button" onClick={() => setIsOpen(true)}>Camera</button>;
  return <section className="panel" aria-label="Camera"><div className="panel-header"><div><h2>Camera</h2><p>{cameraStatusText}</p></div><button className="button button-small" onClick={() => setIsOpen(false)}>Đóng</button></div>
    <div className="panel-body device-grid">{["Camera biển số", "Camera khuôn mặt"].map((name) => <div className="device-card" key={name}><h3>{name}</h3><EmptyState>Chưa có luồng xem trước.</EmptyState></div>)}</div>
  </section>;
};

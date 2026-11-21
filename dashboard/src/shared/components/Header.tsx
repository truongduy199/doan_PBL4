import React, { useEffect, useState } from "react";
import { ParkingBrand } from "./ui";

export const Header: React.FC = () => {
  const [time, setTime] = useState("");
  useEffect(() => {
    const update = () => setTime(new Date().toLocaleTimeString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", hour: "2-digit", minute: "2-digit" }));
    update(); const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, []);
  return <header className="app-header"><div className="app-header-inner"><ParkingBrand /><span className="small muted">{time}</span></div></header>;
};

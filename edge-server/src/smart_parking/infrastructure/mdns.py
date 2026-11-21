"""Optional LAN discovery for ESP32-S3 devices."""
import socket


class MdnsAdvertisement:
    def __init__(self, lan_ip: str, port: int) -> None:
        self.lan_ip, self.port = lan_ip, port
        self.zeroconf = None
        self.info = None

    def start(self) -> None:
        from zeroconf import ServiceInfo, Zeroconf
        address = socket.inet_aton(self.lan_ip)
        self.info = ServiceInfo("_pbl4._tcp.local.", "PBL4 Parking._pbl4._tcp.local.",
                                addresses=[address], port=self.port, server="pbl4-server.local.",
                                properties={"api": "/api/device/images"})
        self.zeroconf = Zeroconf(interfaces=[self.lan_ip])
        self.zeroconf.register_service(self.info)

    def stop(self) -> None:
        if self.zeroconf:
            if self.info:
                self.zeroconf.unregister_service(self.info)
            self.zeroconf.close()

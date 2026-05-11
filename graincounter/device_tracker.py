"""在线设备追踪器 — 线程安全的设备管理 + 踢出"""
import time
import threading
from graincounter.logger import get_logger
from graincounter.user_agent import parse_user_agent, get_device_display_name

logger = get_logger()


class OnlineDeviceTracker:
    """追踪在线设备，支持踢出(5分钟冷却)，离线阈值30秒"""

    def __init__(self, offline_threshold=30):
        self._lock = threading.RLock()
        self._devices = {}
        self._kicked = {}
        self.offline_threshold = offline_threshold
        self.kick_duration = 300

    def update_activity(self, client_ip: str, user_agent: str = ""):
        now = time.time()
        with self._lock:
            if client_ip in self._devices:
                self._devices[client_ip]["last_seen"] = now
            else:
                ua_info = parse_user_agent(user_agent)
                self._devices[client_ip] = {
                    "first_seen": now,
                    "last_seen": now,
                    "detect_count": 0,
                    "ua_info": ua_info,
                    "display_name": get_device_display_name(ua_info),
                }
                logger.info(f"新设备连接: {client_ip} ({self._devices[client_ip]['display_name']})")

    def increment_detect(self, client_ip: str):
        with self._lock:
            if client_ip in self._devices:
                self._devices[client_ip]["detect_count"] += 1

    def is_kicked(self, client_ip: str) -> bool:
        with self._lock:
            if client_ip in self._kicked:
                if time.time() < self._kicked[client_ip]:
                    return True
                del self._kicked[client_ip]
            return False

    def kick(self, client_ip: str):
        with self._lock:
            self._kicked[client_ip] = time.time() + self.kick_duration
            logger.info(f"设备被踢出: {client_ip}，5分钟后自动恢复")

    def get_online_devices(self) -> list:
        now = time.time()
        online = []
        with self._lock:
            for ip, info in self._devices.items():
                if now - info["last_seen"] <= self.offline_threshold:
                    online.append({
                        "ip": ip,
                        "display_name": info["display_name"],
                        "os": info["ua_info"]["os"],
                        "browser": info["ua_info"]["browser"],
                        "brand": info["ua_info"]["brand"],
                        "connected_seconds": round(now - info["first_seen"]),
                        "detect_count": info["detect_count"],
                        "last_seen_seconds_ago": round(now - info["last_seen"]),
                        "kicked": self.is_kicked(ip),
                    })
        online.sort(key=lambda x: x["last_seen_seconds_ago"])
        return online

    def get_online_count(self) -> int:
        now = time.time()
        count = 0
        with self._lock:
            for ip, info in self._devices.items():
                if now - info["last_seen"] <= self.offline_threshold:
                    count += 1
        return count

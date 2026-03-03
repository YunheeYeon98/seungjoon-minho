#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Управление Xray процессами и генерация конфигов
Точно соответствует формату из примера
"""

import json
import os
import socket
import subprocess
import tempfile
import time
import threading
import random
import string
from pathlib import Path
from typing import Optional, Dict, Any

from lib.models import ProxyConfig
from lib.logger import logger
from lib.config import config


class XrayConfigBuilder:

    def __init__(self, socks_port: int):
        self.socks_port = socks_port
        self.log_level = "error"

    def _build_vless_outbound(self, proxy: ProxyConfig) -> Dict[str, Any]:
        """Построение VLESS outbound"""
        # Базовый user
        user = {
            "id": proxy.uuid,
            "encryption": "none"
        }

        # Добавляем flow если есть
        if "flow" in proxy.params:
            user["flow"] = proxy.params["flow"]

        # VNext структура
        vnext = [{
            "address": proxy.host,
            "port": proxy.port,
            "users": [user]
        }]

        # Stream settings
        stream_settings = {}

        # Настройка network
        if "type" in proxy.params:
            stream_settings["network"] = proxy.params["type"]
        elif "network" in proxy.params:
            stream_settings["network"] = proxy.params["network"]
        else:
            stream_settings["network"] = "tcp"

        # WebSocket настройки
        if stream_settings["network"] == "ws":
            ws_settings = {}
            if "path" in proxy.params:
                ws_settings["path"] = proxy.params["path"]
            if "host" in proxy.params:
                ws_settings["headers"] = {"Host": proxy.params["host"]}
            if ws_settings:
                stream_settings["wsSettings"] = ws_settings

        # TCP настройки
        elif stream_settings["network"] == "tcp" and "headerType" in proxy.params:
            stream_settings["tcpSettings"] = {
                "header": {
                    "type": proxy.params["headerType"]
                }
            }

        # Security
        if "security" in proxy.params:
            stream_settings["security"] = proxy.params["security"]

            if proxy.params["security"] == "tls":
                tls_settings = {
                    "serverName": proxy.params.get("sni", proxy.host),
                    "allowInsecure": True
                }
                if "alpn" in proxy.params:
                    tls_settings["alpn"] = [proxy.params["alpn"]]
                if "fp" in proxy.params:
                    tls_settings["fingerprint"] = proxy.params["fp"]
                stream_settings["tlsSettings"] = tls_settings

            elif proxy.params["security"] == "reality":
                reality_settings = {
                    "serverName": proxy.params.get("sni", proxy.host),
                    "fingerprint": proxy.params.get("fp", "chrome"),
                    "publicKey": proxy.params.get("pbk", ""),
                    "shortId": proxy.params.get("sid", ""),
                    "spiderX": proxy.params.get("spx", "/")
                }
                stream_settings["realitySettings"] = reality_settings
        else:
            stream_settings["security"] = "none"

        # Формируем outbound точно как в примере
        outbound = {
            "tag": "proxy",
            "protocol": "vless",
            "settings": {
                "vnext": vnext
            },
            "streamSettings": stream_settings
        }

        return outbound

    def _build_vmess_outbound(self, proxy: ProxyConfig) -> Dict[str, Any]:
        """Построение VMess outbound"""
        vnext= [{
            "address": proxy.host,
            "port": proxy.port,
            "users": [{
                "id": proxy.uuid,
                "alterId": proxy.aid,
                "security": proxy.scy or "auto"
            }]
        }]

        stream_settings = {
            "network": proxy.net or "tcp",
            "security": "tls" if proxy.tls == "tls" else "none"
        }

        if proxy.net == "ws" and proxy.path:
            ws_settings = {"path": proxy.path}
            if proxy.params.get("host"):
                ws_settings["headers"] = {"Host": proxy.params["host"]}
            stream_settings["wsSettings"] = ws_settings

        if proxy.tls == "tls":
            stream_settings["tlsSettings"] = {
                "serverName": proxy.host,
                "allowInsecure": True
            }

        return {
            "tag": "proxy",
            "protocol": "vmess",
            "settings": {"vnext": vnext},
            "streamSettings": stream_settings
        }

    def _build_trojan_outbound(self, proxy: ProxyConfig) -> Dict[str, Any]:
        """Построение Trojan outbound"""
        return {
            "tag": "proxy",
            "protocol": "trojan",
            "settings": {
                "servers": [{
                    "address": proxy.host,
                    "port": proxy.port,
                    "password": proxy.password
                }]
            },
            "streamSettings": {
                "network": "tcp",
                "security": "tls",
                "tlsSettings": {
                    "serverName": proxy.params.get("sni", proxy.host),
                    "allowInsecure": True
                }
            }
        }

    def _build_shadowsocks_outbound(self, proxy: ProxyConfig) -> Dict[str, Any]:
        """Построение Shadowsocks outbound"""
        # Для Xray 26+ используем "shadowsocks", для старых версий "ss"
        protocol= "shadowsocks"  # или можно определить по версии Xray

        return {
            "tag": "proxy",
            "protocol": protocol,
            "settings": {
                "servers": [{
                    "address": proxy.host,
                    "port": proxy.port,
                    "method": proxy.method,
                    "password": proxy.password,
                    "uot": True
                }]
            },
            "streamSettings": {
                "network": "tcp",
                "security": "none"
            }
        }

    def build(self, proxy: ProxyConfig) -> Dict[str, Any]:
        # Выбираем правильный outbound по протоколу
        if proxy.protocol == 'vless':
            outbound = self._build_vless_outbound(proxy)
        elif proxy.protocol == 'vmess':
            outbound = self._build_vmess_outbound(proxy)
        elif proxy.protocol == 'trojan':
            outbound = self._build_trojan_outbound(proxy)
        elif proxy.protocol in ['ss', 'shadowsocks']:
            outbound = self._build_shadowsocks_outbound(proxy)
        else:
            raise ValueError(f"Unsupported protocol: {proxy.protocol}")

        config_dict = {
            "log": {
                "loglevel": self.log_level
            },
            "inbounds": [
                {
                    "listen": "127.0.0.1",
                    "port": self.socks_port,
                    "protocol": "socks",
                    "settings": {
                        "udp": False
                    },
                    "tag": "in",
                }
            ],
            "outbounds": [
                outbound,  # наш прокси outbound
                {
                    "protocol": "freedom",
                    "tag": "direct"
                }
            ],
            "routing": {
                "domainStrategy": "IPIfNonMatch",
                "rules": [
                    {
                        "type": "field",
                        "inboundTag": ["in"],
                        "outboundTag": "proxy"
                    }
                ],
            },
        }

        return config_dict


class XrayInstance:
    """Отдельный экземпляр Xray для одного порта"""

    def __init__(self, port: int, xray_path: str):
        self.port = port
        self.xray_path = xray_path
        self.process: Optional[subprocess.Popen] = None
        self.config_file: Optional[str] = None
        self.lock = threading.Lock()

    def _check_port_open(self) -> bool:
        """Проверка, открыт ли порт"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', self.port))
            return result == 0
        finally:
            sock.close()

    def _generate_config(self, proxy: ProxyConfig) -> str:
        """Генерация и сохранение конфига"""
        builder = XrayConfigBuilder(self.port)
        config_dict = builder.build(proxy)

        # Создаем уникальное имя файла
        random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        filename = f"xray_{self.port}_{random_str}.json"
        filepath = os.path.join(tempfile.gettempdir(), filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)

        # Для отладки можно сохранить копию
        if config.DEBUG_FIRST_FAIL:
            debug_path = f"/tmp/xray_debug_{self.port}.json"
            with open(debug_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)

        return filepath

    def start(self, proxy_config: ProxyConfig) -> bool:
        """Запуск Xray на указанном порту"""
        with self.lock:
            # Проверка Xray
            if not self.xray_path or not os.path.exists(self.xray_path):
                logger.error(f"Xray not found: {self.xray_path}")
                return False

            if not os.access(self.xray_path, os.X_OK):
                logger.error(f"Xray not executable: {self.xray_path}")
                return False

            # Генерируем конфиг
            try:
                self.config_file = self._generate_config(proxy_config)
                logger.debug(f"Generated config: {self.config_file}")
            except Exception as e:
                logger.error(f"Failed to generate config: {e}")
                return False

            # Запускаем процесс
            try:
                self.process = subprocess.Popen(
                    [self.xray_path, '-c', self.config_file],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

                # Ждем запуска
                startup_wait = getattr(config, 'XRAY_STARTUP_WAIT', 1.2)
                time.sleep(startup_wait)

                # Проверяем что процесс жив
                if self.process.poll() is not None:
                    logger.error(f"Xray on port {self.port} exited immediately")
                    return False

                # Проверяем что порт открыт
                if self._check_port_open():
                    logger.debug(f"Xray started on port {self.port}")
                    return True
                else:
                    logger.error(f"Port {self.port} not open after Xray start")
                    return False

            except Exception as e:
                logger.error(f"Failed to start Xray: {e}")
                return False

    def stop(self) -> None:
        """Остановка Xray"""
        with self.lock:
            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=5)
                except:
                    try:
                        self.process.kill()
                    except:
                        pass
                finally:
                    self.process = None

            # Удаляем конфиг
            if self.config_file and os.path.exists(self.config_file):
                try:
                    os.unlink(self.config_file)
                except:
                    pass


class XrayManager:
    """Менеджер пула Xray процессов"""

    def __init__(self):
        self.xray_path = self._find_xray()
        self.instances: Dict[int, XrayInstance] = {}
        self.next_port = getattr(config, 'BASE_PORT', 20000)
        self.port_lock = threading.Lock()

    def _find_xray(self) -> Optional[str]:
        """Поиск исполняемого файла Xray"""
        if hasattr(config, 'XRAY_PATH') and config.XRAY_PATH and Path(config.XRAY_PATH).exists():
            return config.XRAY_PATH

        for path in os.environ['PATH'].split(os.pathsep):
            for name in ['xray', 'xray.exe']:
                full = Path(path) / name
                if full.exists() and os.access(full, os.X_OK):
                    return str(full)

        return None

    def is_available(self) -> bool:
        """Проверка доступности Xray"""
        if not self.xray_path:
            return False

        try:
            result = subprocess.run(
                [self.xray_path, '-version'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False

    def get_port(self) -> int:
        """Получение следующего порта"""
        with self.port_lock:
            port = self.next_port
            self.next_port += 1
            return port

    def start(self, proxy_config: ProxyConfig) -> Optional[int]:
        """Запуск Xray с конфигурацией прокси"""
        use_xray = getattr(config, 'USE_XRAY', True)
        if not use_xray:
            return 0

        if not self.is_available():
            logger.error("Xray not available")
            return None

        port = self.get_port()
        instance = XrayInstance(port, self.xray_path)

        if instance.start(proxy_config):
            self.instances[port] = instance
            return port
        else:
            return None

    def stop(self, port: int) -> None:
        """Остановка Xray на порту"""
        if port in self.instances:
            self.instances[port].stop()
            del self.instances[port]

    def stop_all(self) -> None:
        """Остановка всех Xray процессов"""
        for instance in list(self.instances.values()):
            instance.stop()
        self.instances.clear()


class XrayConfigGenerator:
    """Генератор конфигов для --print-config"""

    def __init__(self, proxy_config: ProxyConfig, local_port: int):
        self.proxy = proxy_config
        self.port = local_port
        builder = XrayConfigBuilder(local_port)
        self.config = builder.build(proxy_config)
        self.config_file = None

    def save(self, path: Optional[str] = None) -> str:
        """Сохранение конфигурации в файл"""
        if path:
            self.config_file = path
        else:
            fd, self.config_file = tempfile.mkstemp(suffix='.json', prefix=f'xray_{self.port}_')
            os.close(fd)

        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

        return self.config_file
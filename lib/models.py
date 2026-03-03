#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модели данных для проекта
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import time
import hashlib


@dataclass
class GeoLocation:
    """Геолокация по IP"""
    ip: str = ''
    country: str = ''
    region: str = ''
    city: str = ''
    isp: str = ''
    asn: str = ''
    lat: float = 0.0
    lon: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'ip': self.ip,
            'country': self.country,
            'region': self.region,
            'city': self.city,
            'isp': self.isp,
            'asn': self.asn,
            'lat': self.lat,
            'lon': self.lon
        }


@dataclass
class ProxyConfig:
    """Распарсенная конфигурация прокси"""
    protocol: str
    link: str
    normalized_link: str
    host: str
    port: int
    name: str = ''
    
    # Для VLESS/Trojan
    uuid: str = ''
    password: str = ''
    
    # Для VMess
    aid: int = 0
    net: str = 'tcp'
    type: str = 'none'
    path: str = ''
    tls: str = ''
    scy: str = 'auto'
    
    # Для Shadowsocks
    method: str = ''
    
    # Для всех
    params: Dict[str, str] = field(default_factory=dict)
    
    @property
    def stable_id(self) -> str:
        """Уникальный идентификатор конфигурации"""
        config_str = json.dumps({
            'protocol': self.protocol,
            'host': self.host,
            'port': self.port,
            'uuid': self.uuid,
            'password': self.password,
            'method': self.method,
            'net': self.net,
            'path': self.path,
            'tls': self.tls
        }, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]


@dataclass
class SpeedTestResult:
    """Результаты теста скорости"""
    mode: str = 'latency'  # latency, quick, full
    download_mbps: float = 0.0
    upload_mbps: float = 0.0
    ping_ms: float = 0.0
    jitter_ms: float = 0.0
    packet_loss: float = 0.0
    server_name: str = ''
    server_url: str = ''
    test_duration: float = 0.0
    timestamp: float = field(default_factory=time.time)
    error: Optional[str] = None
    
    @property
    def is_successful(self) -> bool:
        return self.error is None and (
            (self.mode == 'latency' and self.ping_ms > 0) or
            (self.mode in ('quick', 'full') and self.download_mbps > 0)
        )
    
    @property
    def quality_score(self) -> float:
        """Интегральная оценка качества (0-100)"""
        if not self.is_successful:
            return 0.0
        
        score = 0.0
        factors = 0
        
        if self.mode in ('quick', 'full') and self.download_mbps > 0:
            dl_score = min(100, self.download_mbps)
            score += dl_score
            factors += 1
        
        if self.mode == 'full' and self.upload_mbps > 0:
            ul_score = min(50, self.upload_mbps)
            score += ul_score
            factors += 1
        
        if self.ping_ms > 0:
            ping_score = max(0, 100 - (self.ping_ms / 2))
            score += ping_score
            factors += 1
        
        if self.jitter_ms > 0:
            score -= min(30, self.jitter_ms)
        
        if self.packet_loss > 0:
            score -= min(50, self.packet_loss * 5)
        
        return max(0, score / max(factors, 1))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'mode': self.mode,
            'download_mbps': round(self.download_mbps, 2),
            'upload_mbps': round(self.upload_mbps, 2),
            'ping_ms': round(self.ping_ms, 2),
            'jitter_ms': round(self.jitter_ms, 2),
            'packet_loss': round(self.packet_loss, 2),
            'server_name': self.server_name,
            'quality_score': round(self.quality_score, 2),
            'test_duration': round(self.test_duration, 2),
            'error': self.error
        }


@dataclass
class ProxyCheckResult:
    """Полный результат проверки прокси"""
    config: ProxyConfig
    is_working: bool = False
    response_times_ms: List[float] = field(default_factory=list)
    geo: Optional[GeoLocation] = None
    speed: Optional[SpeedTestResult] = None
    error: Optional[str] = None
    checked_at: datetime = field(default_factory=datetime.now)
    
    @property
    def avg_response_time_ms(self) -> float:
        if not self.response_times_ms:
            return 0.0
        return sum(self.response_times_ms) / len(self.response_times_ms)
    
    @property
    def min_response_time_ms(self) -> float:
        return min(self.response_times_ms) if self.response_times_ms else 0.0
    
    @property
    def max_response_time_ms(self) -> float:
        return max(self.response_times_ms) if self.response_times_ms else 0.0
    
    @property
    def success_rate(self) -> float:
        return 100.0 if self.is_working else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь для экспорта"""
        result = {
            'link': self.config.link,
            'normalized_link': self.config.normalized_link,
            'protocol': self.config.protocol,
            'host': self.config.host,
            'port': self.config.port,
            'name': self.config.name,
            'stable_id': self.config.stable_id,
            'is_working': self.is_working,
            'avg_response_time_ms': round(self.avg_response_time_ms, 2),
            'min_response_time_ms': round(self.min_response_time_ms, 2),
            'max_response_time_ms': round(self.max_response_time_ms, 2),
            'success_rate': round(self.success_rate, 2),
            'checked_at': self.checked_at.isoformat(),
            'error': self.error or '',
        }
        
        # Геолокация
        if self.geo:
            result.update({
                'geo_ip': self.geo.ip,
                'geo_country': self.geo.country,
                'geo_city': self.geo.city,
                'geo_isp': self.geo.isp,
                'geo_asn': self.geo.asn,
            })
        
        # Speedtest
        if self.speed and self.speed.is_successful:
            result.update({
                'speed_mode': self.speed.mode,
                'speed_download_mbps': round(self.speed.download_mbps, 2),
                'speed_upload_mbps': round(self.speed.upload_mbps, 2),
                'speed_ping_ms': round(self.speed.ping_ms, 2),
                'speed_jitter_ms': round(self.speed.jitter_ms, 2),
                'speed_packet_loss': round(self.speed.packet_loss, 2),
                'speed_quality_score': round(self.speed.quality_score, 2),
                'speed_server': self.speed.server_name,
            })
        
        return result
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Определение геолокации по IP с поддержкой разных сервисов
"""

import requests
from typing import Optional, Dict
from lib.models import GeoLocation
from lib.logger import logger
from lib.config import config


class GeoLocator:
    """Определение геолокации по IP"""
    
    def __init__(self):
        self.cache: Dict[str, GeoLocation] = {}
    
    def _parse_ip_api(self, data: Dict) -> Optional[GeoLocation]:
        """Парсинг ответа ip-api.com"""
        if data.get('status') != 'success':
            return None
        
        return GeoLocation(
            ip=data.get('query', ''),
            country=data.get('country', ''),
            region=data.get('regionName', ''),
            city=data.get('city', ''),
            isp=data.get('isp', ''),
            asn=data.get('as', ''),
            lat=data.get('lat', 0.0),
            lon=data.get('lon', 0.0)
        )
    
    def _parse_ipapi(self, data: Dict) -> Optional[GeoLocation]:
        """Парсинг ответа ipapi.co"""
        if data.get('error'):
            return None
        
        return GeoLocation(
            ip=data.get('ip', ''),
            country=data.get('country_name', ''),
            region=data.get('region', ''),
            city=data.get('city', ''),
            isp=data.get('org', ''),
            asn=data.get('asn', ''),
            lat=data.get('latitude', 0.0),
            lon=data.get('longitude', 0.0)
        )
    
    def _parse_httpbin(self, data: Dict) -> Optional[GeoLocation]:
        """Парсинг ответа httpbin.org"""
        # httpbin возвращает только origin IP
        return GeoLocation(ip=data.get('origin', ''))
    
    def locate(self, ip: str, timeout: int = 5) -> Optional[GeoLocation]:
        """Определение геолокации по IP"""
        if ip in self.cache:
            return self.cache[ip]
        
        # Определяем сервис из конфига
        service_url = config.GEOLOCATION_SERVICE.format(ip=ip)
        
        try:
            response = requests.get(service_url, timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                # Пробуем распарсить в зависимости от сервиса
                location = None
                if 'ip-api.com' in service_url:
                    location = self._parse_ip_api(data)
                elif 'ipapi.co' in service_url:
                    location = self._parse_ipapi(data)
                elif 'httpbin.org' in service_url:
                    location = self._parse_httpbin(data)
                
                if location:
                    self.cache[ip] = location
                    logger.debug(f"Geo located {ip}: {location.country}, {location.city}")
                    return location
                    
        except Exception as e:
            logger.debug(f"Geo service failed: {e}")
        
        return None
    
    def locate_current(self, proxies: Optional[Dict] = None) -> Optional[GeoLocation]:
        """Определение геолокации текущего IP (через прокси если указаны)"""
        try:
            # Получаем текущий IP
            response = requests.get(
                'https://api.ipify.org?format=json',
                proxies=proxies,
                timeout=10
            )
            
            if response.status_code == 200:
                ip = response.json().get('ip')
                if ip:
                    return self.locate(ip)
                    
        except Exception as e:
            logger.debug(f"Failed to get current IP: {e}")
        
        return None

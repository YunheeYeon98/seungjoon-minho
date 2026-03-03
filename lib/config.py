#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Полная конфигурация из .env со всеми переменными оригинального проекта
"""

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Полная конфигурация приложения"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _get_bool(self, name: str, default: bool) -> bool:
        """Получение булевого значения"""
        value = os.getenv(name)
        if value is None:
            return default
        return value.lower() in ('true', '1', 'yes', 'on', 'y')
    
    def _get_int(self, name: str, default: int) -> int:
        """Получение целочисленного значения"""
        try:
            return int(os.getenv(name, str(default)))
        except (ValueError, TypeError):
            return default
    
    def _get_float(self, name: str, default: float) -> float:
        """Получение значения с плавающей точкой"""
        try:
            return float(os.getenv(name, str(default)))
        except (ValueError, TypeError):
            return default
    
    def _get_list(self, name: str, default: List[str], separator: str = ',') -> List[str]:
        """Получение списка значений"""
        value = os.getenv(name)
        if not value:
            return default
        return [v.strip() for v in value.split(separator) if v.strip()]
    
    def _load_config(self):
        """Загрузка всех настроек из .env"""
        
        # ============================================================================
        # ОСНОВНЫЕ НАСТРОЙКИ
        # ============================================================================
        self.MODE = os.getenv('MODE', 'merge')
        self.DEFAULT_LIST_URL = os.getenv('DEFAULT_LIST_URL', '')
        self.LINKS_FILE = os.getenv('LINKS_FILE', 'links.txt')
        self.OUTPUT_ADD_DATE = self._get_bool('OUTPUT_ADD_DATE', False)
        self.AUTO_COMMENT = os.getenv('AUTO_COMMENT', ' verified · XRayCheck')
        self.CIDR_WHITELIST_URL = os.getenv('CIDR_WHITELIST_URL', '')
        
        # ============================================================================
        # ТЕСТОВЫЕ URL
        # ============================================================================
        self.TEST_URL = os.getenv('TEST_URL', 'http://www.google.com/generate_204')
        self.TEST_URLS = self._get_list('TEST_URLS', [
            'http://www.google.com/generate_204',
            'http://www.cloudflare.com/cdn-cgi/trace'
        ])
        self.TEST_URLS_HTTPS = self._get_list('TEST_URLS_HTTPS', [
            'https://www.gstatic.com/generate_204'
        ])
        self.REQUIRE_HTTPS = self._get_bool('REQUIRE_HTTPS', True)
        
        # ============================================================================
        # СТРОГИЙ РЕЖИМ ПРОВЕРКИ
        # ============================================================================
        self.STRONG_STYLE_TEST = self._get_bool('STRONG_STYLE_TEST', True)
        self.STRONG_STYLE_TIMEOUT = self._get_int('STRONG_STYLE_TIMEOUT', 12)
        self.STRONG_MAX_RESPONSE_TIME = self._get_float('STRONG_MAX_RESPONSE_TIME', 3.0)
        self.STRONG_DOUBLE_CHECK = self._get_bool('STRONG_DOUBLE_CHECK', True)
        self.STRONG_ATTEMPTS = self._get_int('STRONG_ATTEMPTS', 3)
        
        # ============================================================================
        # ПАРАМЕТРЫ ЗАПРОСОВ
        # ============================================================================
        self.REQUESTS_PER_URL = self._get_int('REQUESTS_PER_URL', 2)
        self.MIN_SUCCESSFUL_REQUESTS = self._get_int('MIN_SUCCESSFUL_REQUESTS', 2)
        self.MIN_SUCCESSFUL_URLS = self._get_int('MIN_SUCCESSFUL_URLS', 2)
        self.REQUEST_DELAY = self._get_float('REQUEST_DELAY', 0.1)
        self.CONNECT_TIMEOUT = self._get_int('CONNECT_TIMEOUT', 6)
        self.CONNECT_TIMEOUT_SLOW = self._get_int('CONNECT_TIMEOUT_SLOW', 15)
        self.USE_ADAPTIVE_TIMEOUT = self._get_bool('USE_ADAPTIVE_TIMEOUT', False)
        
        # ============================================================================
        # ПОВТОРНЫЕ ПОПЫТКИ
        # ============================================================================
        self.MAX_RETRIES = self._get_int('MAX_RETRIES', 1)
        self.RETRY_DELAY_BASE = self._get_float('RETRY_DELAY_BASE', 0.5)
        self.RETRY_DELAY_MULTIPLIER = self._get_float('RETRY_DELAY_MULTIPLIER', 2.0)
        
        # ============================================================================
        # ПРОВЕРКА ОТВЕТОВ
        # ============================================================================
        self.MAX_RESPONSE_TIME = self._get_float('MAX_RESPONSE_TIME', 6.0)
        self.MIN_RESPONSE_SIZE = self._get_int('MIN_RESPONSE_SIZE', 0)
        self.MAX_LATENCY_MS = self._get_int('MAX_LATENCY_MS', 2000)
        self.VERIFY_HTTPS_SSL = self._get_bool('VERIFY_HTTPS_SSL', False)
        
        # ============================================================================
        # ГЕОЛОКАЦИЯ
        # ============================================================================
        self.CHECK_GEOLOCATION = self._get_bool('CHECK_GEOLOCATION', False)
        self.GEOLOCATION_SERVICE = os.getenv('GEOLOCATION_SERVICE', 'http://httpbin.org/ip')
        self.ALLOWED_COUNTRIES = self._get_list('ALLOWED_COUNTRIES', [])
        
        # ============================================================================
        # ПРОВЕРКА СТАБИЛЬНОСТИ
        # ============================================================================
        self.STABILITY_CHECKS = self._get_int('STABILITY_CHECKS', 2)
        self.STABILITY_CHECK_DELAY = self._get_float('STABILITY_CHECK_DELAY', 2.0)
        
        # ============================================================================
        # СТРОГИЙ РЕЖИМ (STRICT MODE)
        # ============================================================================
        self.STRICT_MODE = self._get_bool('STRICT_MODE', True)
        self.STRICT_MODE_REQUIRE_ALL = self._get_bool('STRICT_MODE_REQUIRE_ALL', True)
        
        # ============================================================================
        # ПРОИЗВОДИТЕЛЬНОСТЬ И ПАРАЛЛЕЛИЗМ
        # ============================================================================
        self.MAX_WORKERS = self._get_int('MAX_WORKERS', 200)
        self.BASE_PORT = self._get_int('BASE_PORT', 20000)
        
        # ============================================================================
        # НАСТРОЙКИ XRAY
        # ============================================================================
        self.XRAY_STARTUP_WAIT = self._get_float('XRAY_STARTUP_WAIT', 1.2)
        self.XRAY_STARTUP_POLL_INTERVAL = self._get_float('XRAY_STARTUP_POLL_INTERVAL', 0.2)
        self.XRAY_PATH = os.getenv('XRAY_PATH', '/usr/local/bin/xray')
        self.XRAY_DIR_NAME = os.getenv('XRAY_DIR_NAME', 'xray_dist')
        self.USE_XRAY = self._get_bool('USE_XRAY', True)
        
        # ============================================================================
        # ОТЛАДКА
        # ============================================================================
        self.DEBUG_FIRST_FAIL = self._get_bool('DEBUG_FIRST_FAIL', True)
        
        # ============================================================================
        # ЛОГИРОВАНИЕ
        # ============================================================================
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
        self.LOG_FILE = os.getenv('LOG_FILE', '')
        self.LOG_MAX_SIZE = self._get_int('LOG_MAX_SIZE', 10485760)
        self.LOG_BACKUP_COUNT = self._get_int('LOG_BACKUP_COUNT', 5)
        self.LOG_RESPONSE_TIME = self._get_bool('LOG_RESPONSE_TIME', False)
        
        # ============================================================================
        # МЕТРИКИ И АНАЛИТИКА
        # ============================================================================
        self.LOG_METRICS = self._get_bool('LOG_METRICS', False)
        self.METRICS_FILE = os.getenv('METRICS_FILE', 'metrics.json')
        self.MIN_AVG_RESPONSE_TIME = self._get_float('MIN_AVG_RESPONSE_TIME', 0.0)
        
        # ============================================================================
        # ДОПОЛНИТЕЛЬНЫЕ ПРОВЕРКИ
        # ============================================================================
        self.TEST_POST_REQUESTS = self._get_bool('TEST_POST_REQUESTS', False)
        
        # ============================================================================
        # КЭШИРОВАНИЕ
        # ============================================================================
        self.ENABLE_CACHE = self._get_bool('ENABLE_CACHE', False)
        self.CACHE_TTL = self._get_int('CACHE_TTL', 3600)
        self.CACHE_FILE = os.getenv('CACHE_FILE', '.checker_cache.json')
        
        # ============================================================================
        # SPEEDTEST
        # ============================================================================
        self.SPEED_TEST_ENABLED = self._get_bool('SPEED_TEST_ENABLED', False)
        self.SPEED_TEST_TIMEOUT = self._get_int('SPEED_TEST_TIMEOUT', 2)
        self.SPEED_TEST_MODE = os.getenv('SPEED_TEST_MODE', 'latency')
        self.SPEED_TEST_METRIC = os.getenv('SPEED_TEST_METRIC', 'latency')
        self.SPEED_TEST_OUTPUT = os.getenv('SPEED_TEST_OUTPUT', 'separate_file')
        self.SPEED_TEST_REQUESTS = self._get_int('SPEED_TEST_REQUESTS', 5)
        self.SPEED_TEST_URL = os.getenv('SPEED_TEST_URL', 'https://www.gstatic.com/generate_204')
        self.SPEED_TEST_WORKERS = self._get_int('SPEED_TEST_WORKERS', 200)
        self.SPEED_TEST_DOWNLOAD_TIMEOUT = self._get_int('SPEED_TEST_DOWNLOAD_TIMEOUT', 30)
        self.SPEED_TEST_DOWNLOAD_URL_SMALL = os.getenv('SPEED_TEST_DOWNLOAD_URL_SMALL', 
                                                       'https://speed.cloudflare.com/__down?bytes=250000')
        self.SPEED_TEST_DOWNLOAD_URL_MEDIUM = os.getenv('SPEED_TEST_DOWNLOAD_URL_MEDIUM', 
                                                        'https://speed.cloudflare.com/__down?bytes=1000000')
        self.MIN_SPEED_THRESHOLD_MBPS = self._get_float('MIN_SPEED_THRESHOLD_MBPS', 2.5)
        
        # ============================================================================
        # ЭКСПОРТ РЕЗУЛЬТАТОВ
        # ============================================================================
        self.EXPORT_FORMAT = os.getenv('EXPORT_FORMAT', 'txt')
        self.EXPORT_DIR = os.getenv('EXPORT_DIR', './exports')
        
        # ============================================================================
        # NOTWORKERS
        # ============================================================================
        self.NOTWORKERS_FILE = os.getenv('NOTWORKERS_FILE', 'notworkers.txt')
        self.NOTWORKERS_UPDATE_ENABLED = self._get_bool('NOTWORKERS_UPDATE_ENABLED', True)
        
        # ============================================================================
        # ПУТИ
        # ============================================================================
        self.BASE_DIR = Path(__file__).parent.parent
        self.LOGS_DIR = self.BASE_DIR / 'logs'
        self.CACHE_DIR = self.BASE_DIR / 'cache'
        self.EXPORTS_DIR = self.BASE_DIR / self.EXPORT_DIR
        
        # Создаем директории
        self.LOGS_DIR.mkdir(exist_ok=True)
        self.CACHE_DIR.mkdir(exist_ok=True)
        self.EXPORTS_DIR.mkdir(exist_ok=True)
    
    def get_output_filename(self, source: str) -> str:
        """Генерация имени выходного файла"""
        if self.MODE == 'notworkers':
            base = 'notworkers_check'
        elif self.MODE == 'merge':
            base = 'available'
        else:
            # Извлекаем имя из URL
            from urllib.parse import urlparse
            parsed = urlparse(source)
            base = Path(parsed.path).stem or 'subscription'
        
        # Добавляем дату если нужно
        if self.OUTPUT_ADD_DATE:
            from datetime import datetime
            date_str = datetime.now().strftime('_%d%m%Y')
            base = f"{base}{date_str}"
        
        return f"{base}.{self.EXPORT_FORMAT}"
    
    def get_output_path(self, source: str) -> Path:
        """Получение полного пути для сохранения"""
        filename = self.get_output_filename(source)
        return self.EXPORTS_DIR / filename


config = Config()

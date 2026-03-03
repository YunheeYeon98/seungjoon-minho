#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XrayCheck - главный файл приложения
Полная реализация с поддержкой всех .env переменных
"""

import sys
import time
import json
from pathlib import Path
from typing import List

from lib.config import config
from lib.logger import setup_logging, logger
from lib.parser import SubscriptionParser, ProxyParser
from lib.models import ProxyConfig, ProxyCheckResult
from lib.checker import ProxyChecker
from lib.cache import Cache
from lib.notworkers import NotWorkersManager
from lib.exporter import ExportManager
from lib.xray_manager import XrayManager
from lib.signals import signal_handler


class XrayCheckApp:
    """Главное приложение"""
    
    def __init__(self):
        setup_logging()
        self.start_time = time.time()
        
        # Инициализация компонентов
        self.parser = SubscriptionParser()
        self.proxy_parser = ProxyParser()
        self.cache = Cache()
        self.notworkers = NotWorkersManager()
        self.checker = ProxyChecker(self.cache)
        self.xray = XrayManager()
        
        # Регистрация обработчика сигналов
        signal_handler.register('cache', self.cache.save)
        signal_handler.register('xray', self.xray.stop_all)
        
        # Результаты
        self.results: List[ProxyCheckResult] = []
        self.source = ''
    
    def print_header(self, count: int):
        """Вывод заголовка"""
        print(f"""
        XRAYCHECK v2.0".center(60)
        Source: {self.source}
        Mode: {config.MODE}
        Proxies found: {count}
        Max workers: {config.MAX_WORKERS}
        Strict mode: {'ON' if config.STRICT_MODE else 'OFF'}
        Speedtest: {config.SPEED_TEST_MODE} ({'ON' if config.SPEED_TEST_ENABLED else 'OFF'})
        Geolocation: {'ON' if config.CHECK_GEOLOCATION else 'OFF'}
        Cache: {'ON' if config.ENABLE_CACHE else 'OFF'}
        """)
    
    def load_proxies(self, urls: List[str]) -> List[ProxyConfig]:
        """Загрузка прокси из источников"""
        
        if config.MODE == 'notworkers':
            self.source = config.NOTWORKERS_FILE
            configs = self.parser.load_from_file(self.source)
            
        elif config.MODE == 'merge':
            self.source = 'merged'
            configs = []
            
            if not Path(config.LINKS_FILE).exists():
                logger.error(f"Links file not found: {config.LINKS_FILE}")
                return []
            
            with open(config.LINKS_FILE, 'r', encoding='utf-8') as f:
                links = [line.strip() for line in f if line.strip()]
            
            for link in links:
                sub_configs = self.parser.load_from_url(link)
                configs.extend(sub_configs)
                logger.info(f"Loaded {len(sub_configs)} from {link}")
        
        else:
            self.source = urls[0] if urls else config.DEFAULT_LIST_URL
            
            if self.source.startswith(('http://', 'https://')):
                configs = self.parser.load_from_url(self.source)
            else:
                configs = self.parser.load_from_file(self.source)
        
        # Дедупликация
        unique = {}
        for cfg in configs:
            if cfg.normalized_link not in unique:
                unique[cfg.normalized_link] = cfg
        
        configs = list(unique.values())

        # Фильтрация notworkers
        configs = self.notworkers.filter(configs)
        
        return configs
    
    def print_progress(self, result: ProxyCheckResult, completed: int, total: int):
        """Вывод прогресса"""
        status = "✅" if result.is_working else "❌"
        
        parts = []
        if result.response_times_ms:
            parts.append(f"{result.avg_response_time_ms:.0f}ms")
        if result.speed and result.speed.download_mbps > 0:
            parts.append(f"{result.speed.download_mbps:.1f}Mbps")
        if result.geo and result.geo.country:
            parts.append(result.geo.country)
        
        info = f" ({', '.join(parts)})" if parts else ""
        
        logger.info(f"[{completed}/{total}] {status} {result.config.protocol}://{result.config.host}{info}")
    
    def run(self) -> int:
        """Запуск приложения"""
        
        # Парсинг аргументов
        args = sys.argv[1:]
        urls = [a for a in args if not a.startswith('-')]
        flags = [a for a in args if a.startswith('-')]
        
        # Проверка --print-config
        if '--print-config' in flags or '-p' in flags:
            if urls:
                cfg = self.proxy_parser.parse(urls[0])
                if cfg:
                    from lib.xray_manager import XrayConfigGenerator
                    xray_cfg = XrayConfigGenerator(cfg, config.BASE_PORT)
                    print(json.dumps(xray_cfg.config, indent=2, ensure_ascii=False))
            return 0
        
        # Проверка Xray если нужен
        if config.USE_XRAY and not self.xray.is_available():
            logger.error("Xray not available. Please install Xray-core")
            return 1
        
        # Загрузка прокси
        configs = self.load_proxies(urls)
        
        if not configs:
            logger.error("No proxies to check")
            return 1
        
        self.print_header(len(configs))
        
        # Проверка прокси
        self.results = self.checker.check_batch(
            configs,
            callback=self.print_progress
        )
        
        # Статистика
        working = sum(1 for r in self.results if r.is_working)
        logger.info(f"\n✅ Working: {working}/{len(self.results)}")
        
        # Сохранение результатов
        output_path = config.get_output_path(self.source)
        exporter = ExportManager(output_path)
        exported = exporter.export(self.results)
        
        for fmt, path in exported.items():
            logger.info(f"✅ Exported {fmt}: {path}")
        
        # Обновление notworkers
        self.notworkers.update(self.results)
        
        # Сохранение кэша
        if config.ENABLE_CACHE:
            self.cache.save()
        
        # Время выполнения
        elapsed = time.time() - self.start_time
        logger.info(f"\n⏱️  Time: {elapsed:.1f}s")
        
        return 0


def main():
    """Точка входа"""
    app = XrayCheckApp()
    sys.exit(app.run())


if __name__ == '__main__':
    main()

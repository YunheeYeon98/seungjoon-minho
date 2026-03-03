#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестирование скорости с поддержкой разных режимов
"""

import time
import statistics
from typing import Optional, Dict, Tuple
import requests

from lib.models import SpeedTestResult
from lib.logger import logger
from lib.config import config


class SpeedTestServer:
    """Сервер для тестирования скорости"""
    
    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url.rstrip('/')
        self.ping_ms: float = 0.0


class SpeedTester:
    """Тестер скорости с разными режимами"""
    
    SERVERS = [
        SpeedTestServer("Cloudflare", "https://speed.cloudflare.com"),
        #SpeedTestServer("Google", "https://speedtest.google.com"),
        SpeedTestServer("Fast.com", "https://fast.com"),
        SpeedTestServer("LibreSpeed", "https://librespeed.org"),
    ]
    
    def __init__(self, proxies: Optional[Dict] = None, mode: str = 'latency'):
        self.proxies = proxies
        self.mode = mode
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        return session
    
    def measure_ping(self, server: SpeedTestServer, count: int = None) -> Tuple[float, float, float]:
        """
        Измерение ping и jitter
        
        Returns:
            (avg_ping_ms, jitter_ms, packet_loss_percent)
        """
        if count is None:
            count = config.SPEED_TEST_REQUESTS
        
        pings = []
        
        for i in range(count):
            try:
                start = time.time()
                response = self.session.get(
                    f"{server.url}/__down",
                    proxies=self.proxies,
                    timeout=config.SPEED_TEST_TIMEOUT
                )
                
                elapsed = (time.time() - start) * 1000
                
                if response.status_code == 200:
                    pings.append(elapsed)
                
                time.sleep(0.2)
                
            except Exception as e:
                logger.debug(f"Ping error: {e}")
                continue
        
        if not pings:
            return 0.0, 0.0, 100.0
        
        avg_ping = statistics.mean(pings)
        jitter = statistics.stdev(pings) if len(pings) > 1 else 0.0
        loss = ((count - len(pings)) / count) * 100
        
        return avg_ping, jitter, loss
    
    def measure_download(self, server: SpeedTestServer, size_bytes: int) -> float:
        """
        Измерение скорости загрузки
        """
        try:
            url = f"{server.url}/__down?bytes={size_bytes}"
            
            start = time.time()
            downloaded = 0
            
            response = self.session.get(
                url,
                proxies=self.proxies,
                timeout=config.SPEED_TEST_DOWNLOAD_TIMEOUT,
                stream=True
            )
            
            if response.status_code == 200:
                for chunk in response.iter_content(chunk_size=64*1024):
                    downloaded += len(chunk)
                    
                    elapsed = time.time() - start
                    if elapsed > config.SPEED_TEST_DOWNLOAD_TIMEOUT / 2:
                        break
                    
                    if elapsed >= 2 and downloaded >= size_bytes / 2:
                        break
                
                elapsed = time.time() - start
                if elapsed > 0:
                    return (downloaded * 8) / (elapsed * 1_000_000)
            
        except Exception as e:
            logger.debug(f"Download test error: {e}")
        
        return 0.0
    
    def find_best_server(self) -> Optional[SpeedTestServer]:
        """Поиск сервера с минимальным пингом"""
        best_server = None
        best_ping = float('inf')
        
        for server in self.SERVERS:
            try:
                ping, jitter, loss = self.measure_ping(server, count=3)
                
                if ping > 0 and ping < best_ping and loss < 50:
                    best_ping = ping
                    best_server = server
                    server.ping_ms = ping
                    
            except Exception as e:
                logger.debug(f"Error pinging {server.name}: {e}")
        
        return best_server
    
    def run_test(self) -> SpeedTestResult:
        """
        Запуск теста скорости в соответствии с режимом
        """
        result = SpeedTestResult(mode=self.mode)
        start_total = time.time()
        
        try:
            # Находим лучший сервер
            server = self.find_best_server()
            if not server:
                result.error = "No suitable server found"
                return result
            
            result.server_name = server.name
            result.server_url = server.url
            
            # Ping тест (всегда)
            ping, jitter, loss = self.measure_ping(server)
            result.ping_ms = ping
            result.jitter_ms = jitter
            result.packet_loss = loss
            
            # Download тест в зависимости от режима
            if self.mode in ('quick', 'full'):
                if self.mode == 'quick':
                    # Маленький файл
                    from urllib.parse import parse_qs, urlparse
                    parsed = urlparse(config.SPEED_TEST_DOWNLOAD_URL_SMALL)
                    query = parse_qs(parsed.query)
                    size_bytes = int(query.get('bytes', [250000])[0])
                else:
                    # Средний файл
                    from urllib.parse import parse_qs, urlparse
                    parsed = urlparse(config.SPEED_TEST_DOWNLOAD_URL_MEDIUM)
                    query = parse_qs(parsed.query)
                    size_bytes = int(query.get('bytes', [1000000])[0])
                
                result.download_mbps = self.measure_download(server, size_bytes)
            
            result.test_duration = time.time() - start_total
            
        except Exception as e:
            result.error = str(e)
            logger.error(f"Speed test failed: {e}")
        
        return result

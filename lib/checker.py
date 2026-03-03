#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка доступности прокси с retry логикой и адаптивными таймаутами
"""

import time
from typing import Optional, Dict, List, Tuple, Callable
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from lib.models import ProxyConfig, ProxyCheckResult, GeoLocation
from lib.xray_manager import XrayManager
from lib.geo import GeoLocator
from lib.speedtest import SpeedTester
from lib.cache import Cache
from lib.logger import logger
from lib.config import config


class ProxyChecker:
    """Проверка прокси на доступность"""
    
    def __init__(self, cache: Optional[Cache] = None):
        self.cache = cache or Cache()
        self.xray = XrayManager()
        self.geo = GeoLocator()
        self.speed_tester = None
        
        # Статистика для адаптивных таймаутов
        self.successful_times: List[float] = []
    
    def _create_session(self) -> requests.Session:
        """Создание сессии с поддержкой retry"""
        session = requests.Session()
        
        # Настройка retry стратегии
        retry_strategy = Retry(
            total=config.MAX_RETRIES,
            backoff_factor=config.RETRY_DELAY_BASE,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        
        return session
    
    def _get_adaptive_timeout(self) -> float:
        """Получение адаптивного таймаута на основе истории"""
        if not config.USE_ADAPTIVE_TIMEOUT or not self.successful_times:
            return config.CONNECT_TIMEOUT
        
        avg_time = sum(self.successful_times) / len(self.successful_times)
        # Таймаут = среднее время * 2 + 1 секунда запаса
        return min(avg_time * 2 + 1, config.CONNECT_TIMEOUT_SLOW)
    
    def _create_proxies_dict(self, port: int) -> Optional[Dict]:
        """Создание словаря прокси для requests"""
        if port == 0 or not config.USE_XRAY:
            return None

        return {
            "http": f"socks5h://127.0.0.1:{port}",
            "https": f"socks5h://127.0.0.1:{port}",
        }
    
    def _test_url(self, url: str, proxies: Optional[Dict], 
                  debug: bool = False) -> Tuple[bool, float, int]:
        """
        Тестирование одного URL
        
        Returns:
            (success, response_time_ms, response_size)
        """
        # Определяем таймаут
        timeout = self._get_adaptive_timeout()
        
        # Для HTTPS может быть другой таймаут
        if url.startswith('https') and config.STRONG_STYLE_TEST:
            timeout = config.STRONG_STYLE_TIMEOUT
        
        try:
            start = time.time()
            
            # Выполняем запрос
            response = requests.get(
                url,
                proxies=proxies,
                timeout=timeout,
                verify=config.VERIFY_HTTPS_SSL,
                allow_redirects=False
            )
            
            elapsed = (time.time() - start) * 1000  # в мс
            
            # Проверка размера ответа
            content_length = len(response.content)
            if config.MIN_RESPONSE_SIZE > 0 and content_length < config.MIN_RESPONSE_SIZE:
                if debug:
                    logger.debug(f"✗ {url} - response too small: {content_length} < {config.MIN_RESPONSE_SIZE}")
                return False, elapsed, content_length
            
            # Проверка кода ответа
            if response.status_code in (200, 204):
                # Проверка времени ответа
                max_time = config.MAX_RESPONSE_TIME * 1000
                if config.STRONG_STYLE_TEST:
                    max_time = config.STRONG_MAX_RESPONSE_TIME * 1000
                
                if elapsed <= max_time:
                    if debug:
                        logger.debug(f"✓ {url} - {elapsed:.0f}ms")
                    return True, elapsed, content_length
                else:
                    if debug:
                        logger.debug(f"✗ {url} - timeout ({elapsed:.0f}ms > {max_time}ms)")
            else:
                if debug:
                    logger.debug(f"✗ {url} - status {response.status_code}")
                    
        except requests.exceptions.Timeout:
            if debug:
                logger.debug(f"✗ {url} - timeout")
        except requests.exceptions.ConnectionError:
            if debug:
                logger.debug(f"✗ {url} - connection error")
        except Exception as e:
            if debug:
                logger.debug(f"✗ {url} - {e}")
        
        return False, 0, 0
    
    def _test_proxy(self, proxies: Optional[Dict], debug: bool = False) -> Tuple[bool, List[float]]:
        """
        Тестирование прокси на всех тестовых URL
        
        Returns:
            (success, response_times_ms)
        """
        response_times = []
        successful_urls = 0
        
        # Определяем URL для тестирования
        test_urls = list(config.TEST_URLS_HTTPS) if config.REQUIRE_HTTPS else list(config.TEST_URLS)
        if config.STRONG_STYLE_TEST:
            test_urls = config.TEST_URLS_HTTPS
        
        for url in test_urls:
            url_success = False
            url_times = []
            
            # Делаем несколько запросов к одному URL
            for attempt in range(config.REQUESTS_PER_URL):
                # Задержка между запросами
                if attempt > 0 and config.REQUEST_DELAY > 0:
                    time.sleep(config.REQUEST_DELAY)
                
                success, elapsed, size = self._test_url(url, proxies, debug)
                
                if success:
                    url_times.append(elapsed)
                    url_success = True
                    
                    # Обновляем статистику для адаптивных таймаутов
                    if config.USE_ADAPTIVE_TIMEOUT:
                        self.successful_times.append(elapsed / 1000)  # в секунды
                        # Ограничиваем размер истории
                        if len(self.successful_times) > 100:
                            self.successful_times.pop(0)
            
            # Проверяем достаточно ли успешных запросов к этому URL
            if url_success and len(url_times) >= config.MIN_SUCCESSFUL_REQUESTS:
                successful_urls += 1
                response_times.extend(url_times)
            
            # Ранний выход при достаточном количестве успешных URL
            if config.MIN_SUCCESSFUL_URLS > 0 and successful_urls >= config.MIN_SUCCESSFUL_URLS:
                break
        
        # Успех если достаточно успешных URL
        success = successful_urls >= config.MIN_SUCCESSFUL_URLS
        return success, response_times
    
    def _check_country_allowed(self, geo: Optional[GeoLocation]) -> bool:
        """Проверка, разрешена ли страна"""
        if not config.ALLOWED_COUNTRIES or not geo:
            return True
        
        return geo.country in config.ALLOWED_COUNTRIES
    
    def check(self, proxy_config: ProxyConfig, debug: bool = False) -> ProxyCheckResult:
        """
        Полная проверка одного прокси
        """
        result = ProxyCheckResult(config=proxy_config)
        
        # Проверка кэша
        if config.ENABLE_CACHE:
            cached = self.cache.get(proxy_config.stable_id)
            if cached:
                logger.debug(f"Cache hit for {proxy_config.stable_id}")
                return cached
        
        logger.info(f"Checking {proxy_config.protocol}://{proxy_config.host}:{proxy_config.port}")
        
        port = None
        try:
            # Запуск Xray
            port = self.xray.start(proxy_config)
            if port is None:
                result.error = "Failed to start Xray"
                return result
            
            proxies = self._create_proxies_dict(port)
            
            # Проверка стабильности
            working_count = 0
            all_times = []
            
            for i in range(config.STABILITY_CHECKS):
                success, times = self._test_proxy(proxies, debug and i == 0)
                if success:
                    working_count += 1
                    all_times.extend(times)
                
                if i < config.STABILITY_CHECKS - 1:
                    time.sleep(config.STABILITY_CHECK_DELAY)
            
            # Определяем работоспособность
            result.is_working = working_count >= 1  # хотя бы одна успешная проверка стабильности
            result.response_times_ms = all_times
            
            if result.is_working:
                # Геолокация
                if config.CHECK_GEOLOCATION:
                    result.geo = self.geo.locate_current(proxies)
                    
                    # Фильтрация по странам
                    if not self._check_country_allowed(result.geo):
                        result.is_working = False
                        result.error = f"Country {result.geo.country} not allowed"
                        return result
                
                # Speedtest
                if config.SPEED_TEST_ENABLED:
                    logger.info(f"Running speedtest for {proxy_config.host}")
                    self.speed_tester = SpeedTester(proxies, mode=config.SPEED_TEST_MODE)
                    speed_result = self.speed_tester.run_test()
                    
                    # Фильтр по минимальной скорости
                    if speed_result.download_mbps >= config.MIN_SPEED_THRESHOLD_MBPS:
                        result.speed = speed_result
                    else:
                        logger.debug(f"Speed too low: {speed_result.download_mbps} Mbps")
                        if config.STRICT_MODE and config.STRICT_MODE_REQUIRE_ALL:
                            result.is_working = False
                            result.error = f"Speed too low: {speed_result.download_mbps} Mbps"
            
            # Сохраняем в кэш
            if config.ENABLE_CACHE:
                self.cache.set(proxy_config.stable_id, result)
            
        except Exception as e:
            result.error = str(e)
            logger.error(f"Check failed: {e}")
        
        finally:
            if port is not None and port > 0:
                self.xray.stop(port)
        
        return result
    
    def check_batch(self, configs: List[ProxyConfig], 
                   callback: Optional[Callable[[ProxyCheckResult, int, int], None]] = None) -> List[ProxyCheckResult]:
        """
        Параллельная проверка нескольких прокси
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = []
        total = len(configs)
        
        with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
            futures = {
                executor.submit(self.check, cfg, i == 0 and config.DEBUG_FIRST_FAIL): i 
                for i, cfg in enumerate(configs)
            }
            
            completed = 0
            for future in as_completed(futures):
                completed += 1
                try:
                    result = future.result()
                    results.append(result)
                    
                    if callback:
                        callback(result, completed, total)
                        
                except Exception as e:
                    logger.error(f"Batch check error: {e}")
        
        return results

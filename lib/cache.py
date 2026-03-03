#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Кэширование результатов проверки
"""

import pickle
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from lib.models import ProxyCheckResult
from lib.logger import logger
from lib.config import config


class Cache:
    """Кэш результатов проверки"""
    
    def __init__(self, ttl_hours: int = 24):
        self.cache_dir = config.CACHE_DIR
        self.cache_file = self.cache_dir / 'cache.pkl'
        self.ttl = timedelta(hours=ttl_hours)
        self.data: Dict[str, Dict] = self._load()
    
    def _load(self) -> Dict[str, Dict]:
        """Загрузка кэша из файла"""
        if not self.cache_file.exists():
            return {}
        
        try:
            with open(self.cache_file, 'rb') as f:
                data = pickle.load(f)
            
            # Очистка устаревших записей
            now = datetime.now()
            valid = {}
            
            for key, entry in data.items():
                timestamp = datetime.fromisoformat(entry['timestamp'])
                if now - timestamp < self.ttl:
                    valid[key] = entry
            
            if len(valid) < len(data):
                logger.info(f"Cleaned {len(data) - len(valid)} expired cache entries")
            
            return valid
            
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")
            return {}
    
    def save(self) -> None:
        """Сохранение кэша в файл"""
        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.data, f)
            logger.debug(f"Cache saved: {len(self.data)} entries")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
    
    def get(self, key: str) -> Optional[ProxyCheckResult]:
        """Получение результата из кэша"""
        if key in self.data:
            entry = self.data[key]
            # Проверка TTL
            timestamp = datetime.fromisoformat(entry['timestamp'])
            if datetime.now() - timestamp < self.ttl:
                return entry['result']
            else:
                # Удаляем устаревшее
                del self.data[key]
        return None
    
    def set(self, key: str, result: ProxyCheckResult) -> None:
        """Сохранение результата в кэш"""
        self.data[key] = {
            'result': result,
            'timestamp': datetime.now().isoformat()
        }
    
    def clear(self) -> None:
        """Очистка кэша"""
        self.data.clear()
        self.save()
    
    def get_stats(self) -> Dict[str, Any]:
        """Статистика кэша"""
        total = len(self.data)
        now = datetime.now()
        expired = 0
        
        for entry in self.data.values():
            timestamp = datetime.fromisoformat(entry['timestamp'])
            if now - timestamp >= self.ttl:
                expired += 1
        
        return {
            'total_entries': total,
            'expired_entries': expired,
            'active_entries': total - expired,
            'cache_file': str(self.cache_file),
            'ttl_hours': self.ttl.total_seconds() / 3600
        }

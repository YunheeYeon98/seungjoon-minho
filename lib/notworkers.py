#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Управление списком нерабочих прокси
"""

from pathlib import Path
from datetime import datetime
from typing import Set, Dict, List, Tuple
from lib.logger import logger
from lib.config import config
from lib.models import  ProxyConfig, ProxyCheckResult


class NotWorkersManager:
    """Менеджер списка нерабочих прокси"""
    
    def __init__(self):
        self.file_path = Path(config.NOTWORKERS_FILE)
        self.enabled = config.NOTWORKERS_UPDATE_ENABLED
    
    def load(self) -> Tuple[Set[str], Dict[str, str]]:
        """
        Загрузка списка нерабочих
        
        Returns:
            (set нормализованных ссылок, dict {норм_ссылка: полная_строка})
        """
        normalized = set()
        full_lines = {}
        
        if not self.file_path.exists():
            return normalized, full_lines
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Извлекаем нормализованную ссылку
                        from lib.parser import ProxyParser
                        norm = ProxyParser.normalize_link(line)
                        if norm:
                            normalized.add(norm)
                            full_lines[norm] = line
                            
            logger.info(f"Loaded {len(normalized)} notworkers from {self.file_path}")
            
        except Exception as e:
            logger.error(f"Failed to load notworkers: {e}")
        
        return normalized, full_lines
    
    def save(self, normalized_to_full: Dict[str, str]) -> None:
        """Сохранение списка нерабочих"""
        try:
            # Сортируем для стабильности
            lines = sorted(normalized_to_full.values())
            
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write("# Not working proxies\n")
                f.write(f"# Updated: {datetime.now().isoformat()}\n")
                f.write("# " + "="*50 + "\n")
                for line in lines:
                    f.write(line + '\n')
                    
            logger.info(f"Saved {len(lines)} notworkers to {self.file_path}")
            
        except Exception as e:
            logger.error(f"Failed to save notworkers: {e}")
    
    def update(self, results: List[ProxyCheckResult]) -> None:
        """
        Обновление списка на основе результатов проверки
        
        Args:
            results: результаты проверки
        """
        if not self.enabled:
            return
        
        # Загружаем текущий список
        existing_norms, existing_map = self.load()
        
        # Определяем рабочие и нерабочие
        working_norms = {r.config.normalized_link for r in results if r.is_working}
        non_working_norms = {r.config.normalized_link for r in results if not r.is_working}
        
        # Формируем новый список
        new_map = {}
        
        # Сохраняем существующие нерабочие, если они не стали рабочими
        for norm, full in existing_map.items():
            if norm not in working_norms:
                new_map[norm] = full
        
        # Добавляем новые нерабочие
        for result in results:
            if not result.is_working:
                norm = result.config.normalized_link
                if norm not in new_map:
                    new_map[norm] = result.config.link
        
        # Сохраняем
        self.save(new_map)
        
        # Статистика
        added = len(set(new_map.keys()) - set(existing_map.keys()))
        removed = len(set(existing_map.keys()) & working_norms)
        
        if added or removed:
            logger.info(f"Notworkers updated: +{added} new, -{removed} revived, total {len(new_map)}")
    
    def filter(self, configs: List[ProxyConfig]) -> List[ProxyConfig]:
        """
        Фильтрация конфигов - исключение нерабочих
        
        Args:
            configs: исходные конфиги
            
        Returns:
            конфиги без нерабочих
        """
        if not self.enabled:
            return configs
        
        notworkers, _ = self.load()
        if not notworkers:
            return configs
        
        filtered = []
        skipped = 0
        
        for cfg in configs:
            if cfg.normalized_link not in notworkers:
                filtered.append(cfg)
            else:
                skipped += 1
        
        if skipped:
            logger.info(f"Skipped {skipped} notworkers")
        
        return filtered

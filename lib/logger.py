#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Настройка логирования
"""

import logging
import sys
from logging.handlers import RotatingFileHandler

from lib.config import config


class ColoredFormatter(logging.Formatter):
    """Форматтер с цветами для консоли"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'
    }
    
    def format(self, record):
        if sys.stderr.isatty():
            levelname = record.levelname
            if levelname in self.COLORS:
                record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        return super().format(record)


def setup_logging():
    """Настройка логирования"""
    
    # Уровень логирования
    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    
    # Корневой логгер
    root = logging.getLogger()
    root.setLevel(level)
    
    # Очищаем существующие обработчики
    root.handlers.clear()
    
    # Форматтер для файла
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Форматтер для консоли
    console_formatter = ColoredFormatter(
        '%(levelname)s - %(message)s'
    )
    
    # Консольный обработчик
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(console_formatter)
    root.addHandler(console)
    
    # Файловый обработчик
    log_file = config.LOGS_DIR / 'xraycheck.log'
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    root.addHandler(file_handler)
    
    # Подавляем лишние логи библиотек
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


# Создаем логгер для текущего модуля
logger = logging.getLogger(__name__)

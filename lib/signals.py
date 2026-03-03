#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обработка системных сигналов (Ctrl+C и т.д.)
"""

import signal
import sys
from typing import Callable, Dict
from lib.logger import logger

class SignalHandler:
    """Обработчик сигналов"""
    
    def __init__(self):
        self.interrupted = False
        self.handlers: Dict[str, Callable] = {}
        
        # Устанавливаем обработчики
        signal.signal(signal.SIGINT, self._handle)
        signal.signal(signal.SIGTERM, self._handle)
        
        if hasattr(signal, 'SIGBREAK'):  # Windows
            signal.signal(signal.SIGBREAK, self._handle)
    
    def _handle(self, signum, frame):
        """Обработка сигнала"""
        self.interrupted = True
        logger.info("\n⚠️ Interrupted, shutting down...")
        
        # Вызываем зарегистрированные обработчики
        for name, handler in self.handlers.items():
            try:
                handler()
            except Exception as e:
                logger.info(f"Error in handler {name}: {e}")
        
        sys.exit(1)
    
    def register(self, name: str, handler: Callable):
        """Регистрация обработчика"""
        self.handlers[name] = handler


signal_handler = SignalHandler()

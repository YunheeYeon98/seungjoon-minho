#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсинг прокси-конфигураций различных протоколов
"""

import base64
import json
import re
import urllib.parse
from typing import Optional, List

from lib.models import ProxyConfig
from lib.logger import logger


class ProxyParser:
    """Парсер прокси-конфигураций"""
    
    # Паттерны протоколов
    PROTOCOLS = {
        'vless': re.compile(r'^vless://', re.I),
        'vmess': re.compile(r'^vmess://', re.I),
        'trojan': re.compile(r'^trojan://', re.I),
        'ss': re.compile(r'^ss://', re.I),
        'hysteria': re.compile(r'^hysteria://', re.I),
        'hysteria2': re.compile(r'^(hysteria2|hy2)://', re.I),
    }
    
    @staticmethod
    def decode_base64(content: str) -> str:
        """Декодирование base64"""
        try:
            content = content.strip()
            # Добавляем паддинг
            missing = len(content) % 4
            if missing:
                content += '=' * (4 - missing)
            return base64.b64decode(content).decode('utf-8')
        except Exception as e:
            logger.debug(f"Base64 decode error: {e}")
            return content
    
    @staticmethod
    def normalize_link(link: str) -> str:
        """Нормализация ссылки для дедупликации"""
        # Удаляем фрагмент и пробелы
        link = link.split('#')[0].strip()
        
        # Для VMess нужна особая нормализация
        if link.startswith('vmess://'):
            try:
                # Декодируем VMess JSON
                b64_part = link[8:].split('#')[0].strip()
                decoded = ProxyParser.decode_base64(b64_part)
                vmess = json.loads(decoded)
                
                # Создаем каноническую форму (без имени)
                canonical = {
                    'v': vmess.get('v', '2'),
                    'add': vmess.get('add', ''),
                    'port': vmess.get('port', ''),
                    'id': vmess.get('id', ''),
                    'aid': vmess.get('aid', '0'),
                    'net': vmess.get('net', 'tcp'),
                    'type': vmess.get('type', 'none'),
                    'host': vmess.get('host', ''),
                    'path': vmess.get('path', ''),
                    'tls': vmess.get('tls', ''),
                    'scy': vmess.get('scy', 'auto'),
                }
                
                # Перекодируем
                canon_json = json.dumps(canonical, sort_keys=True, separators=(',', ':'))
                return f"vmess://{base64.b64encode(canon_json.encode()).decode()}"
            except:
                pass
        
        return link
    
    @classmethod
    def detect_protocol(cls, link: str) -> Optional[str]:
        """Определение протокола"""
        for proto, pattern in cls.PROTOCOLS.items():
            if pattern.match(link):
                return proto
        return None

    def parse_vless(self, link: str) -> Optional[ProxyConfig]:
        """
        Полностью рабочий парсер VLESS
        """
        # Удаляем лишние пробелы
        link = link.strip()

        # Проверяем протокол
        if not link.startswith('vless://'):
            return None

        # Разбиваем на части
        try:
            # Убираем vless://
            rest = link[8:]

            # Разделяем на uuid@host:port и остальное
            if '@' not in rest:
                logger.debug(f"No @ in VLESS link: {link[:50]}")
                return None

            uuid_host, rest2 = rest.split('@', 1)

            # Извлекаем uuid
            uuid = uuid_host

            # Извлекаем host и port
            if ':' not in rest2:
                logger.debug(f"No port in VLESS link: {link[:50]}")
                return None

            # Может быть host:port?params#name
            if '?' in rest2:
                host_port, params_fragment = rest2.split('?', 1)
            else:
                host_port = rest2
                params_fragment = ''

            if ':' not in host_port:
                logger.debug(f"Invalid host:port format: {host_port}")
                return None

            host, port_str = host_port.split(':', 1)

            # Очищаем порт
            port_clean = re.sub(r'[^0-9]', '', port_str.split('?')[0].split('#')[0].strip())
            try:
                port = int(port_clean)
            except ValueError:
                logger.error(f"Invalid port number: {port_str}")
                return None

            # Парсим параметры и имя
            params = {}
            name = ''

            if params_fragment:
                if '#' in params_fragment:
                    params_str, name = params_fragment.split('#', 1)
                else:
                    params_str = params_fragment

                if params_str:
                    for p in params_str.split('&'):
                        if '=' in p:
                            k, v = p.split('=', 1)
                            params[k] = urllib.parse.unquote(v)

            # Обрабатываем имя
            if name:
                name = urllib.parse.unquote(name)
                # Пробуем исправить битую кодировку
                try:
                    name = name.encode('latin-1').decode('utf-8')
                except:
                    pass

            return ProxyConfig(
                protocol='vless',
                link=link,
                normalized_link=self.normalize_link(link),
                host=host,
                port=port,
                name=name,
                uuid=uuid,
                params=params
            )

        except Exception as e:
            logger.error(f"Error parsing VLESS link: {e}")
            logger.debug(f"Link: {link[:200]}")
            return None
    
    def parse_vmess(self, link: str) -> Optional[ProxyConfig]:
        """Парсинг VMess"""
        if not link.startswith('vmess://'):
            return None
        
        try:
            b64_part = link[8:].split('#')[0].strip()
            decoded = self.decode_base64(b64_part)
            vmess = json.loads(decoded)
            
            return ProxyConfig(
                protocol='vmess',
                link=link,
                normalized_link=self.normalize_link(link),
                host=vmess.get('add', ''),
                port=int(vmess.get('port', 0)),
                name=vmess.get('ps', ''),
                uuid=vmess.get('id', ''),
                aid=int(vmess.get('aid', 0)),
                net=vmess.get('net', 'tcp'),
                type=vmess.get('type', 'none'),
                path=vmess.get('path', ''),
                tls=vmess.get('tls', ''),
                scy=vmess.get('scy', 'auto'),
                params={}
            )
        except Exception as e:
            logger.debug(f"VMess parse error: {e}")
            return None
    
    def parse_trojan(self, link: str) -> Optional[ProxyConfig]:
        """Парсинг Trojan"""
        # trojan://password@host:port?params#name
        pattern = re.compile(r'^trojan://([^@]+)@([^:]+):(\d+)(?:\?(.*))?(?:#(.*))?$', re.I)
        match = pattern.match(link)
        if not match:
            return None
        
        password, host, port, params_str, name = match.groups()
        
        params = {}
        if params_str:
            for p in params_str.split('&'):
                if '=' in p:
                    k, v = p.split('=', 1)
                    params[k] = urllib.parse.unquote(v)
        
        return ProxyConfig(
            protocol='trojan',
            link=link,
            normalized_link=self.normalize_link(link),
            host=host,
            port=int(port),
            name=name or '',
            password=password,
            params=params
        )

    def parse_shadowsocks(self, link: str) -> Optional[ProxyConfig]:
        """
        Парсинг Shadowsocks ссылок

        Поддерживаемые форматы:
        1. ss://method:password@host:port#name
        2. ss://base64(method:password)@host:port#name
        3. ss://method:password@host:port?plugin=... # с параметрами
        """
        if not link.startswith('ss://'):
            return None

        # Убираем протокол
        rest = link[5:]

        # Извлекаем имя (после #)
        name = ''
        if '#' in rest:
            rest, name = rest.split('#', 1)

        # Разделяем на auth и host_port
        if '@' not in rest:
            logger.debug(f"Invalid ss:// format (no @): {link[:50]}...")
            return None

        auth_part, host_port_part = rest.split('@', 1)

        # === ОЧИСТКА ПОРТА ОТ ПАРАМЕТРОВ ===
        # host_port_part может быть "example.com:14999?plugin=..."
        if ':' not in host_port_part:
            logger.debug(f"Invalid ss:// format (no port): {link[:50]}...")
            return None

        # Разделяем host и port с параметрами
        host, port_with_params = host_port_part.split(':', 1)

        # Очищаем порт от параметров (всё до '?' или '#')
        port_clean = port_with_params.split('?')[0].split('#')[0].strip()

        try:
            port = int(port_clean)
        except ValueError:
            logger.error(f"Invalid port format in ss://: '{port_with_params}' (cleaned: '{port_clean}')")
            return None

        # Извлекаем параметры если есть
        params = {}
        if '?' in port_with_params:
            params_str = port_with_params.split('?', 1)[1]
            for p in params_str.split('&'):
                if '=' in p:
                    k, v = p.split('=', 1)
                    params[k] = urllib.parse.unquote(v)

        # === ПАРСИНГ AUTH PART ===
        method = None
        password = None

        # Пробуем распарсить как base64
        try:
            # Проверяем, похоже ли на base64
            import base64
            import re

            # Если auth_part содержит только допустимые символы base64
            if re.match(r'^[A-Za-z0-9+/=]+$', auth_part):
                decoded = base64.b64decode(auth_part).decode('utf-8')
                if ':' in decoded:
                    method, password = decoded.split(':', 1)
        except:
            pass

        # Если не получилось с base64, пробуем как plain text
        if not method and ':' in auth_part:
            method, password = auth_part.split(':', 1)

        if not method or not password:
            logger.debug(f"Failed to parse auth part in ss://: {auth_part}")
            return None

        return ProxyConfig(
            protocol='ss',
            link=link,
            normalized_link=self.normalize_link(link),
            host=host,
            port=port,
            name=name or '',
            method=method,
            password=password,
            params=params
        )
    
    def parse_hysteria(self, link: str) -> Optional[ProxyConfig]:
        """Парсинг Hysteria/Hysteria2"""
        pattern = re.compile(r'^(hysteria|hysteria2|hy2)://([^:]+):(\d+)(?:\?(.*))?(?:#(.*))?$', re.I)
        match = pattern.match(link)
        if not match:
            return None
        
        protocol, host, port, params_str, name = match.groups()
        
        params = {}
        if params_str:
            for p in params_str.split('&'):
                if '=' in p:
                    k, v = p.split('=', 1)
                    params[k] = urllib.parse.unquote(v)
        
        return ProxyConfig(
            protocol=protocol.lower(),
            link=link,
            normalized_link=self.normalize_link(link),
            host=host,
            port=int(port),
            name=name or '',
            params=params
        )
    
    def parse(self, link: str) -> Optional[ProxyConfig]:
        """Универсальный парсинг"""
        parsers = [
            self.parse_vless,
            self.parse_vmess,
            self.parse_trojan,
            self.parse_shadowsocks,
            self.parse_hysteria
        ]
        
        for parser in parsers:
            result = parser(link)
            if result:
                return result
        
        logger.debug(f"Failed to parse: {link[:50]}...")
        return None


class SubscriptionParser:
    """Парсер подписок"""
    
    def __init__(self):
        self.proxy_parser = ProxyParser()
    
    def decode_subscription(self, content: str) -> str:
        """Декодирование подписки (base64 или plain text)"""
        # Проверяем, похоже ли на base64
        b64_pattern = re.compile(r'^[A-Za-z0-9+/=]+$')
        lines = content.strip().split('\n')
        
        # Одна строка - возможно вся подписка в base64
        if len(lines) == 1 and b64_pattern.match(lines[0]):
            try:
                return self.proxy_parser.decode_base64(lines[0])
            except:
                pass
        
        # Много строк - возможно каждая в base64
        if all(b64_pattern.match(line) for line in lines if line):
            decoded = []
            for line in lines:
                if line:
                    try:
                        decoded.append(self.proxy_parser.decode_base64(line))
                    except:
                        decoded.append(line)
            return '\n'.join(decoded)
        
        return content
    
    def parse_content(self, content: str) -> List[ProxyConfig]:
        """Парсинг контента в список конфигов"""
        configs = []
        seen = set()
        
        # Декодируем подписку
        content = self.decode_subscription(content)
        c = 0
        for line in content.splitlines():
            if c == 1:
                break
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            config = self.proxy_parser.parse('vless://d65cc14c-f53f-4fe2-b262-97856601319c@87.229.108.135:5443?type=tcp&security=reality&encryption=none&flow=xtls-rprx-vision&fp=chrome&pbk=e2RLf57Li_-MDZGE9ss1BWPgP54mqRb5PfXhW2jcVVg&sid=c39cc7310a&sni=yandex.com#0340 | 🇳🇱 Netherlands | 🏳️ SNI-Yandex | VLESS | 📺 YT | TG: @YoutubeUnBlockRu')
            if config and config.normalized_link not in seen:
                seen.add(config.normalized_link)
                configs.append(config)
                c += 1
        
        return configs
    
    def load_from_url(self, url: str, timeout: int = 15) -> List[ProxyConfig]:
        """Загрузка из URL"""
        import requests
        
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return self.parse_content(response.text)
        except Exception as e:
            logger.error(f"Failed to load {url}: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def load_from_file(self, path: str) -> List[ProxyConfig]:
        """Загрузка из файла"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return self.parse_content(f.read())
        except Exception as e:
            logger.error(f"Failed to read {path}: {e}")
            return []

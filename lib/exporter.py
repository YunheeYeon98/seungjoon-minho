#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Экспорт результатов в различные форматы (txt, json, csv, html)
"""

import csv
import json
from pathlib import Path
from typing import List, Dict
from datetime import datetime

from lib.models import ProxyCheckResult
from lib.logger import logger
from lib.config import config


class BaseExporter:
    """Базовый класс экспортера"""
    
    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)


class TxtExporter(BaseExporter):
    """Экспорт в TXT (оригинальный формат)"""
    
    def export(self, results: List[ProxyCheckResult]) -> Path:
        """Экспорт результатов в TXT"""
        lines = []
        
        # Сортируем: сначала рабочие по скорости
        working = [r for r in results if r.is_working]
        working.sort(key=lambda x: -(x.speed.download_mbps if x.speed else 0))
        
        non_working = [r for r in results if not r.is_working]
        
        # Добавляем комментарий
        lines.append(f"# XRayCheck Results - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"# Total: {len(results)}, Working: {len(working)}, Failed: {len(non_working)}")
        lines.append("# " + "="*50)
        
        # Рабочие
        for r in working:
            comment = []
            if r.response_times_ms:
                comment.append(f"{r.avg_response_time_ms:.0f}ms")
            if r.speed:
                comment.append(f"{r.speed.download_mbps:.1f}Mbps")
            if r.geo and r.geo.country:
                comment.append(r.geo.country)
            
            comment_str = f" # {' '.join(comment)}" if comment else ""
            lines.append(f"{r.config.link}{comment_str}")
        
        # Разделитель
        if non_working:
            lines.append("# " + "="*50)
            lines.append("# Failed proxies:")
            for r in non_working:
                error = f" # {r.error}" if r.error else ""
                lines.append(f"{r.config.link}{error}")
        
        with open(self.output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        logger.info(f"Exported {len(results)} results to {self.output_path}")
        return self.output_path


class CSVExporter(BaseExporter):
    """Экспорт в CSV"""
    
    def export(self, results: List[ProxyCheckResult]) -> Path:
        """Экспорт результатов в CSV"""
        if not results:
            return self.output_path
        
        rows = [r.to_dict() for r in results]
        fieldnames = sorted(set().union(*(r.keys() for r in rows)))
        
        with open(self.output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            writer.writerows(rows)
        
        logger.info(f"Exported {len(results)} results to {self.output_path}")
        return self.output_path


class JSONExporter(BaseExporter):
    """Экспорт в JSON"""
    
    def export(self, results: List[ProxyCheckResult]) -> Path:
        """Экспорт результатов в JSON"""
        data = {
            'exported_at': datetime.now().isoformat(),
            'config': {
                'mode': config.MODE,
                'max_workers': config.MAX_WORKERS,
                'strict_mode': config.STRICT_MODE,
            },
            'total': len(results),
            'working': sum(1 for r in results if r.is_working),
            'results': [r.to_dict() for r in results]
        }
        
        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported {len(results)} results to {self.output_path}")
        return self.output_path


class HTMLExporter(BaseExporter):
    """Экспорт в HTML с красивым отображением"""
    
    TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>XRayCheck Results</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        .header {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #2196F3;
        }}
        .stat-label {{
            color: #666;
            font-size: 14px;
        }}
        table {{
            width: 100%;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-collapse: collapse;
        }}
        th {{
            background: #2196F3;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 500;
        }}
        td {{
            padding: 12px;
            border-bottom: 1px solid #eee;
        }}
        tr:hover {{
            background: #f5f5f5;
        }}
        .working {{ color: #4CAF50; font-weight: bold; }}
        .not-working {{ color: #f44336; }}
        .speed-good {{ color: #4CAF50; }}
        .speed-medium {{ color: #FF9800; }}
        .speed-bad {{ color: #f44336; }}
        .link-cell {{
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>XRayCheck Results</h1>
            <p>Exported: {export_time}</p>
            <p>Mode: {mode} | Workers: {workers} | Strict: {strict}</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{total}</div>
                <div class="stat-label">Total</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{working}</div>
                <div class="stat-label">Working</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{success_rate:.1f}%</div>
                <div class="stat-label">Success Rate</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{avg_speed:.1f}</div>
                <div class="stat-label">Avg Speed (Mbps)</div>
            </div>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>Status</th>
                    <th>Protocol</th>
                    <th>Host</th>
                    <th>Port</th>
                    <th>Ping (ms)</th>
                    <th>Speed (Mbps)</th>
                    <th>Country</th>
                    <th>Link</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
    </div>
</body>
</html>
"""
    
    def _get_speed_class(self, speed: float) -> str:
        if speed >= 50:
            return 'speed-good'
        elif speed >= 10:
            return 'speed-medium'
        else:
            return 'speed-bad'
    
    def export(self, results: List[ProxyCheckResult]) -> Path:
        """Экспорт результатов в HTML"""
        
        total = len(results)
        working = sum(1 for r in results if r.is_working)
        success_rate = (working / total * 100) if total > 0 else 0
        
        speeds = [r.speed.download_mbps for r in results if r.speed and r.speed.download_mbps > 0]
        avg_speed = sum(speeds) / len(speeds) if speeds else 0
        
        rows = []
        for r in sorted(results, key=lambda x: (not x.is_working, -(x.speed.download_mbps if x.speed else 0))):
            status_class = 'working' if r.is_working else 'not-working'
            status_text = '✓' if r.is_working else '✗'
            
            speed = r.speed.download_mbps if r.speed else 0
            speed_class = self._get_speed_class(speed) if speed > 0 else ''
            speed_display = f"{speed:.1f}" if speed > 0 else '-'
            
            ping = r.avg_response_time_ms if r.response_times_ms else 0
            ping_display = f"{ping:.0f}" if ping > 0 else '-'
            
            country = r.geo.country if r.geo and r.geo.country else '-'
            
            rows.append(f"""<tr>
                <td class="{status_class}">{status_text}</td>
                <td>{r.config.protocol}</td>
                <td>{r.config.host}</td>
                <td>{r.config.port}</td>
                <td>{ping_display}</td>
                <td class="{speed_class}">{speed_display}</td>
                <td>{country}</td>
                <td class="link-cell" title="{r.config.link}">{r.config.link[:50]}...</td>
            </tr>""")
        
        html = self.TEMPLATE.format(
            export_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            mode=config.MODE,
            workers=config.MAX_WORKERS,
            strict='yes' if config.STRICT_MODE else 'no',
            total=total,
            working=working,
            success_rate=success_rate,
            avg_speed=round(avg_speed, 1),
            rows='\n'.join(rows)
        )
        
        with open(self.output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        logger.info(f"Exported {len(results)} results to {self.output_path}")
        return self.output_path


class ExportManager:
    """Менеджер экспорта"""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
    
    def export(self, results: List[ProxyCheckResult]) -> Dict[str, Path]:
        """
        Экспорт в форматы согласно конфигурации
        """
        exported = {}
        formats = config.EXPORT_FORMAT.split(',')
        
        for fmt in formats:
            fmt = fmt.strip()
            if fmt == 'txt':
                path = self.base_path.with_suffix('.txt')
                exporter = TxtExporter(path)
                exported['txt'] = exporter.export(results)
                
            elif fmt == 'json':
                path = self.base_path.with_suffix('.json')
                exporter = JSONExporter(path)
                exported['json'] = exporter.export(results)
                
            elif fmt == 'all':
                # Экспорт во все форматы
                for f in ['txt', 'json']:
                    path = self.base_path.with_suffix(f'.{f}')
                    exporter_class = {
                        'txt': TxtExporter,
                        'json': JSONExporter,
                    }[f]
                    exporter = exporter_class(path)
                    exported[f] = exporter.export(results)

        if 'txt' in formats or 'all' in formats:
            working = [r for r in results if r.is_working]
            if len(working) >= 10:
                working.sort(key=lambda x: -(x.speed.download_mbps if x.speed else 0))
                
                top_path = self.base_path.parent / f"{self.base_path.stem}_top_100_available.txt"
                exporter = TxtExporter(top_path)
                exporter.export(working)
                exported['working'] = top_path
        
        return exported
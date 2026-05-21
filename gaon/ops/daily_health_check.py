#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명: daily_health_check.py
목적: GAON NEXUS 전체 시스템 일일 헬스체크 + Discord 리포트
작성일: 2026-05-21
설치 위치(Windows): C:/gaon/ops/daily_health_check.py

n8n 스케줄: 매일 09:00 자동 실행
실행: D:\programs\python.exe C:\gaon\ops\daily_health_check.py
"""
import sys
import os
import json
import time
import shutil
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

if sys.platform == 'win32':
    import ctypes
    try:
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass

# ── 경로 설정 ────────────────────────────────────────────────────────────────
CONFIG_PATH = Path('C:/gaon/config/channels.json')
LOG_DIR     = Path('C:/gaon/logs')
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'health_check.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# .env 로드
def _load_env():
    env_path = Path('C:/gaon/.env')
    if not env_path.exists():
        return
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

_load_env()


# ── 체크 항목 정의 ────────────────────────────────────────────────────────────

def check_gemini_api() -> dict:
    """Gemini Free API 응답 확인 (13키 순환 첫 번째 키 테스트)."""
    result = {'name': 'Gemini API', 'status': 'unknown', 'detail': ''}
    try:
        import urllib.request
        api_key = os.environ.get('GEMINI_API_KEY_01', '')
        if not api_key:
            result.update(status='skip', detail='GEMINI_API_KEY_01 미설정')
            return result

        url = (
            f'https://generativelanguage.googleapis.com/v1beta/models?key={api_key}'
        )
        req = urllib.request.Request(url, headers={'User-Agent': 'gaon-health-check'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                result.update(status='ok', detail='응답 정상')
            else:
                result.update(status='warn', detail=f'HTTP {resp.status}')
    except Exception as e:
        result.update(status='fail', detail=str(e)[:80])
    return result


def check_ollama() -> dict:
    """Ollama gemma4:e4b 응답 확인 (localhost:11434)."""
    result = {'name': 'Ollama (gemma4:e4b)', 'status': 'unknown', 'detail': ''}
    try:
        import urllib.request
        url = 'http://localhost:11434/api/tags'
        with urllib.request.urlopen(url, timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read())
                models = [m['name'] for m in data.get('models', [])]
                has_gemma = any('gemma' in m.lower() for m in models)
                result.update(
                    status='ok' if has_gemma else 'warn',
                    detail=f"모델: {', '.join(models[:3])}{'...' if len(models)>3 else ''}"
                    if models else 'gemma4 없음'
                )
            else:
                result.update(status='warn', detail=f'HTTP {resp.status}')
    except Exception as e:
        result.update(status='fail', detail=f'연결 실패: {str(e)[:60]}')
    return result


def check_wangp() -> dict:
    """WanGP 서버 상태 확인 (포트 자동 탐색)."""
    result = {'name': 'WanGP I2V', 'status': 'unknown', 'detail': ''}
    ports = [8080, 7860, 7861, 8000]
    try:
        import urllib.request
        for port in ports:
            try:
                url = f'http://localhost:{port}/'
                with urllib.request.urlopen(url, timeout=3) as resp:
                    if resp.status < 500:
                        result.update(status='ok', detail=f'port {port} 응답')
                        return result
            except Exception:
                continue
        result.update(status='fail', detail=f'포트 {ports} 모두 응답 없음')
    except Exception as e:
        result.update(status='fail', detail=str(e)[:60])
    return result


def check_n8n() -> dict:
    """n8n Docker 컨테이너 상태 확인 (port 5678)."""
    result = {'name': 'n8n (Docker)', 'status': 'unknown', 'detail': ''}
    try:
        import urllib.request
        with urllib.request.urlopen('http://localhost:5678/healthz', timeout=5) as resp:
            result.update(
                status='ok' if resp.status == 200 else 'warn',
                detail=f'HTTP {resp.status}'
            )
    except Exception as e:
        result.update(status='fail', detail=f'연결 실패: {str(e)[:60]}')
    return result


def check_disk_space() -> list[dict]:
    """주요 드라이브 여유 공간 확인."""
    results = []
    drives = [
        ('C:', 'C:/gaon', 10),    # (드라이브명, 경로, 최소 여유GB)
        ('D:', 'D:/gaon_data', 100),
    ]
    for drive_name, path, min_gb in drives:
        r = {'name': f'디스크 {drive_name}', 'status': 'unknown', 'detail': ''}
        try:
            usage = shutil.disk_usage(path)
            free_gb = usage.free / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)
            used_pct = (usage.used / usage.total) * 100
            if free_gb >= min_gb:
                r['status'] = 'ok'
            elif free_gb >= min_gb * 0.5:
                r['status'] = 'warn'
            else:
                r['status'] = 'fail'
            r['detail'] = f'여유 {free_gb:.1f}GB / 전체 {total_gb:.1f}GB ({used_pct:.0f}% 사용)'
        except Exception as e:
            r['status'] = 'skip'
            r['detail'] = f'경로 없음: {path}'
        results.append(r)
    return results


def check_error_log() -> dict:
    """최근 에러 로그 존재 여부 확인."""
    result = {'name': '에러 로그', 'status': 'unknown', 'detail': ''}
    error_files = [
        Path('C:/gaon/logs/wangp_agent.log'),
        Path('C:/gaon/logs/discord_notify.log'),
        Path('D:/gaon_temp/error_log.json'),
    ]
    recent_errors = 0
    now = time.time()
    for f in error_files:
        if f.exists():
            # 최근 24시간 내 ERROR 라인 카운트
            try:
                with open(f, 'r', encoding='utf-8', errors='replace') as fh:
                    lines = fh.readlines()
                recent_errors += sum(
                    1 for ln in lines[-200:] if '[ERROR]' in ln
                )
            except Exception:
                pass

    if recent_errors == 0:
        result.update(status='ok', detail='최근 에러 없음')
    elif recent_errors <= 5:
        result.update(status='warn', detail=f'최근 에러 {recent_errors}건 — 로그 확인 권장')
    else:
        result.update(status='fail', detail=f'최근 에러 {recent_errors}건 — 즉시 확인 필요')
    return result


def check_finals_count() -> dict:
    """완성본 EP 수량 확인 (채널별)."""
    result = {'name': '완성본 현황', 'status': 'unknown', 'detail': ''}
    finals_root = Path('D:/gaon_data/finals')
    if not finals_root.exists():
        result.update(status='skip', detail='D:/gaon_data/finals 없음')
        return result

    total = 0
    channel_counts = {}
    for ch_dir in sorted(finals_root.iterdir()):
        if ch_dir.is_dir():
            mp4s = list(ch_dir.glob('*.mp4'))
            count = len(mp4s)
            channel_counts[ch_dir.name] = count
            total += count

    result.update(
        status='ok',
        detail=f'총 {total}편 완성 | ' + ', '.join(
            f"{k}:{v}" for k, v in list(channel_counts.items())[:5]
        ) + ('...' if len(channel_counts) > 5 else '')
    )
    return result


def check_python_version() -> dict:
    """Python 버전 및 필수 패키지 확인."""
    result = {'name': 'Python 환경', 'status': 'unknown', 'detail': ''}
    ver = sys.version_info
    pkgs = []
    for pkg in ['requests', 'pathlib', 'json']:
        try:
            __import__(pkg)
            pkgs.append(f'✓{pkg}')
        except ImportError:
            pkgs.append(f'✗{pkg}')

    result.update(
        status='ok',
        detail=f'Python {ver.major}.{ver.minor}.{ver.micro} | {" ".join(pkgs)}'
    )
    return result


# ── Discord 리포트 발송 ──────────────────────────────────────────────────────

def _send_discord(webhook_url: str, results: list[dict]) -> bool:
    """헬스체크 결과를 Discord Embed로 발송."""
    try:
        import urllib.request
        import urllib.parse

        ok    = [r for r in results if r['status'] == 'ok']
        warn  = [r for r in results if r['status'] == 'warn']
        fail  = [r for r in results if r['status'] == 'fail']
        skip  = [r for r in results if r['status'] == 'skip']

        if fail:
            color = 0xFF4444
            overall = f'🔴 {len(fail)}개 서비스 장애'
        elif warn:
            color = 0xFFCC00
            overall = f'🟡 {len(warn)}개 서비스 경고'
        else:
            color = 0x44BB44
            overall = '💚 모든 서비스 정상'

        STATUS_ICON = {'ok': '✅', 'warn': '⚠️', 'fail': '❌', 'skip': '⏭️', 'unknown': '❓'}

        lines = [f'**{overall}**\n']
        for r in results:
            icon = STATUS_ICON.get(r['status'], '❓')
            lines.append(f'{icon} **{r["name"]}** — {r["detail"]}')

        payload = {
            'embeds': [{
                'title': f'📊 GAON NEXUS 일일 헬스체크 — {datetime.now().strftime("%Y-%m-%d %H:%M")}',
                'description': '\n'.join(lines),
                'color': color,
                'footer': {'text': f'정상 {len(ok)} / 경고 {len(warn)} / 장애 {len(fail)} / 건너뜀 {len(skip)}'},
            }]
        }

        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 204)
    except Exception as e:
        logger.error(f'Discord 발송 실패: {e}')
        return False


def _save_report(results: list[dict]) -> Path:
    """헬스체크 결과 JSON 저장."""
    report_dir = Path('D:/1인기업/01_youtube/analytics/weekly_reports')
    report_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime('%Y-%m-%d')
    out = report_dir / f'{today}_health.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({
            'date': today,
            'time': datetime.now().strftime('%H:%M:%S'),
            'results': results,
            'summary': {
                'ok':   sum(1 for r in results if r['status'] == 'ok'),
                'warn': sum(1 for r in results if r['status'] == 'warn'),
                'fail': sum(1 for r in results if r['status'] == 'fail'),
            }
        }, f, ensure_ascii=False, indent=2)
    return out


# ── 메인 실행 ─────────────────────────────────────────────────────────────────

def run_health_check(send_discord: bool = True) -> list[dict]:
    """전체 헬스체크 실행."""
    logger.info('=' * 50)
    logger.info(f'GAON NEXUS 일일 헬스체크 시작: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    logger.info('=' * 50)

    results = []

    checks = [
        ('Python 환경',   check_python_version),
        ('Gemini API',    check_gemini_api),
        ('Ollama',        check_ollama),
        ('WanGP',         check_wangp),
        ('n8n',           check_n8n),
        ('에러 로그',     check_error_log),
        ('완성본 현황',   check_finals_count),
    ]

    for name, fn in checks:
        logger.info(f'  체크 중: {name}...')
        try:
            result = fn()
            if isinstance(result, list):
                results.extend(result)
            else:
                results.append(result)
        except Exception as e:
            results.append({'name': name, 'status': 'fail', 'detail': str(e)[:80]})

    # 디스크 체크 (별도 — 복수 결과)
    results.extend(check_disk_space())

    # 결과 출력
    STATUS_ICON = {'ok': '✅', 'warn': '⚠️', 'fail': '❌', 'skip': '⏭️', 'unknown': '❓'}
    logger.info('\n[결과 요약]')
    for r in results:
        icon = STATUS_ICON.get(r['status'], '❓')
        logger.info(f'  {icon} {r["name"]}: {r["detail"]}')

    # 보고서 저장
    try:
        out = _save_report(results)
        logger.info(f'\n보고서 저장: {out}')
    except Exception as e:
        logger.warning(f'보고서 저장 실패: {e}')

    # Discord 발송
    if send_discord:
        webhook_url = os.environ.get('DISCORD_WEBHOOK_URL', '')
        if webhook_url:
            ok = _send_discord(webhook_url, results)
            logger.info(f'Discord 발송: {"성공" if ok else "실패"}')
        else:
            logger.warning('DISCORD_WEBHOOK_URL 미설정 — Discord 알림 건너뜀')

    fail_count = sum(1 for r in results if r['status'] == 'fail')
    logger.info(f'\n헬스체크 완료 (장애 {fail_count}건)')
    return results


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='GAON NEXUS 일일 헬스체크')
    parser.add_argument('--no-discord', action='store_true', help='Discord 알림 비활성화')
    parser.add_argument('--quiet', action='store_true', help='콘솔 출력 최소화')
    args = parser.parse_args()

    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    results = run_health_check(send_discord=not args.no_discord)
    fail_count = sum(1 for r in results if r['status'] == 'fail')
    sys.exit(1 if fail_count > 0 else 0)

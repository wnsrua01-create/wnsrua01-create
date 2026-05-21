#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명: discord_notify.py
목적: GAON NEXUS 파이프라인 상태 Discord Webhook 자동 알림
작성일: 2026-05-21
설치 위치(Windows): C:/gaon/utils/discord_notify.py

설정: C:/gaon/.env 파일에 DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/... 추가
"""
import sys
import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

os.environ.setdefault('PYTHONUTF8', '1')

if sys.platform == 'win32':
    import ctypes
    try:
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass

try:
    import requests
except ImportError:
    print("requests 미설치. pip install requests 실행 후 재시도.")
    sys.exit(1)

# ── 환경변수 로드 ────────────────────────────────────────────────────────────
def _load_env(env_path: Path = Path('C:/gaon/.env')) -> None:
    """간단한 .env 파서 (python-dotenv 없이)."""
    if not env_path.exists():
        return
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

_load_env()

# ── 로깅 ─────────────────────────────────────────────────────────────────────
LOG_DIR = Path('C:/gaon/logs')
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'discord_notify.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ── 알림 이벤트 템플릿 ────────────────────────────────────────────────────────
NOTIFY_EVENTS = {
    "scene_error":   "🔴 씬 에러: **{ch}** EP{ep} 씬{scene:03d} — `{error}`",
    "ep_complete":   "✅ EP 완성: **{ch}** EP{ep:02d} — {duration:.1f}분 소요",
    "daily_summary": "📊 일일 요약 [{date}]\n완성: **{done}**편 / 에러: **{errors}**건 / 처리중: {pending}건",
    "grok_limit":    "⚠️ Grok 한도 도달 — WanGP 로컬로 전환. 24시간 후 복구.",
    "wangp_queue":   "🎬 WanGP 처리 중: **{queue}**씬 대기 / 완료: {done}씬",
    "disk_warning":  "💾 디스크 경고: **{drive}** {usage}% 사용 (여유: {free_gb:.1f}GB)",
    "ep_upload_ok":  "📤 업로드 완료: **{ch}** EP{ep:02d} — {url}",
    "pipeline_start":"🚀 파이프라인 시작: **{ch}** EP{ep:02d} ({stage})",
    "health_ok":     "💚 헬스체크 OK [{time}] — 모든 서비스 정상",
    "health_warn":   "🟡 헬스체크 경고 [{time}]\n{issues}",
    "batch_complete":"🏁 배치 완료: {ch} EP{ep_start:02d}~EP{ep_end:02d} — 성공 {done}편",
}

# ── 임베드 컬러 ────────────────────────────────────────────────────────────
COLORS = {
    'red':    0xFF4444,
    'green':  0x44BB44,
    'yellow': 0xFFCC00,
    'blue':   0x4488FF,
    'gray':   0x888888,
}

EVENT_COLORS = {
    "scene_error":   'red',
    "ep_complete":   'green',
    "daily_summary": 'blue',
    "grok_limit":    'yellow',
    "wangp_queue":   'blue',
    "disk_warning":  'yellow',
    "ep_upload_ok":  'green',
    "pipeline_start":'gray',
    "health_ok":     'green',
    "health_warn":   'yellow',
    "batch_complete":'green',
}


class DiscordNotifier:
    """Discord Webhook 알림 클라이언트."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.environ.get('DISCORD_WEBHOOK_URL', '')
        if not self.webhook_url:
            logger.warning("DISCORD_WEBHOOK_URL 미설정 — C:\\gaon\\.env 확인")

    def send(self, event: str, embed: bool = True, **kwargs) -> bool:
        """
        알림 발송.

        Args:
            event: NOTIFY_EVENTS 키 (예: 'ep_complete')
            embed: True면 Discord Embed 형식, False면 일반 텍스트
            **kwargs: 템플릿 변수

        Returns:
            True = 성공
        """
        if not self.webhook_url:
            logger.warning(f"Webhook URL 없음 — 알림 건너뜀: {event}")
            return False

        template = NOTIFY_EVENTS.get(event, str(kwargs))
        try:
            message = template.format(**kwargs)
        except KeyError as e:
            logger.error(f"템플릿 변수 누락: {e} (event={event})")
            message = f"[{event}] {kwargs}"

        if embed:
            color_key = EVENT_COLORS.get(event, 'gray')
            color = COLORS[color_key]
            payload = {
                "embeds": [{
                    "description": message,
                    "color": color,
                    "footer": {"text": f"GAON NEXUS • {datetime.now().strftime('%Y-%m-%d %H:%M')}"},
                }]
            }
        else:
            payload = {"content": message}

        return self._post(payload)

    def send_raw(self, content: str) -> bool:
        """자유 형식 텍스트 발송."""
        return self._post({"content": content})

    def send_embed(self, title: str, description: str, color: str = 'blue',
                   fields: Optional[list] = None) -> bool:
        """커스텀 Embed 발송."""
        embed = {
            "title": title,
            "description": description,
            "color": COLORS.get(color, COLORS['blue']),
            "footer": {"text": f"GAON NEXUS • {datetime.now().strftime('%Y-%m-%d %H:%M')}"},
        }
        if fields:
            embed["fields"] = fields
        return self._post({"embeds": [embed]})

    def _post(self, payload: dict, retries: int = 3) -> bool:
        for attempt in range(1, retries + 1):
            try:
                r = requests.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10,
                    headers={'Content-Type': 'application/json'},
                )
                if r.status_code in (200, 204):
                    logger.debug("Discord 알림 발송 성공")
                    return True
                # Rate limit
                if r.status_code == 429:
                    retry_after = r.json().get('retry_after', 1.0)
                    logger.warning(f"Discord Rate Limit — {retry_after}초 대기")
                    time.sleep(retry_after)
                    continue
                logger.warning(f"Discord 응답 오류: {r.status_code} {r.text[:200]}")
            except requests.exceptions.Timeout:
                logger.warning(f"Discord 타임아웃 (시도 {attempt})")
            except Exception as e:
                logger.error(f"Discord 전송 오류: {e}")

            if attempt < retries:
                time.sleep(2 ** attempt)

        return False


# ── 전역 인스턴스 (간편 사용) ────────────────────────────────────────────────
_notifier: Optional[DiscordNotifier] = None


def get_notifier() -> DiscordNotifier:
    global _notifier
    if _notifier is None:
        _notifier = DiscordNotifier()
    return _notifier


def notify(event: str, **kwargs) -> bool:
    """간편 알림 함수. 전역 인스턴스 사용."""
    return get_notifier().send(event, **kwargs)


# ── CLI / 테스트 ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Discord 알림 테스트')
    parser.add_argument('--test', action='store_true', help='테스트 알림 발송')
    parser.add_argument('--event', default='ep_complete', help='이벤트 이름')
    args = parser.parse_args()

    n = DiscordNotifier()

    if args.test:
        print("[테스트 알림 발송]")

        # 각 이벤트 타입 테스트
        tests = [
            ('ep_complete',   dict(ch='시니어보물창고', ep=1, duration=8.5)),
            ('scene_error',   dict(ch='senior', ep=1, scene=42, error='이미지 없음')),
            ('daily_summary', dict(date='2026-05-21', done=3, errors=1, pending=14)),
            ('disk_warning',  dict(drive='D:', usage=87, free_gb=13.2)),
            ('health_ok',     dict(time='09:00')),
        ]

        for event, kwargs in tests:
            ok = n.send(event, **kwargs)
            status = '✅' if ok else '⚠️ (Webhook URL 확인 필요)'
            print(f"  {status} {event}")
            time.sleep(0.5)

        print("\n테스트 완료.")
        print("알림이 안 오면 C:\\gaon\\.env 에 DISCORD_WEBHOOK_URL 설정 확인.")
    else:
        # 단일 이벤트
        ok = n.send(args.event, ch='테스트채널', ep=1, duration=5.0,
                    scene=1, error='test', done=0, errors=0, pending=0,
                    date='2026-05-21', queue=0, drive='D:', usage=50,
                    free_gb=100.0, url='https://youtube.com', stage='script',
                    ep_start=1, ep_end=10, time='09:00', issues='없음')
        print(f"발송 결과: {'성공' if ok else '실패'}")

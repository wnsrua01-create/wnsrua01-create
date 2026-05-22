#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명: performance_loop.py
목적: YouTube Analytics API → 자동 개선 루프 (CTR/Retention 기반)
작성일: 2026-05-21
설치 위치(Windows): C:/gaon/analytics/performance_loop.py

n8n 스케줄: 매일 06:00 실행
의존성: pip install google-api-python-client google-auth
"""
import sys
import os
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional

os.environ.setdefault('PYTHONUTF8', '1')

if sys.platform == 'win32':
    import ctypes
    try:
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass

# ── 경로 상수 ────────────────────────────────────────────────────────────────
ROOT_ANALYTICS = Path('D:/1인기업/01_youtube/analytics')
ROOT_QUEUE     = Path('D:/gaon_temp/script_queue')
LOG_DIR        = Path('C:/gaon/logs')

LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'performance_loop.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ── 자동화 규칙 임계값 ────────────────────────────────────────────────────────
RULE_CTR_MIN          = 4.0     # % — 이하면 썸네일 교체 플래그
RULE_RETENTION_MIN    = 390     # 초 (6.5분, 50%) — 이하면 body1 재설계 플래그
RULE_VIEW_SURGE_RATIO = 3.0     # 배 — 이상이면 유사 주제 확장
RULE_SHORTS_BONUS_MIN = 10_000  # Shorts 조회수 기준

CHANNEL_SLUGS = {
    'ch01': 'senior',  'ch02': 'finance', 'ch03': 'health',
    'ch04': 'pension', 'ch05': 'psych',   'ch06': 'realty',
    'ch07': 'parent',  'ch08': 'cooking', 'ch09': 'aitech',
    'ch10': 'travel',  'ch11': 'beauty',  'ch12': 'growth',
    'ch13': 'history', 'ch14': 'pets',    'ch15': 'home',
    'ch16': 'midlife', 'ch17': 'money',
}


class YouTubeAnalyticsClient:
    """YouTube Analytics API v2 클라이언트."""

    def __init__(self, credentials_path: str = 'C:/gaon/config/yt_credentials.json'):
        self.credentials_path = Path(credentials_path)
        self._service = None
        self._data_service = None

    def _build_service(self) -> bool:
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            if not self.credentials_path.exists():
                logger.error(f"인증 파일 없음: {self.credentials_path}")
                return False

            with open(self.credentials_path, 'r', encoding='utf-8') as f:
                creds_data = json.load(f)

            creds = Credentials.from_authorized_user_info(creds_data)
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # 갱신된 토큰 저장
                with open(self.credentials_path, 'w', encoding='utf-8') as f:
                    json.dump(json.loads(creds.to_json()), f, ensure_ascii=False, indent=2)

            self._service = build('youtube', 'v3', credentials=creds)
            self._data_service = build('youtubeAnalytics', 'v2', credentials=creds)
            return True

        except ImportError:
            logger.error("google-api-python-client 미설치. pip install google-api-python-client google-auth")
            return False
        except Exception as e:
            logger.error(f"YouTube API 초기화 실패: {e}")
            return False

    def get_channel_stats(self, channel_id: str,
                          days: int = 28) -> Optional[dict]:
        """채널의 최근 N일 통계 조회."""
        if not self._service and not self._build_service():
            return None

        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days)

        try:
            response = self._data_service.reports().query(
                ids=f'channel=={channel_id}',
                startDate=str(start_date),
                endDate=str(end_date),
                metrics='views,estimatedMinutesWatched,averageViewDuration,clickThroughRate,subscribersGained',
                dimensions='video',
                sort='-views',
                maxResults=50,
            ).execute()
            return response
        except Exception as e:
            logger.error(f"Analytics API 오류 ({channel_id}): {e}")
            return None

    def get_video_retention(self, video_id: str) -> Optional[float]:
        """영상별 평균 시청 지속 시간(초) 조회."""
        if not self._service and not self._build_service():
            return None
        try:
            response = self._data_service.reports().query(
                ids=f'video=={video_id}',
                startDate='2020-01-01',
                endDate=str(datetime.now(timezone.utc).date()),
                metrics='averageViewDuration',
            ).execute()
            rows = response.get('rows', [])
            return float(rows[0][0]) if rows else None
        except Exception as e:
            logger.error(f"Retention 조회 실패 ({video_id}): {e}")
            return None


class PerformanceRuleEngine:
    """Analytics 데이터 → 자동 개선 액션 생성."""

    def __init__(self):
        ROOT_ANALYTICS.mkdir(parents=True, exist_ok=True)
        ROOT_QUEUE.mkdir(parents=True, exist_ok=True)

    def evaluate(self, video_id: str, title: str, ch_slug: str,
                 ctr: float, avg_view_sec: float, views: int,
                 prev_avg_views: float) -> list[dict]:
        """
        단일 영상에 대한 규칙 평가.

        Returns:
            list of action dicts: {'action': str, 'video_id': str, ...}
        """
        actions = []

        # 규칙 1: CTR < 4% → 썸네일 교체 플래그
        if ctr < RULE_CTR_MIN:
            actions.append({
                'action':    'thumbnail_update',
                'video_id':  video_id,
                'title':     title,
                'ch_slug':   ch_slug,
                'ctr':       ctr,
                'reason':    f'CTR {ctr:.1f}% < {RULE_CTR_MIN}% 기준',
            })
            logger.info(f"[{ch_slug}] {title} — CTR {ctr:.1f}% 낮음 → 썸네일 교체 플래그")

        # 규칙 2: 평균 시청 시간 < 390초 → body1 재설계 플래그
        if avg_view_sec < RULE_RETENTION_MIN:
            actions.append({
                'action':    'body1_redesign',
                'video_id':  video_id,
                'title':     title,
                'ch_slug':   ch_slug,
                'avg_sec':   avg_view_sec,
                'reason':    f'평균 시청 {avg_view_sec:.0f}초 < {RULE_RETENTION_MIN}초 기준',
            })
            logger.info(f"[{ch_slug}] {title} — Retention {avg_view_sec:.0f}초 낮음 → body1 재설계 플래그")

        # 규칙 3: 조회수 급등 (3배+) → 유사 주제 자동 확장
        if prev_avg_views > 0 and views >= prev_avg_views * RULE_VIEW_SURGE_RATIO:
            actions.append({
                'action':      'topic_expansion',
                'video_id':    video_id,
                'title':       title,
                'ch_slug':     ch_slug,
                'views':       views,
                'prev_avg':    prev_avg_views,
                'ratio':       views / prev_avg_views,
                'reason':      f'조회수 {views:,} = 평균 {prev_avg_views:,.0f}의 {views/prev_avg_views:.1f}배',
            })
            logger.info(f"[{ch_slug}] {title} — 조회수 급등 {views/prev_avg_views:.1f}x → 주제 확장 플래그")

        return actions

    def save_actions(self, actions: list[dict], date_str: str) -> Path:
        """액션 목록을 JSON 파일로 저장."""
        out = ROOT_ANALYTICS / 'weekly_reports' / f'{date_str}_actions.json'
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, 'w', encoding='utf-8') as f:
            json.dump({'date': date_str, 'actions': actions}, f,
                      ensure_ascii=False, indent=2)
        logger.info(f"액션 저장: {out} ({len(actions)}건)")
        return out

    def save_report(self, report: dict, date_str: str) -> Path:
        """일일 리포트 저장."""
        out = ROOT_ANALYTICS / 'weekly_reports' / f'{date_str}_report.json'
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"리포트 저장: {out}")
        return out

    def queue_topic_expansion(self, ch_slug: str, base_title: str,
                               count: int = 10) -> None:
        """급등 영상 주제 기반 유사 주제 생성 큐에 추가."""
        queue_file = ROOT_QUEUE / f'{ch_slug}_topic_expand.json'
        existing = []
        if queue_file.exists():
            with open(queue_file, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        existing.append({
            'base_title': base_title,
            'count':      count,
            'queued_at':  datetime.now().isoformat(),
            'status':     'pending',
        })
        with open(queue_file, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        logger.info(f"주제 확장 큐 추가: {ch_slug} / '{base_title}' × {count}편")


def run_performance_loop(channel_configs: Optional[list[dict]] = None) -> dict:
    """
    전체 채널 성과 분석 및 액션 생성.

    Args:
        channel_configs: [{'ch_slug': ..., 'channel_id': ...}, ...]
                         None이면 C:/gaon/config/channels.json에서 로드

    Returns:
        summary dict
    """
    today = datetime.now().strftime('%Y-%m-%d')
    logger.info(f"=== 성과 피드백 루프 시작: {today} ===")

    if channel_configs is None:
        config_path = Path('C:/gaon/config/channels.json')
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                channel_configs = json.load(f)
        else:
            logger.warning("channels.json 없음 — 더미 데이터로 실행")
            channel_configs = [
                {'ch_slug': slug, 'channel_id': f'UC_PLACEHOLDER_{chid}'}
                for chid, slug in CHANNEL_SLUGS.items()
            ]

    client = YouTubeAnalyticsClient()
    engine = PerformanceRuleEngine()

    all_actions = []
    summary = {
        'date':            today,
        'channels_checked': 0,
        'total_actions':   0,
        'thumbnail_flags': 0,
        'retention_flags': 0,
        'topic_expansions': 0,
    }

    for cfg in channel_configs:
        ch_slug    = cfg.get('ch_slug', 'unknown')
        channel_id = cfg.get('channel_id', '')

        logger.info(f"[{ch_slug}] 분석 시작")
        stats = client.get_channel_stats(channel_id)

        if stats is None:
            logger.warning(f"[{ch_slug}] 데이터 없음 — 건너뜀")
            continue

        rows = stats.get('rows', [])
        col_headers = [h['name'] for h in stats.get('columnHeaders', [])]

        if not rows:
            logger.info(f"[{ch_slug}] 영상 없음")
            continue

        views_list = []
        for row in rows:
            row_dict = dict(zip(col_headers, row))
            views_list.append(float(row_dict.get('views', 0)))

        prev_avg = sum(views_list) / len(views_list) if views_list else 0

        for row in rows:
            row_dict = dict(zip(col_headers, row))
            video_id    = row_dict.get('video', '')
            views       = float(row_dict.get('views', 0))
            avg_sec     = float(row_dict.get('averageViewDuration', 0))
            ctr_raw     = row_dict.get('clickThroughRate')
            ctr         = float(ctr_raw) * 100 if ctr_raw is not None else 5.0

            actions = engine.evaluate(
                video_id=video_id,
                title=row_dict.get('title', video_id),
                ch_slug=ch_slug,
                ctr=ctr,
                avg_view_sec=avg_sec,
                views=views,
                prev_avg_views=prev_avg,
            )

            for act in actions:
                if act['action'] == 'topic_expansion':
                    engine.queue_topic_expansion(ch_slug, act['title'])

            all_actions.extend(actions)

        summary['channels_checked'] += 1

    summary['total_actions']    = len(all_actions)
    summary['thumbnail_flags']  = sum(1 for a in all_actions if a['action'] == 'thumbnail_update')
    summary['retention_flags']  = sum(1 for a in all_actions if a['action'] == 'body1_redesign')
    summary['topic_expansions'] = sum(1 for a in all_actions if a['action'] == 'topic_expansion')

    engine.save_actions(all_actions, today)
    engine.save_report(summary, today)

    logger.info(
        f"=== 완료: 채널 {summary['channels_checked']}개, "
        f"썸네일 {summary['thumbnail_flags']}건, "
        f"리텐션 {summary['retention_flags']}건, "
        f"주제확장 {summary['topic_expansions']}건 ==="
    )
    return summary


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='GAONIX 성과 피드백 루프')
    parser.add_argument('--dry-run', action='store_true',
                        help='실제 API 호출 없이 구조 테스트')
    args = parser.parse_args()

    if args.dry_run:
        engine = PerformanceRuleEngine()
        test_actions = engine.evaluate(
            video_id='TEST_VID_001',
            title='테스트 영상',
            ch_slug='senior',
            ctr=2.5,
            avg_view_sec=300,
            views=15000,
            prev_avg_views=4000,
        )
        today = datetime.now().strftime('%Y-%m-%d')
        engine.save_actions(test_actions, today)
        print(f"\n[dry-run] 생성된 액션 {len(test_actions)}건:")
        for a in test_actions:
            print(f"  - {a['action']}: {a['reason']}")
    else:
        summary = run_performance_loop()
        print(f"\n완료: {summary}")

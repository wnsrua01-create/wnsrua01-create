#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명: youtube_uploader.py
목적: 완성본 MP4 → YouTube Data API v3 자동 업로드
작성일: 2026-05-22
설치 위치(Windows): D:/1인기업/01_youtube/scripts/youtube_uploader.py

사전 설치:
  pip install google-auth google-auth-oauthlib google-api-python-client

OAuth2 최초 인증:
  python youtube_uploader.py --ch senior --ep 1 --auth
  → 브라우저 인증 후 C:/gaon/config/yt_token_{ch_slug}.json 저장

사용법:
  python youtube_uploader.py --ch senior --ep 1
  python youtube_uploader.py --ch senior --ep 1 --schedule "2026-06-01T09:00:00+09:00"
  python youtube_uploader.py --ch senior --ep 1 --dry-run
"""
import sys
import os
import json
import time
import logging
import argparse
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

ROOT_FINALS  = Path('D:/gaon_data/finals')
ROOT_THUMBS  = Path('D:/gaon_data/thumbs')
ROOT_SCRIPTS = Path('D:/gaon_data/scripts')
CONFIG_PATH  = Path('C:/gaon/config/channels.json')
TOKEN_DIR    = Path('C:/gaon/config')
LOG_DIR      = Path('C:/gaon/logs')
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'youtube_uploader.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

CHANNEL_SLUGS = {
    'ch01': 'senior',  'ch02': 'finance', 'ch03': 'health',
    'ch04': 'pension', 'ch05': 'psych',   'ch06': 'realty',
    'ch07': 'parent',  'ch08': 'cooking', 'ch09': 'aitech',
    'ch10': 'travel',  'ch11': 'beauty',  'ch12': 'growth',
    'ch13': 'history', 'ch14': 'pets',    'ch15': 'home',
    'ch16': 'midlife', 'ch17': 'money',
}

# YouTube Data API v3 카테고리 (22=People&Blogs, 26=Howto, 27=Education)
CHANNEL_CATEGORY = {
    'senior': '26', 'finance': '27', 'health': '26', 'pension': '27',
    'psych':  '22', 'realty':  '27', 'parent': '26', 'cooking': '26',
    'aitech': '28', 'travel':  '19', 'beauty': '22', 'growth':  '27',
    'history':'27', 'pets':    '15', 'home':   '26', 'midlife': '22',
    'money':  '27',
}

SCOPES = ['https://www.googleapis.com/auth/youtube.upload',
          'https://www.googleapis.com/auth/youtube']


def _load_env():
    for p in [Path('C:/gaon/.env'), Path('D:/1인기업/.env')]:
        if not p.exists():
            continue
        with open(p, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

_load_env()


def _load_channel_config(ch_slug: str) -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f'channels.json 파싱 오류: {e}')
        return {}
    for _, info in cfg.get('channels', {}).items():
        if info.get('slug') == ch_slug:
            return info
    return {}


def _load_ep_data(ch_slug: str, ep_num: int) -> dict:
    ch_num = next((k for k, v in CHANNEL_SLUGS.items() if v == ch_slug), 'ch01')
    ep_str = f'ep{ep_num:02d}'
    ep_dir = ROOT_SCRIPTS / f'ch{int(ch_num[2:]):02d}_{ch_slug}' / ep_str
    for fname in [f'{ep_str}_data.json', 'data.json']:
        p = ep_dir / fname
        if p.exists():
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f'JSON 파싱 오류: {e}')
    return {}


def _get_credentials(ch_slug: str, client_secrets_file: Optional[str] = None):
    """OAuth2 자격증명 로드 (토큰 캐시 우선, 없으면 브라우저 인증)."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        logger.error('google-auth 미설치. pip install google-auth google-auth-oauthlib google-api-python-client')
        return None

    token_path = TOKEN_DIR / f'yt_token_{ch_slug}.json'
    creds = None

    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except Exception as e:
            logger.warning(f'토큰 로드 실패: {e}')

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info(f'[{ch_slug}] OAuth2 토큰 갱신 완료')
            except Exception as e:
                logger.warning(f'토큰 갱신 실패: {e}')
                creds = None

        if not creds:
            secrets = client_secrets_file or os.environ.get('YT_CLIENT_SECRETS', 'C:/gaon/config/yt_client_secret.json')
            if not Path(secrets).exists():
                logger.error(f'client_secrets 파일 없음: {secrets}')
                return None
            flow = InstalledAppFlow.from_client_secrets_file(secrets, SCOPES)
            creds = flow.run_local_server(port=0)
            logger.info(f'[{ch_slug}] OAuth2 인증 완료')

        TOKEN_DIR.mkdir(parents=True, exist_ok=True)
        with open(token_path, 'w', encoding='utf-8') as f:
            f.write(creds.to_json())

    return creds


def _find_video_file(ch_slug: str, ep_num: int) -> Optional[Path]:
    """완성본 MP4 파일 탐색."""
    ch_num = next((k for k, v in CHANNEL_SLUGS.items() if v == ch_slug), 'ch01')
    ep_str = f'ep{ep_num:02d}'
    ch_dir = ROOT_FINALS / f'ch{int(ch_num[2:]):02d}_{ch_slug}'

    candidates = [
        ch_dir / f'{ep_str}_final.mp4',
        ch_dir / f'{ch_slug}_{ep_str}_final.mp4',
        ch_dir / f'{ep_str}.mp4',
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _find_thumbnail(ch_slug: str, ep_num: int) -> Optional[Path]:
    ch_num = next((k for k, v in CHANNEL_SLUGS.items() if v == ch_slug), 'ch01')
    ep_str = f'ep{ep_num:02d}'
    ch_dir = ROOT_THUMBS / f'ch{int(ch_num[2:]):02d}_{ch_slug}'

    candidates = [
        ch_dir / f'{ep_str}_thumb.png',
        ch_dir / f'{ep_str}_thumb.jpg',
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _build_metadata(ch_slug: str, ep_num: int,
                     ch_cfg: dict, ep_data: dict,
                     schedule_time: Optional[str] = None) -> dict:
    """YouTube 업로드 메타데이터 구성."""
    name_kr = ch_cfg.get('name_kr', ch_slug)
    topics  = ch_cfg.get('topics', [])
    cta     = ch_cfg.get('cta', f'{name_kr} 채널을 구독해 보세요.')
    title   = ep_data.get('title', f'{name_kr} EP{ep_num:02d}')

    # 설명란: 씬 대사 요약 + 제휴링크 삽입점 + CTA
    scenes      = ep_data.get('scenes', [])
    intro_narrs = [sc.get('narration', '') for sc in scenes
                   if 1 <= sc.get('scene_num', 0) <= 5 and sc.get('narration')]
    description_parts = [
        title, '',
        '━' * 20,
        '📌 이 영상에서 알려드리는 내용',
        '━' * 20,
    ]
    description_parts.extend(f'• {n[:80]}' for n in intro_narrs[:3])
    description_parts += [
        '',
        '━' * 20,
        f'📺 {name_kr} 채널 구독',
        f'https://www.youtube.com/@{ch_slug}_gaonix',
        '',
        cta,
        '',
        '⏱ 타임스탬프',
        '00:00 인트로',
        '01:18 본론',
        '11:48 마무리',
        '',
        '#' + ' #'.join(topics[:5]),
    ]
    description = '\n'.join(description_parts)

    tags = list(topics[:10]) + [name_kr, 'GAONIX', '유튜브']

    privacy = 'private' if schedule_time else 'public'

    snippet = {
        'title':       title[:100],
        'description': description[:5000],
        'tags':        tags[:500],
        'categoryId':  CHANNEL_CATEGORY.get(ch_slug, '22'),
        'defaultLanguage': 'ko',
    }
    status = {
        'privacyStatus':           privacy,
        'selfDeclaredMadeForKids': False,
    }
    if schedule_time and privacy == 'private':
        status['publishAt'] = schedule_time

    return {'snippet': snippet, 'status': status}


def upload_video(ch_slug: str, ep_num: int,
                 schedule_time: Optional[str] = None,
                 dry_run: bool = False) -> dict:
    """YouTube 업로드 실행."""
    logger.info(f'YouTube 업로드 시작: {ch_slug} EP{ep_num:02d}')

    ch_cfg   = _load_channel_config(ch_slug)
    ep_data  = _load_ep_data(ch_slug, ep_num)
    video_path = _find_video_file(ch_slug, ep_num)
    thumb_path = _find_thumbnail(ch_slug, ep_num)

    if not video_path:
        logger.error(f'영상 파일 없음: {ch_slug} EP{ep_num:02d}')
        return {'ok': False, 'reason': '영상 파일 없음'}

    metadata = _build_metadata(ch_slug, ep_num, ch_cfg, ep_data, schedule_time)
    logger.info(f'  제목: {metadata["snippet"]["title"]}')
    logger.info(f'  영상: {video_path}')
    logger.info(f'  썸네일: {thumb_path or "없음"}')

    if dry_run:
        logger.info('[dry-run] 업로드 시뮬레이션 완료')
        return {'ok': True, 'dry_run': True, 'title': metadata['snippet']['title']}

    creds = _get_credentials(ch_slug)
    if not creds:
        logger.error('OAuth2 인증 실패')
        return {'ok': False, 'reason': 'OAuth2 인증 실패'}

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        youtube = build('youtube', 'v3', credentials=creds)

        media = MediaFileUpload(
            str(video_path),
            mimetype='video/mp4',
            resumable=True,
            chunksize=10 * 1024 * 1024,  # 10MB 청크
        )

        request = youtube.videos().insert(
            part='snippet,status',
            body=metadata,
            media_body=media,
        )

        logger.info('업로드 시작 (대용량 파일은 시간이 걸립니다)...')
        response = None
        while response is None:
            status_obj, response = request.next_chunk()
            if status_obj:
                pct = int(status_obj.progress() * 100)
                logger.info(f'  진행: {pct}%')

        video_id = response.get('id', '')
        yt_url   = f'https://www.youtube.com/watch?v={video_id}'
        logger.info(f'✅ 업로드 완료: {yt_url}')

        # 썸네일 설정
        if thumb_path and video_id:
            try:
                from googleapiclient.http import MediaFileUpload as MFU
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MFU(str(thumb_path), mimetype='image/png'),
                ).execute()
                logger.info('썸네일 설정 완료')
            except Exception as e:
                logger.warning(f'썸네일 설정 실패: {type(e).__name__}')

        # 업로드 결과 저장
        _save_upload_record(ch_slug, ep_num, video_id, yt_url, metadata)

        return {'ok': True, 'video_id': video_id, 'url': yt_url}

    except Exception as e:
        logger.error(f'업로드 오류: {type(e).__name__}: {str(e)[:100]}')
        return {'ok': False, 'reason': str(e)[:100]}


def _save_upload_record(ch_slug: str, ep_num: int,
                         video_id: str, url: str, metadata: dict) -> None:
    """업로드 기록 저장."""
    record_dir = Path('D:/1인기업/01_youtube/upload_records')
    record_dir.mkdir(parents=True, exist_ok=True)
    record = {
        'ch_slug':   ch_slug,
        'ep_num':    ep_num,
        'video_id':  video_id,
        'url':       url,
        'title':     metadata['snippet']['title'],
        'uploaded_at': datetime.now().isoformat(),
    }
    date_str = datetime.now().strftime('%Y%m%d')
    out = record_dir / f'{ch_slug}_ep{ep_num:02d}_{date_str}.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    logger.info(f'업로드 기록 저장: {out.name}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='GAONIX YouTube 자동 업로드')
    parser.add_argument('--ch',       required=True,  help='채널 슬러그')
    parser.add_argument('--ep',       type=int, required=True, help='에피소드 번호')
    parser.add_argument('--schedule', default=None,
                        help='예약 발행 시각 (ISO8601, 예: 2026-06-01T09:00:00+09:00)')
    parser.add_argument('--dry-run',  action='store_true', help='업로드 없이 메타데이터 확인')
    parser.add_argument('--auth',     action='store_true', help='OAuth2 인증만 실행')
    args = parser.parse_args()

    valid_slugs = set(CHANNEL_SLUGS.values())
    if args.ch not in valid_slugs:
        parser.error(f'알 수 없는 채널: {args.ch!r}')
    if not (1 <= args.ep <= 9999):
        parser.error(f'EP 범위 오류: {args.ep}')

    if args.auth:
        creds = _get_credentials(args.ch)
        print(f'인증 {"완료" if creds else "실패"}: {args.ch}')
        sys.exit(0 if creds else 1)

    result = upload_video(args.ch, args.ep, args.schedule, args.dry_run)
    if result['ok']:
        print(f'✅ 완료: {result.get("url", "(dry-run)")}')
    else:
        print(f'❌ 실패: {result.get("reason", "")}')
        sys.exit(1)

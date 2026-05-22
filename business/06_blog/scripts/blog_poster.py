#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명: blog_poster.py
목적: EP 완성 후 네이버/티스토리 블로그 자동 포스팅
작성일: 2026-05-21
설치 위치(Windows): D:/1인기업/06_blog/scripts/blog_poster.py

사용법:
  python blog_poster.py --ch senior --ep 1
  python blog_poster.py --ch senior --ep 1 --platform naver
  python blog_poster.py --ch all --ep 1 --dry-run

의존성: pip install requests selenium (티스토리 자동화 시)
"""
import sys
import os
import json
import logging
import argparse
import time
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
ROOT_SCRIPTS  = Path('D:/gaon_data/scripts')
ROOT_BLOG     = Path('D:/1인기업/06_blog')
CONFIG_PATH   = Path('C:/gaon/config/channels.json')
LOG_DIR       = Path('C:/gaon/logs')
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'blog_poster.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# .env 로드
def _load_env():
    for env_path in [Path('C:/gaon/.env'), Path('D:/1인기업/.env')]:
        if not env_path.exists():
            continue
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

_load_env()

CHANNEL_SLUGS = {
    'ch01': 'senior',  'ch02': 'finance', 'ch03': 'health',
    'ch04': 'pension', 'ch05': 'psych',   'ch06': 'realty',
    'ch07': 'parent',  'ch08': 'cooking', 'ch09': 'aitech',
    'ch10': 'travel',  'ch11': 'beauty',  'ch12': 'growth',
    'ch13': 'history', 'ch14': 'pets',    'ch15': 'home',
    'ch16': 'midlife', 'ch17': 'money',
}


def _load_channel_config(ch_slug: str) -> dict:
    """channels.json에서 채널 설정 로드."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f'channels.json 파싱 오류: {e}')
        return {}
    for chid, info in cfg.get('channels', {}).items():
        if info.get('slug') == ch_slug:
            return info
    return {}


def _load_ep_data(ch_slug: str, ep_num: int) -> dict:
    """에피소드 대본 데이터 로드."""
    ch_num = next((k for k, v in CHANNEL_SLUGS.items() if v == ch_slug), 'ch01')
    num = int(ch_num[2:])
    ep_str = f'ep{ep_num:02d}'
    ep_dir = ROOT_SCRIPTS / f'ch{num:02d}_{ch_slug}' / ep_str

    for fname in [f'{ep_str}_data.json', 'data.json', f'{ep_str}.json']:
        p = ep_dir / fname
        if p.exists():
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f'JSON 파싱 오류 {p.name}: {e}')
    return {}


def generate_blog_content(ch_slug: str, ep_num: int) -> dict:
    """
    대본 데이터 → 블로그 포스트 내용 생성.

    Returns:
        {'title': str, 'content': str, 'tags': list, 'thumbnail': str}
    """
    ch_cfg  = _load_channel_config(ch_slug)
    ep_data = _load_ep_data(ch_slug, ep_num)

    ep_str = f'ep{ep_num:02d}'
    ch_name_kr = ch_cfg.get('name_kr', ch_slug)
    title = ep_data.get('title', f'{ch_name_kr} EP{ep_num:02d}')
    topics = ch_cfg.get('topics', [])
    tone   = ch_cfg.get('tone', '')

    # 씬별 대사 수집
    scenes = ep_data.get('scenes', [])
    intro_lines = [
        sc.get('narration', '') for sc in scenes
        if 1 <= sc.get('scene_num', 0) <= 13 and sc.get('narration')
    ]
    body_lines = [
        sc.get('narration', '') for sc in scenes
        if 14 <= sc.get('scene_num', 0) <= 50 and sc.get('narration')
    ]
    outro_lines = [
        sc.get('narration', '') for sc in scenes
        if 118 <= sc.get('scene_num', 0) <= 130 and sc.get('narration')
    ]

    # 포스트 본문 조립
    now_str = datetime.now().strftime('%Y년 %m월 %d일')
    content_parts = [
        f'# {title}',
        f'\n> {now_str} | {ch_name_kr} EP{ep_num:02d}\n',
    ]

    if intro_lines:
        content_parts.append('## 오늘의 핵심 내용\n')
        content_parts.append('\n'.join(intro_lines[:3]))
        content_parts.append('')

    if body_lines:
        content_parts.append('\n## 자세히 알아보기\n')
        content_parts.append('\n\n'.join(body_lines[:5]))
        content_parts.append('')

    if outro_lines:
        content_parts.append('\n## 실천 포인트\n')
        for line in outro_lines[:3]:
            sentences = [s.strip() for s in line.replace('。', '.').split('.') if s.strip()]
            for s in sentences[:2]:
                content_parts.append(f'- {s}')
        content_parts.append('')

    cta = ch_cfg.get('cta', f'{ch_name_kr} 채널을 구독해 보세요.')
    content_parts.append(f'\n---\n\n{cta}')
    content_parts.append(
        f'\n▶ YouTube: https://www.youtube.com/@{ch_slug}_gaonix'
    )

    # 기본 주제 태그
    tags = list(topics[:5]) + [ch_name_kr, 'GAONIX', '유튜브', '자동화']

    # 썸네일 경로 탐색
    ch_num = next((k for k, v in CHANNEL_SLUGS.items() if v == ch_slug), 'ch01')
    thumb_candidates = [
        Path(f'D:/gaon_data/thumbs/ch{int(ch_num[2:]):02d}_{ch_slug}/{ep_str}_thumb.png'),
        Path(f'D:/gaon_data/finals/ch{int(ch_num[2:]):02d}_{ch_slug}/{ep_str}_thumb.png'),
    ]
    thumbnail = next((str(p) for p in thumb_candidates if p.exists()), '')

    return {
        'title':     title,
        'content':   '\n'.join(content_parts),
        'tags':      tags,
        'thumbnail': thumbnail,
        'ch_slug':   ch_slug,
        'ep_num':    ep_num,
        'generated': datetime.now().isoformat(),
    }


def save_draft(post: dict, platform: str) -> Path:
    """블로그 포스트 초안 저장."""
    out_dir = ROOT_BLOG / platform
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{post['ch_slug']}_ep{post['ep_num']:02d}_{datetime.now().strftime('%Y%m%d')}.md"
    out = out_dir / fname
    with open(out, 'w', encoding='utf-8') as f:
        f.write(f"---\ntitle: {post['title']}\ntags: {post['tags']}\n---\n\n")
        f.write(post['content'])
    logger.info(f'초안 저장: {out}')
    return out


def post_to_naver(post: dict, dry_run: bool = False) -> bool:
    """
    네이버 블로그 포스팅.
    네이버 블로그 Open API → 실제 구현은 OAuth 토큰 필요.
    현재: 초안 저장 + 로그 기록 (API 승인 후 확장)
    """
    logger.info(f'[네이버] 포스팅 준비: {post["title"]}')

    draft_path = save_draft(post, 'naver')

    if dry_run:
        logger.info(f'[dry-run] 네이버 포스팅 시뮬레이션: {draft_path}')
        return True

    naver_token = os.environ.get('NAVER_BLOG_TOKEN', '')
    if not naver_token:
        logger.warning('[네이버] NAVER_BLOG_TOKEN 미설정 — 초안만 저장됨')
        logger.info(f'          초안 위치: {draft_path}')
        logger.info('          네이버 블로그 API 발급 후 .env에 추가하세요')
        return False

    # TODO: 네이버 블로그 API 실제 호출
    # POST https://openapi.naver.com/blog/writePost.json
    # Headers: Authorization: Bearer {naver_token}
    logger.info(f'[네이버] ✅ 포스팅 성공 (시뮬레이션): {post["title"]}')
    return True


def post_to_tistory(post: dict, dry_run: bool = False) -> bool:
    """
    티스토리 블로그 포스팅.
    Tistory Open API v1 사용 (OAuth 토큰 필요).
    """
    logger.info(f'[티스토리] 포스팅 준비: {post["title"]}')

    draft_path = save_draft(post, 'tistory')

    if dry_run:
        logger.info(f'[dry-run] 티스토리 포스팅 시뮬레이션: {draft_path}')
        return True

    tistory_token  = os.environ.get('TISTORY_ACCESS_TOKEN', '')
    tistory_blogid = os.environ.get('TISTORY_BLOG_ID', '')

    if not tistory_token or not tistory_blogid:
        logger.warning('[티스토리] TISTORY_ACCESS_TOKEN / TISTORY_BLOG_ID 미설정 — 초안만 저장됨')
        logger.info(f'            초안 위치: {draft_path}')
        return False

    try:
        import requests
        url = 'https://www.tistory.com/apis/post/write'
        params = {
            'output':     'json',
            'blogName':   tistory_blogid,
            'title':      post['title'],
            'content':    post['content'],
            'visibility': 3,  # 공개
            'tag':        ','.join(post['tags'][:10]),
        }
        headers = {'Authorization': f'Bearer {tistory_token}'}
        resp = requests.post(url, data=params, headers=headers, timeout=30)
        if resp.status_code == 200:
            result = resp.json()
            if result.get('tistory', {}).get('status') == '200':
                logger.info(f'[티스토리] ✅ 포스팅 성공: {post["title"]}')
                return True
        logger.error(f'[티스토리] 실패: {resp.text[:200]}')
        return False
    except ImportError:
        logger.warning('requests 미설치. pip install requests')
        return False
    except Exception as e:
        logger.error(f'[티스토리] 오류: {e}')
        return False


def run(ch_slug: str, ep_num: int, platforms: list[str],
        dry_run: bool = False) -> dict:
    """단일 EP 블로그 포스팅 실행."""
    logger.info(f'블로그 포스팅 시작: {ch_slug} EP{ep_num:02d}')

    post = generate_blog_content(ch_slug, ep_num)
    logger.info(f'  제목: {post["title"]}')
    logger.info(f'  태그: {post["tags"]}')

    results = {}
    for platform in platforms:
        if platform == 'naver':
            results['naver'] = post_to_naver(post, dry_run)
        elif platform == 'tistory':
            results['tistory'] = post_to_tistory(post, dry_run)
        else:
            logger.warning(f'미지원 플랫폼: {platform}')

    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='GAONIX 블로그 자동 포스터')
    parser.add_argument('--ch', required=True, help='채널 슬러그 (예: senior) 또는 all')
    parser.add_argument('--ep', type=int, required=True, help='에피소드 번호')
    parser.add_argument('--platform', default='naver,tistory',
                        help='플랫폼 (naver,tistory 또는 개별)')
    parser.add_argument('--dry-run', action='store_true', help='실제 포스팅 없이 초안만 저장')
    args = parser.parse_args()

    valid_slugs = set(CHANNEL_SLUGS.values())
    if args.ch == 'all':
        slugs = list(valid_slugs)
    elif args.ch in valid_slugs:
        slugs = [args.ch]
    else:
        parser.error(f'알 수 없는 채널 슬러그: {args.ch!r}\n유효 값: {sorted(valid_slugs)}')

    if not 1 <= args.ep <= 9999:
        parser.error(f'에피소드 번호 범위 오류: {args.ep}')

    valid_platforms = {'naver', 'tistory', 'wordpress'}
    platforms = [p.strip() for p in args.platform.split(',')]
    for p in platforms:
        if p not in valid_platforms:
            parser.error(f'지원하지 않는 플랫폼: {p!r} (지원: {valid_platforms})')

    for slug in slugs:
        result = run(slug, args.ep, platforms, args.dry_run)
        print(f'[{slug}] EP{args.ep:02d}: {result}')

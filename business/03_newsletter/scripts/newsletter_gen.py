#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명: newsletter_gen.py
목적: EP 완성 후 뉴스레터 자동 생성 및 Stibee/Mailchimp 발송
작성일: 2026-05-21
설치 위치(Windows): D:/1인기업/03_newsletter/scripts/newsletter_gen.py

사용법:
  python newsletter_gen.py --ch senior --ep 1
  python newsletter_gen.py --ch senior --ep 1 --dry-run
  python newsletter_gen.py --weekly-digest

환경변수 (.env):
  STIBEE_API_KEY=...          (Stibee API 키)
  STIBEE_LIST_ID=...          (구독자 목록 ID)
  MAILCHIMP_API_KEY=...       (Mailchimp API 키)
  MAILCHIMP_LIST_ID=...       (Mailchimp 목록 ID)
  MAILCHIMP_SERVER_PREFIX=... (예: us21)
"""
import sys
import os
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime, timedelta
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
ROOT_SCRIPTS    = Path('D:/gaon_data/scripts')
ROOT_NEWSLETTER = Path('D:/1인기업/03_newsletter')
CONFIG_PATH     = Path('C:/gaon/config/channels.json')
LOG_DIR         = Path('C:/gaon/logs')
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'newsletter_gen.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

def _load_env():
    for p in [Path('C:/gaon/.env'), Path('D:/1인기업/.env')]:
        if not p.exists():
            continue
        with open(p, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip())

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
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    for chid, info in cfg.get('channels', {}).items():
        if info.get('slug') == ch_slug:
            return info
    return {}


def _load_ep_data(ch_slug: str, ep_num: int) -> dict:
    ch_num = next((k for k, v in CHANNEL_SLUGS.items() if v == ch_slug), 'ch01')
    num    = int(ch_num[2:])
    ep_str = f'ep{ep_num:02d}'
    ep_dir = ROOT_SCRIPTS / f'ch{num:02d}_{ch_slug}' / ep_str
    for fname in [f'{ep_str}_data.json', 'data.json']:
        p = ep_dir / fname
        if p.exists():
            with open(p, 'r', encoding='utf-8') as f:
                return json.load(f)
    return {}


def build_html_newsletter(ch_slug: str, ep_num: int) -> dict:
    """
    대본 데이터 → HTML 뉴스레터 생성.

    Returns:
        {'subject': str, 'html': str, 'text': str}
    """
    ch_cfg  = _load_channel_config(ch_slug)
    ep_data = _load_ep_data(ch_slug, ep_num)

    ch_name_kr = ch_cfg.get('name_kr', ch_slug)
    title      = ep_data.get('title', f'{ch_name_kr} EP{ep_num:02d}')
    color      = ch_cfg.get('color_theme', '#FF4500')
    cta        = ch_cfg.get('cta', '구독해 주세요!')
    topics     = ch_cfg.get('topics', [])

    # 씬 추출
    scenes = ep_data.get('scenes', [])
    intro  = [sc.get('narration','') for sc in scenes
              if 1 <= sc.get('scene_num',0) <= 13 and sc.get('narration')]
    key_points = [sc.get('narration','') for sc in scenes
                  if 14 <= sc.get('scene_num',0) <= 50 and sc.get('narration')]
    checklist  = [sc.get('narration','') for sc in scenes
                  if 118 <= sc.get('scene_num',0) <= 130 and sc.get('narration')]

    # 핵심 포인트 → 리스트 항목
    key_items = []
    for text in key_points[:4]:
        sentences = [s.strip() for s in text.replace('。','.').split('.') if len(s.strip()) > 10]
        key_items.extend(sentences[:1])

    # 체크리스트 항목
    check_items = []
    for text in checklist[:3]:
        sentences = [s.strip() for s in text.replace('。','.').split('.') if len(s.strip()) > 5]
        check_items.extend(sentences[:2])

    now_str   = datetime.now().strftime('%Y년 %m월 %d일')
    intro_txt = intro[0] if intro else f'{ch_name_kr}의 새 에피소드가 도착했습니다!'

    subject = f'[{ch_name_kr}] {title}'

    # HTML 템플릿
    key_li  = ''.join(f'<li style="margin-bottom:8px">{item}</li>' for item in key_items[:4]) \
              or '<li>이번 에피소드를 YouTube에서 확인하세요!</li>'
    check_li = ''.join(
        f'<li style="margin-bottom:6px">☐ {item}</li>' for item in check_items[:5]
    ) or '<li>☐ 오늘 배운 내용을 하나 실천해 보세요</li>'

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{subject}</title>
</head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:'Noto Sans KR',Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:20px 0">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0"
       style="background:#fff;border-radius:8px;overflow:hidden;max-width:600px">

  <!-- 헤더 -->
  <tr>
    <td style="background:{color};padding:30px;text-align:center">
      <p style="color:rgba(255,255,255,0.8);margin:0 0 8px;font-size:13px">GAONIX | {ch_name_kr}</p>
      <h1 style="color:#fff;margin:0;font-size:22px;line-height:1.4">{title}</h1>
      <p style="color:rgba(255,255,255,0.7);margin:10px 0 0;font-size:12px">{now_str}</p>
    </td>
  </tr>

  <!-- 인트로 -->
  <tr>
    <td style="padding:30px 30px 0">
      <p style="font-size:16px;line-height:1.7;color:#333;margin:0">{intro_txt}</p>
    </td>
  </tr>

  <!-- 핵심 내용 -->
  <tr>
    <td style="padding:24px 30px 0">
      <h2 style="color:{color};font-size:16px;margin:0 0 12px;border-left:4px solid {color};padding-left:10px">
        이번 에피소드 핵심 포인트
      </h2>
      <ul style="padding-left:20px;margin:0;color:#444;font-size:14px;line-height:1.8">
        {key_li}
      </ul>
    </td>
  </tr>

  <!-- 실천 체크리스트 -->
  <tr>
    <td style="padding:24px 30px 0">
      <h2 style="color:{color};font-size:16px;margin:0 0 12px;border-left:4px solid {color};padding-left:10px">
        오늘의 실천 체크리스트
      </h2>
      <ul style="padding-left:20px;margin:0;color:#444;font-size:14px;line-height:1.9;list-style:none">
        {check_li}
      </ul>
    </td>
  </tr>

  <!-- CTA 버튼 -->
  <tr>
    <td style="padding:30px;text-align:center">
      <a href="https://www.youtube.com/@{ch_slug}_gaonix"
         style="background:{color};color:#fff;padding:14px 32px;border-radius:6px;
                text-decoration:none;font-size:15px;font-weight:bold;display:inline-block">
        ▶ YouTube에서 전체 보기
      </a>
    </td>
  </tr>

  <!-- 푸터 -->
  <tr>
    <td style="background:#f8f8f8;padding:20px 30px;text-align:center;border-top:1px solid #eee">
      <p style="color:#999;font-size:12px;margin:0">{cta}</p>
      <p style="color:#bbb;font-size:11px;margin:8px 0 0">
        GAONIX | AI가 일하고, 당신이 쉰다<br>
        <a href="{{{{unsubscribe_url}}}}" style="color:#bbb">수신 거부</a>
      </p>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""

    # 텍스트 버전
    text = f"""{subject}

{intro_txt}

[핵심 포인트]
{chr(10).join(f'• {item}' for item in key_items[:4]) or '• YouTube에서 확인하세요!'}

[실천 체크리스트]
{chr(10).join(f'☐ {item}' for item in check_items[:5]) or '☐ 오늘 배운 내용 하나 실천하기'}

▶ YouTube: https://www.youtube.com/@{ch_slug}_gaonix

---
{cta}
GAONIX | AI가 일하고, 당신이 쉰다
"""
    return {'subject': subject, 'html': html, 'text': text}


def save_newsletter(newsletter: dict, ch_slug: str, ep_num: int) -> Path:
    """뉴스레터 HTML 파일 저장."""
    out_dir = ROOT_NEWSLETTER / 'sent'
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{ch_slug}_ep{ep_num:02d}_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
    out = out_dir / fname
    with open(out, 'w', encoding='utf-8') as f:
        f.write(newsletter['html'])
    logger.info(f'뉴스레터 저장: {out}')
    return out


def send_via_stibee(newsletter: dict, dry_run: bool = False) -> bool:
    """Stibee API로 뉴스레터 발송."""
    api_key = os.environ.get('STIBEE_API_KEY', '')
    list_id = os.environ.get('STIBEE_LIST_ID', '')

    if not api_key or not list_id:
        logger.warning('[Stibee] API 키 미설정 — .env에 STIBEE_API_KEY, STIBEE_LIST_ID 추가')
        return False

    if dry_run:
        logger.info(f'[dry-run] Stibee 발송 시뮬레이션: {newsletter["subject"]}')
        return True

    try:
        import requests
        url = f'https://api.stibee.com/v1/addresses/{list_id}/campaigns'
        headers = {'AccessToken': api_key, 'Content-Type': 'application/json'}
        payload = {
            'name':     newsletter['subject'],
            'subject':  newsletter['subject'],
            'fromName': 'GAONIX',
            'html':     newsletter['html'],
            'text':     newsletter['text'],
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            logger.info(f'[Stibee] ✅ 발송 성공: {newsletter["subject"]}')
            return True
        logger.error(f'[Stibee] 실패: {resp.status_code} {resp.text[:200]}')
        return False
    except ImportError:
        logger.warning('requests 미설치. pip install requests')
        return False
    except Exception as e:
        logger.error(f'[Stibee] 오류: {e}')
        return False


def send_via_mailchimp(newsletter: dict, dry_run: bool = False) -> bool:
    """Mailchimp API로 뉴스레터 발송."""
    api_key = os.environ.get('MAILCHIMP_API_KEY', '')
    list_id = os.environ.get('MAILCHIMP_LIST_ID', '')
    server  = os.environ.get('MAILCHIMP_SERVER_PREFIX', 'us1')

    if not api_key or not list_id:
        logger.warning('[Mailchimp] API 키 미설정')
        return False

    if dry_run:
        logger.info(f'[dry-run] Mailchimp 발송 시뮬레이션: {newsletter["subject"]}')
        return True

    try:
        import requests
        from requests.auth import HTTPBasicAuth

        url = f'https://{server}.api.mailchimp.com/3.0/campaigns'
        auth = HTTPBasicAuth('anystring', api_key)
        payload = {
            'type': 'regular',
            'recipients': {'list_id': list_id},
            'settings': {
                'subject_line': newsletter['subject'],
                'from_name':    'GAONIX',
                'reply_to':     os.environ.get('REPLY_TO_EMAIL', 'noreply@gaonix.com'),
            },
        }
        resp = requests.post(url, auth=auth, json=payload, timeout=30)
        if resp.status_code == 200:
            campaign_id = resp.json().get('id', '')
            # 캠페인 콘텐츠 설정
            content_url = f'https://{server}.api.mailchimp.com/3.0/campaigns/{campaign_id}/content'
            requests.put(content_url, auth=auth, json={
                'html': newsletter['html'],
                'plain_text': newsletter['text'],
            }, timeout=30)
            logger.info(f'[Mailchimp] ✅ 캠페인 생성: {campaign_id}')
            return True
        logger.error(f'[Mailchimp] 실패: {resp.text[:200]}')
        return False
    except ImportError:
        logger.warning('requests 미설치. pip install requests')
        return False
    except Exception as e:
        logger.error(f'[Mailchimp] 오류: {e}')
        return False


def run(ch_slug: str, ep_num: int, dry_run: bool = False) -> dict:
    """단일 EP 뉴스레터 발송 실행."""
    logger.info(f'뉴스레터 생성 시작: {ch_slug} EP{ep_num:02d}')

    newsletter = build_html_newsletter(ch_slug, ep_num)
    logger.info(f'  제목: {newsletter["subject"]}')

    saved = save_newsletter(newsletter, ch_slug, ep_num)

    results = {
        'stibee':    send_via_stibee(newsletter, dry_run),
        'mailchimp': send_via_mailchimp(newsletter, dry_run),
        'saved':     str(saved),
    }
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='GAONIX 뉴스레터 자동 발송')
    parser.add_argument('--ch', required=True, help='채널 슬러그 (예: senior)')
    parser.add_argument('--ep', type=int, required=True, help='에피소드 번호')
    parser.add_argument('--dry-run', action='store_true', help='실제 발송 없이 테스트')
    args = parser.parse_args()

    result = run(args.ch, args.ep, args.dry_run)
    print(f'\n결과: {result}')

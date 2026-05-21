#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명: affiliate_matcher.py
목적: EP 대본 키워드 → 쿠팡파트너스(AF7354598) 제휴링크 자동 매핑
작성일: 2026-05-21
설치 위치(Windows): D:/1인기업/07_affiliate/scripts/affiliate_matcher.py

사용법:
  python affiliate_matcher.py --ch senior --ep 1
  python affiliate_matcher.py --ch senior --ep 1 --dry-run
  python affiliate_matcher.py --ch all --ep 1

환경변수 (.env):
  COUPANG_ACCESS_KEY=...   (쿠팡파트너스 API Access Key)
  COUPANG_SECRET_KEY=...   (쿠팡파트너스 API Secret Key)
  COUPANG_AF_ID=AF7354598  (파트너스 ID)
"""
import sys
import os
import json
import hmac
import hashlib
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode, quote

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
ROOT_SCRIPTS   = Path('D:/gaon_data/scripts')
ROOT_AFFILIATE = Path('D:/1인기업/07_affiliate')
CONFIG_PATH    = Path('C:/gaon/config/channels.json')
LOG_DIR        = Path('C:/gaon/logs')
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'affiliate_matcher.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

COUPANG_AF_ID = 'AF7354598'

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

# ── 채널별 키워드 → 쿠팡 카테고리 매핑 ─────────────────────────────────────
CHANNEL_CATEGORY_MAP = {
    'senior':  ['건강식품', '시니어 건강', '혈압계', '안마기', '보청기', '영양제'],
    'finance': ['재테크 책', '가계부', '금융 도서', '계산기', '투자 책'],
    'health':  ['운동기구', '건강식품', '마사지기', '체중계', '혈당계', '영양제'],
    'pension': ['연금 도서', '노후 준비', '보험', '연금저축'],
    'psych':   ['심리 책', '명상 용품', '다이어리', '힐링 음악'],
    'realty':  ['부동산 책', '계약서', '인테리어', '리모델링'],
    'parent':  ['육아용품', '교육 교재', '장난감', '아기 식품', '유아 의류'],
    'cooking': ['주방용품', '식재료', '요리책', '에어프라이어', '냄비'],
    'aitech':  ['AI 책', '노트북', '키보드', '마우스', '모니터', '태블릿'],
    'travel':  ['여행 가방', '여행 용품', '카메라', '여행 책', '목베개'],
    'beauty':  ['스킨케어', '화장품', '뷰티 도구', '향수', '헤어 케어'],
    'growth':  ['자기계발 책', '다이어리', '플래너', '독서대', '메모지'],
    'history': ['역사 책', '한국사', '세계사', '지도', '교양 도서'],
    'pets':    ['강아지 사료', '고양이 용품', '반려동물 장난감', '동물 병원'],
    'home':    ['청소용품', '수납 용품', '주방 도구', '생활 가전', '정리함'],
    'midlife': ['건강식품', '운동복', '여행 용품', '뷰티', '자기계발 책'],
    'money':   ['주식 책', '경제 책', '금융 도구', '재테크 강의'],
}

# 쿠팡파트너스 단축 링크 base
COUPANG_PARTNERS_BASE = f'https://link.coupang.com/a/{COUPANG_AF_ID}'


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


def extract_keywords(ep_data: dict, ch_slug: str) -> list[str]:
    """
    대본에서 상품 연관 키워드 추출.
    채널 카테고리 기본값 + 대본 내 명사 추출.
    """
    base_keywords = CHANNEL_CATEGORY_MAP.get(ch_slug, [])

    # 대본 내 언급 키워드 수집 (간단한 패턴 매칭)
    scenes = ep_data.get('scenes', [])
    all_text = ' '.join(
        sc.get('narration', '') for sc in scenes if sc.get('narration')
    )

    # 상품 연관 패턴 (확장 가능)
    import re
    product_patterns = [
        r'([가-힣]{2,6}(?:기기|제품|용품|도구|책|앱|서비스|식품|영양제|보조제))',
        r'([가-힣]{2,4}(?:계|기|대|통|판|함|대|틀|기계))',
    ]
    extracted = []
    for pat in product_patterns:
        extracted.extend(re.findall(pat, all_text))

    # 중복 제거 + base 키워드 합산
    combined = list(dict.fromkeys(base_keywords + extracted[:5]))
    return combined[:10]


def _make_coupang_api_request(keyword: str) -> Optional[list]:
    """
    쿠팡파트너스 상품 검색 API 호출.
    API 승인 전: 더미 데이터 반환
    """
    access_key = os.environ.get('COUPANG_ACCESS_KEY', '')
    secret_key  = os.environ.get('COUPANG_SECRET_KEY', '')

    if not access_key or not secret_key:
        # API 미승인 상태: 쿠팡 검색 URL 직접 생성
        search_url = (
            f'https://www.coupang.com/np/search?component=&q={quote(keyword)}'
            f'&channel=auto&autoSuggest=true'
        )
        return [{'productName': keyword, 'productUrl': search_url, 'price': 0, 'api': False}]

    # 쿠팡파트너스 API HMAC 인증
    try:
        import urllib.request
        timestamp  = str(int(time.time() * 1000))
        method     = 'GET'
        path       = '/v2/providers/affiliate_open_api/apis/openapi/v1/products/search'
        params     = {'keyword': keyword, 'limit': 5, 'subId': COUPANG_AF_ID}
        query      = urlencode(params)
        message    = f'{timestamp}{method}{path}{query}'
        signature  = hmac.new(
            secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

        url = f'https://api-gateway.coupang.com{path}?{query}'
        req = urllib.request.Request(url)
        req.add_header('Authorization', f'CEA algorithm=HmacSHA256, access-key={access_key}, signed-date={timestamp}, signature={signature}')

        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get('data', {}).get('productData', [])
    except Exception as e:
        logger.warning(f'쿠팡 API 오류 ({keyword}): {e}')
        return None


def generate_affiliate_links(ch_slug: str, ep_num: int) -> list[dict]:
    """
    채널 + 에피소드 → 쿠팡파트너스 제휴링크 목록 생성.
    """
    ep_data  = _load_ep_data(ch_slug, ep_num)
    keywords = extract_keywords(ep_data, ch_slug)

    logger.info(f'키워드 추출: {keywords}')

    links = []
    for kw in keywords[:5]:  # 최대 5개 키워드
        products = _make_coupang_api_request(kw)
        if not products:
            continue
        for prod in products[:2]:  # 키워드당 최대 2개 상품
            links.append({
                'keyword':     kw,
                'productName': prod.get('productName', kw),
                'productUrl':  prod.get('productUrl', ''),
                'price':       prod.get('productPrice', prod.get('price', 0)),
                'af_id':       COUPANG_AF_ID,
                'api_used':    prod.get('api', True),
            })
        time.sleep(0.2)  # API rate limit

    return links


def build_youtube_description(ch_slug: str, ep_num: int,
                               links: list[dict]) -> str:
    """YouTube 영상 설명란 자동 생성 (제휴링크 포함)."""
    ep_data    = _load_ep_data(ch_slug, ep_num)
    title      = ep_data.get('title', f'EP{ep_num:02d}')
    ch_name    = next(
        (info.get('name_kr','') for chid, info in _load_all_channels().items()
         if info.get('slug') == ch_slug), ch_slug
    )

    lines = [
        f'📌 {title}',
        '',
        '━━━━━━━━━━━━━━━━━━━━',
        '🛒 영상 속 추천 제품',
        '━━━━━━━━━━━━━━━━━━━━',
    ]
    for lnk in links[:5]:
        name = lnk['productName']
        url  = lnk['productUrl']
        price = f" ({lnk['price']:,}원~)" if lnk.get('price') else ''
        lines.append(f'• {name}{price}')
        lines.append(f'  → {url}')

    lines += [
        '',
        '━━━━━━━━━━━━━━━━━━━━',
        f'📺 {ch_name} 채널 구독하기',
        f'https://www.youtube.com/@{ch_slug}_gaonix',
        '',
        f'※ 이 영상은 쿠팡파트너스 활동의 일환으로, 일정액의 수수료를 제공받습니다.',
        f'※ AF ID: {COUPANG_AF_ID}',
    ]
    return '\n'.join(lines)


def _load_all_channels() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f).get('channels', {})


def save_links(ch_slug: str, ep_num: int, links: list[dict],
               description: str) -> dict:
    """제휴링크 및 설명란 저장."""
    out_dir = ROOT_AFFILIATE / 'coupang' / 'links'
    out_dir.mkdir(parents=True, exist_ok=True)

    ep_str   = f'ep{ep_num:02d}'
    date_str = datetime.now().strftime('%Y%m%d')

    # JSON 링크 저장
    links_path = out_dir / f'{ch_slug}_{ep_str}_{date_str}_links.json'
    with open(links_path, 'w', encoding='utf-8') as f:
        json.dump({
            'ch_slug': ch_slug, 'ep_num': ep_num,
            'generated': datetime.now().isoformat(),
            'af_id': COUPANG_AF_ID,
            'links': links,
        }, f, ensure_ascii=False, indent=2)

    # 설명란 텍스트 저장
    desc_path = out_dir / f'{ch_slug}_{ep_str}_{date_str}_description.txt'
    with open(desc_path, 'w', encoding='utf-8') as f:
        f.write(description)

    logger.info(f'저장 완료: {links_path.name} ({len(links)}개 링크)')
    return {'links_file': str(links_path), 'desc_file': str(desc_path)}


def run(ch_slug: str, ep_num: int, dry_run: bool = False) -> dict:
    """단일 EP 제휴링크 생성 실행."""
    logger.info(f'제휴링크 매핑 시작: {ch_slug} EP{ep_num:02d} (AF: {COUPANG_AF_ID})')

    if dry_run:
        keywords = CHANNEL_CATEGORY_MAP.get(ch_slug, ['테스트'])[:3]
        links = [{'keyword': kw, 'productName': f'{kw} 추천상품',
                  'productUrl': f'https://www.coupang.com/np/search?q={quote(kw)}&subId={COUPANG_AF_ID}',
                  'price': 0, 'af_id': COUPANG_AF_ID, 'api_used': False}
                 for kw in keywords]
        logger.info(f'[dry-run] 키워드: {keywords}')
    else:
        links = generate_affiliate_links(ch_slug, ep_num)

    description = build_youtube_description(ch_slug, ep_num, links)
    saved       = save_links(ch_slug, ep_num, links, description)

    logger.info(f'생성된 링크 수: {len(links)}개')
    print('\n[YouTube 설명란 미리보기]')
    print('-' * 40)
    print(description[:500] + ('...' if len(description) > 500 else ''))

    return {'links': len(links), 'saved': saved}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='GAONIX 쿠팡파트너스 제휴링크 자동 매핑')
    parser.add_argument('--ch', required=True, help='채널 슬러그 또는 all')
    parser.add_argument('--ep', type=int, required=True, help='에피소드 번호')
    parser.add_argument('--dry-run', action='store_true',
                        help='API 호출 없이 구조 테스트')
    args = parser.parse_args()

    slugs = list(CHANNEL_SLUGS.values()) if args.ch == 'all' else [args.ch]

    for slug in slugs:
        result = run(slug, args.ep, args.dry_run)
        print(f'\n[{slug}] EP{args.ep:02d}: 링크 {result["links"]}개 생성')

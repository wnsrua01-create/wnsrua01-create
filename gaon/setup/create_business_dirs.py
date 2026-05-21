#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명: create_business_dirs.py
목적: D:\1인기업\ GAONIX 사업 폴더 구조 자동 생성
작성일: 2026-05-21
설치 위치(Windows): C:\gaon\setup\create_business_dirs.py
실행: D:\programs\python.exe C:\gaon\setup\create_business_dirs.py
"""
import sys
import os

os.environ.setdefault('PYTHONUTF8', '1')

if sys.platform == 'win32':
    import ctypes
    try:
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass

import json
from pathlib import Path

# ── 생성할 폴더 목록 ────────────────────────────────────────────────────────
BASE = Path('D:/1인기업')

DIRS = [
    # 브랜드
    'GAONIX/brand/logo',
    'GAONIX/brand/fonts',
    'GAONIX/docs',

    # 유튜브
    '01_youtube/channels',
    '01_youtube/analytics/weekly_reports',
    '01_youtube/analytics/ab_test_results',
    '01_youtube/uploads_queue',

    # Shorts
    '02_shorts/clips',
    '02_shorts/shorts_queue',
    '02_shorts/scripts',

    # 뉴스레터
    '03_newsletter/templates',
    '03_newsletter/subscribers',
    '03_newsletter/sent',
    '03_newsletter/scripts',

    # 전자책
    '04_ebooks/drafts',
    '04_ebooks/published',
    '04_ebooks/covers',
    '04_ebooks/sales_data',
    '04_ebooks/scripts',

    # 스마트스토어
    '05_smartstore/products',
    '05_smartstore/descriptions',
    '05_smartstore/images',
    '05_smartstore/scripts',

    # 블로그
    '06_blog/naver',
    '06_blog/tistory',
    '06_blog/wordpress',
    '06_blog/scripts',

    # 제휴마케팅
    '07_affiliate/coupang/links',
    '07_affiliate/coupang/reports',
    '07_affiliate/scripts',

    # 컨설팅 (미래)
    '08_consulting/courses',
    '08_consulting/clients',

    # 공용 도구
    '09_tools',

    # 재무
    '10_finance/income',
    '10_finance/expenses',
    '10_finance/monthly_reports',

    # 법무
    '11_legal/business_registration',
    '11_legal/trademark',
    '11_legal/contracts',

    # 기타
    '_archive',
    '_temp',
]

# ── README 내용 매핑 ────────────────────────────────────────────────────────
README_CONTENTS: dict[str, str] = {
    'GAONIX':          'GAONIX 브랜드 에셋 (로고, 컬러, 폰트, 사업 문서)',
    '01_youtube':      'YouTube 17채널 관리, 분석, 업로드 큐',
    '02_shorts':       'YouTube Shorts 자동 생성 파이프라인 (롱폼→60초 변환)',
    '03_newsletter':   '뉴스레터 자동 생성 및 Stibee/Mailchimp 발송',
    '04_ebooks':       '배치 10편 대본 기반 전자책 자동 생성 및 판매',
    '05_smartstore':   '스마트스토어 상품설명 자동 생성',
    '06_blog':         '네이버/티스토리/워드프레스 SEO 자동 포스팅',
    '07_affiliate':    '쿠팡파트너스 AF7354598 제휴링크 자동 매핑',
    '08_consulting':   '컨설팅 및 강의 사업 (미래 확장용)',
    '09_tools':        '공용 유틸리티 (path_utils.py, gemini_client.py 등)',
    '10_finance':      '수입/지출 기록, 월별 손익 리포트',
    '11_legal':        '사업자등록, 상표(GAONIX), 계약서 보관',
    '_archive':        '구버전 파일 보관',
    '_temp':           '임시 파일 (주기적 정리)',
}

# ── 브랜드 컬러 팔레트 ────────────────────────────────────────────────────
BRAND_COLORS = {
    "brand": "GAONIX",
    "palette": {
        "primary":   "#FF4500",   # 강렬한 오렌지-레드 (메인 CTA)
        "secondary": "#1A1A2E",   # 딥 네이비 (배경)
        "accent":    "#E8C547",   # 골드 옐로우 (강조 텍스트)
        "neutral":   "#F5F5F5",   # 라이트 그레이 (본문)
    },
    "fonts": {
        "primary":   "Noto Sans KR",
        "display":   "Pretendard",
        "fallback":  "맑은 고딕",
    },
    "slogan_kr":  "AI가 일하고, 당신이 쉰다",
    "slogan_en":  "One person. Infinite content.",
    "coupang_af": "AF7354598",
}


def create_dirs() -> None:
    print("=" * 50)
    print("GAONIX 1인기업 폴더 구조 생성")
    print(f"대상 루트: {BASE}")
    print("=" * 50)

    created, skipped = 0, 0

    for d in DIRS:
        full = BASE / d
        if full.exists():
            print(f"  (기존) {full}")
            skipped += 1
        else:
            full.mkdir(parents=True, exist_ok=True)
            print(f"  ✅ 생성: {full}")
            created += 1

    print(f"\n폴더 생성: {created}개 / 기존: {skipped}개")


def create_readmes() -> None:
    print("\n[README.md 생성]")
    for folder, desc in README_CONTENTS.items():
        p = BASE / folder / 'README.md'
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"# {folder}\n\n{desc}\n", encoding='utf-8')
            print(f"  ✅ {p}")

    # 루트 README
    root_readme = BASE / 'README.md'
    sections = '\n'.join(
        f'- **{k}/** : {v}' for k, v in README_CONTENTS.items()
    )
    root_readme.write_text(
        f"""# GAONIX 1인기업 운영 폴더

## 브랜드
- 이름: **GAONIX** (GAON NEXUS → GAONIX 리브랜딩)
- 슬로건: AI가 일하고, 당신이 쉰다
- 기반: GAON NEXUS 17채널 유튜브 자동화 시스템

## 폴더 구조
{sections}

## 핵심 원칙
- 모든 경로는 영문 슬러그 사용 (한글은 JSON 메타데이터에만 보관)
- GAON NEXUS 데이터와 심볼릭 링크로 연결 (파일 복사 없음)
- 09_tools/path_utils.py 반드시 임포트 후 사용

## 수익원 목표 (월)
| 수익원 | 목표 |
|-------|------|
| YouTube AdSense (17채널) | ₩85~510만 |
| YouTube Shorts 보너스 | ₩17~85만 |
| 뉴스레터 | ₩50~200만 |
| 전자책 | ₩30~150만 |
| 쿠팡파트너스 | ₩50~200만 |
| 블로그 애드센스 | ₩20~100만 |
| **합계** | **₩252~1,245만** |
""",
        encoding='utf-8',
    )
    print(f"  ✅ {root_readme}")


def create_brand_files() -> None:
    print("\n[브랜드 파일 생성]")

    colors_path = BASE / 'GAONIX' / 'brand' / 'colors.json'
    if not colors_path.exists():
        with open(colors_path, 'w', encoding='utf-8') as f:
            json.dump(BRAND_COLORS, f, ensure_ascii=False, indent=2)
        print(f"  ✅ {colors_path}")

    business_plan = BASE / 'GAONIX' / 'docs' / 'business_plan.md'
    if not business_plan.exists():
        business_plan.write_text(
            """# GAONIX 사업 계획서

## 사업 개요
- 업종: 1인미디어콘텐츠창작자 (940306) / AI서비스 (921505)
- 브랜드: GAONIX
- 기술 기반: GAON NEXUS 7-에이전트 AI 자동화 파이프라인

## 채널 운영 목표
- 현재: 17채널 운영 중
- 목표: 30채널 확장 (2026 Q4)
- 일 생산: 17편/일 → 6,205편/년

## Phase 별 수익화
- Phase 3 (7-9월): YouTube 수익화 신청 (1,000구독자 × 17채널)
- Phase 3 (7-9월): 쿠팡파트너스 자동 링크 삽입
- Phase 3 (7-9월): 멀티언어(영/일) 파이프라인

## 상표 등록
- 상표명: GAONIX
- 분류: 제41류(교육/영상), 제42류(AI서비스)
""",
            encoding='utf-8',
        )
        print(f"  ✅ {business_plan}")


def copy_path_utils() -> None:
    """path_utils.py를 09_tools에 복사."""
    src = Path('C:/gaon/utils/path_utils.py')
    dst = BASE / '09_tools' / 'path_utils.py'
    if src.exists() and not dst.exists():
        import shutil
        shutil.copy2(src, dst)
        print(f"  ✅ path_utils.py → {dst}")
    elif not src.exists():
        print(f"  ⚠️  {src} 없음 — P0-A 완료 후 다시 실행하세요")


def create_channel_dirs() -> None:
    """01_youtube/channels/ 하위 17개 채널 폴더 생성."""
    channels = {
        'ch01': 'senior',  'ch02': 'finance', 'ch03': 'health',
        'ch04': 'pension', 'ch05': 'psych',   'ch06': 'realty',
        'ch07': 'parent',  'ch08': 'cooking', 'ch09': 'aitech',
        'ch10': 'travel',  'ch11': 'beauty',  'ch12': 'growth',
        'ch13': 'history', 'ch14': 'pets',    'ch15': 'home',
        'ch16': 'midlife', 'ch17': 'money',
    }
    base = BASE / '01_youtube' / 'channels'
    for chid, slug in channels.items():
        d = base / f'{chid}_{slug}'
        d.mkdir(parents=True, exist_ok=True)
    print(f"  ✅ 17개 채널 폴더 생성 완료")


if __name__ == '__main__':
    create_dirs()
    create_readmes()
    create_brand_files()
    create_channel_dirs()

    print("\n[09_tools path_utils.py 복사]")
    copy_path_utils()

    print("\n" + "=" * 50)
    print("✅ D:\\1인기업\\ 폴더 구조 생성 완료")
    print("=" * 50)
    print("\n다음 단계:")
    print("  1. gaon_link_setup.bat 실행 (관리자 권한) → 심볼릭 링크 생성")
    print("  2. GAONIX 도메인 확인: gaonix.com / gaonix.co.kr")
    print("  3. 07_affiliate/coupang/ → 쿠팡파트너스 API 승인 후 연동")

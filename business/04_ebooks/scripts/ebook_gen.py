#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명: ebook_gen.py
목적: 배치 10편 대본 JSON → PDF 전자책 자동 생성 (reportlab)
작성일: 2026-05-21
설치 위치(Windows): D:/1인기업/04_ebooks/scripts/ebook_gen.py

의존성: pip install reportlab
한글 폰트: C:/Windows/Fonts/malgunbd.ttf (맑은 고딕 Bold)
"""
import sys
import os
import json
import logging
from pathlib import Path
from datetime import datetime

os.environ.setdefault('PYTHONUTF8', '1')

if sys.platform == 'win32':
    import ctypes
    try:
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False
    print("reportlab 미설치. pip install reportlab 실행 후 재시도.")

# ── 경로 상수 ────────────────────────────────────────────────────────────────
ROOT_SCRIPTS  = Path('D:/gaon_data/scripts')
ROOT_EBOOKS   = Path('D:/1인기업/04_ebooks')
FONT_PATH     = Path('C:/Windows/Fonts/malgunbd.ttf')
FONT_FALLBACK = Path('C:/Windows/Fonts/malgun.ttf')

# ── 브랜드 컬러 ────────────────────────────────────────────────────────────
COLOR_PRIMARY   = HexColor('#FF4500') if REPORTLAB_OK else None
COLOR_SECONDARY = HexColor('#1A1A2E') if REPORTLAB_OK else None
COLOR_ACCENT    = HexColor('#E8C547') if REPORTLAB_OK else None
COLOR_LIGHT     = HexColor('#F5F5F5') if REPORTLAB_OK else None

# ── 채널 슬러그 매핑 ─────────────────────────────────────────────────────────
CHANNEL_SLUGS = {
    'ch01': 'senior',  'ch02': 'finance', 'ch03': 'health',
    'ch04': 'pension', 'ch05': 'psych',   'ch06': 'realty',
    'ch07': 'parent',  'ch08': 'cooking', 'ch09': 'aitech',
    'ch10': 'travel',  'ch11': 'beauty',  'ch12': 'growth',
    'ch13': 'history', 'ch14': 'pets',    'ch15': 'home',
    'ch16': 'midlife', 'ch17': 'money',
}

# 로깅
LOG_DIR = Path('C:/gaon/logs')
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'ebook_gen.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def _register_font() -> str:
    """한글 폰트 등록. 반환값: 등록된 폰트 이름."""
    font_name = 'MalgunGothic'
    for fp in [FONT_PATH, FONT_FALLBACK]:
        if fp.exists():
            try:
                pdfmetrics.registerFont(TTFont(font_name, str(fp)))
                logger.info(f"폰트 등록: {fp}")
                return font_name
            except Exception as e:
                logger.warning(f"폰트 등록 실패 ({fp}): {e}")
    logger.warning("맑은 고딕 없음 — 기본 폰트 사용 (한글 깨질 수 있음)")
    return 'Helvetica'


def _load_ep_data(ch_slug: str, ep_num: int) -> dict:
    """에피소드 데이터 JSON 로드."""
    ch_num = next((k for k, v in CHANNEL_SLUGS.items() if v == ch_slug), 'ch01')
    num = int(ch_num[2:])
    ep_str = f'ep{ep_num:02d}'
    ep_dir = ROOT_SCRIPTS / f'ch{num:02d}_{ch_slug}' / ep_str

    candidates = [
        ep_dir / f'{ep_str}_data.json',
        ep_dir / 'data.json',
        ep_dir / f'{ep_str}.json',
    ]
    for p in candidates:
        if p.exists():
            with open(p, 'r', encoding='utf-8') as f:
                return json.load(f)

    logger.warning(f"데이터 파일 없음: {ep_dir}")
    return {}


def _extract_scenes(ep_data: dict, scene_range: tuple[int, int]) -> list[str]:
    """씬 범위의 대사 추출."""
    scenes = ep_data.get('scenes', [])
    result = []
    for sc in scenes:
        sc_num = sc.get('scene_num', 0) or sc.get('num', 0)
        if scene_range[0] <= sc_num <= scene_range[1]:
            text = sc.get('narration', '') or sc.get('text', '') or sc.get('dialogue', '')
            if text:
                result.append(text.strip())
    return result


def _build_checklist(texts: list[str]) -> list[str]:
    """outro 대사를 실천 체크리스트로 변환."""
    items = []
    for t in texts:
        sentences = [s.strip() for s in t.replace('。', '.').split('.') if s.strip()]
        items.extend(sentences[:2])
    return [f'☐ {item}' for item in items[:10]]


def generate_ebook(ch_slug: str, batch_start: int = 1,
                   batch_size: int = 10) -> Path:
    """
    배치 에피소드 → PDF 전자책 생성.

    Args:
        ch_slug:     채널 슬러그 (예: 'senior')
        batch_start: 시작 에피소드 번호
        batch_size:  배치 크기 (기본 10)

    Returns:
        생성된 PDF Path
    """
    if not REPORTLAB_OK:
        raise ImportError("reportlab 미설치")

    ch_num = next((k for k, v in CHANNEL_SLUGS.items() if v == ch_slug), 'ch01')
    num = int(ch_num[2:])
    batch_num = (batch_start - 1) // batch_size + 1

    out_dir = ROOT_EBOOKS / 'published'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f'ch{num:02d}_{ch_slug}_batch{batch_num:02d}_ebook.pdf'

    font_name = _register_font()
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=20*mm,
        rightMargin=20*mm,
        topMargin=25*mm,
        bottomMargin=20*mm,
    )

    styles = getSampleStyleSheet()
    style_title   = ParagraphStyle('title',   fontName=font_name, fontSize=28, leading=36,
                                   textColor=COLOR_PRIMARY,   spaceAfter=8*mm, alignment=1)
    style_subtitle = ParagraphStyle('subtitle', fontName=font_name, fontSize=14, leading=20,
                                    textColor=COLOR_SECONDARY, spaceAfter=4*mm, alignment=1)
    style_h1      = ParagraphStyle('h1',      fontName=font_name, fontSize=18, leading=24,
                                   textColor=COLOR_PRIMARY,   spaceBefore=8*mm, spaceAfter=4*mm)
    style_h2      = ParagraphStyle('h2',      fontName=font_name, fontSize=13, leading=18,
                                   textColor=COLOR_SECONDARY, spaceBefore=4*mm, spaceAfter=2*mm)
    style_body    = ParagraphStyle('body',    fontName=font_name, fontSize=10, leading=16,
                                   spaceAfter=2*mm)
    style_check   = ParagraphStyle('check',  fontName=font_name, fontSize=10, leading=18,
                                   leftIndent=10, spaceAfter=1*mm)
    style_cta     = ParagraphStyle('cta',    fontName=font_name, fontSize=11, leading=18,
                                   textColor=COLOR_PRIMARY,   alignment=1, spaceBefore=8*mm)

    story = []

    # ── 표지 ──────────────────────────────────────────────────────────────
    story.append(Spacer(1, 40*mm))
    story.append(Paragraph(f'GAONIX × {ch_slug.upper()}', style_subtitle))
    story.append(Paragraph(f'시리즈 {batch_num}권', style_title))
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph(f'EP{batch_start:02d} ~ EP{batch_start + batch_size - 1:02d}', style_subtitle))
    story.append(Spacer(1, 20*mm))
    story.append(Paragraph(f'GAONIX · {datetime.now().strftime("%Y년 %m월")}', style_subtitle))
    story.append(PageBreak())

    # ── 목차 ──────────────────────────────────────────────────────────────
    story.append(Paragraph('목 차', style_h1))
    for ep in range(batch_start, batch_start + batch_size):
        ep_data = _load_ep_data(ch_slug, ep)
        title = ep_data.get('title', f'EP{ep:02d}')
        story.append(Paragraph(f'제{ep - batch_start + 1}장 · {title}', style_body))
    story.append(PageBreak())

    # ── 각 에피소드 챕터 ──────────────────────────────────────────────────
    for ep in range(batch_start, batch_start + batch_size):
        ep_data = _load_ep_data(ch_slug, ep)
        if not ep_data:
            ep_data = {'title': f'EP{ep:02d}', 'scenes': []}

        title = ep_data.get('title', f'EP{ep:02d}')
        story.append(Paragraph(f'제{ep - batch_start + 1}장', style_h2))
        story.append(Paragraph(title, style_h1))

        # 핵심 요약 (씬 1-13)
        summary_texts = _extract_scenes(ep_data, (1, 13))
        if summary_texts:
            story.append(Paragraph('핵심 요약', style_h2))
            story.append(Paragraph(' '.join(summary_texts[:3]), style_body))

        # 본문 (씬 14-117)
        body_texts = _extract_scenes(ep_data, (14, 117))
        if body_texts:
            story.append(Paragraph('본 문', style_h2))
            for chunk in body_texts[:8]:
                story.append(Paragraph(chunk, style_body))

        # 실천 체크리스트 (씬 118-130)
        outro_texts = _extract_scenes(ep_data, (118, 130))
        checklist = _build_checklist(outro_texts) if outro_texts else [
            '☐ 오늘 배운 내용 하나를 바로 적용해 보세요',
            '☐ 주변 한 사람과 핵심 내용을 공유하세요',
            '☐ 다음 에피소드에서 더 깊은 내용을 만나보세요',
        ]
        story.append(Paragraph('실천 체크리스트', style_h2))
        for item in checklist:
            story.append(Paragraph(item, style_check))

        story.append(PageBreak())

    # ── 후기 / CTA ─────────────────────────────────────────────────────────
    story.append(Spacer(1, 30*mm))
    story.append(Paragraph('AI가 일하고, 당신이 쉰다', style_cta))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph('— GAONIX', style_cta))
    story.append(Spacer(1, 15*mm))
    story.append(Paragraph(
        f'다음 시리즈도 기대해 주세요.<br/>'
        f'YouTube · 뉴스레터 · 전자책으로 계속 만나겠습니다.',
        style_body
    ))

    doc.build(story)
    logger.info(f'✅ 전자책 생성 완료: {out_path}')
    return out_path


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='GAONIX 전자책 자동 생성기')
    parser.add_argument('--ch', required=True, help='채널 슬러그 (예: senior)')
    parser.add_argument('--batch-start', type=int, default=1, help='시작 에피소드 번호')
    parser.add_argument('--batch-size', type=int, default=10, help='배치 크기 (기본 10)')
    args = parser.parse_args()

    if not REPORTLAB_OK:
        print("reportlab 미설치. pip install reportlab")
        sys.exit(1)

    out = generate_ebook(args.ch, args.batch_start, args.batch_size)
    print(f'생성 완료: {out}')

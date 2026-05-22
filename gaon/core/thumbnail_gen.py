#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명: thumbnail_gen.py
목적: 채널 브랜드 컬러 + 제목 텍스트 썸네일 자동 생성
작성일: 2026-05-22
설치 위치(Windows): C:/gaon/core/thumbnail_gen.py

우선순위:
  1. ComfyUI API (localhost:8188) — AI 이미지 생성
  2. Pillow 텍스트 오버레이 폴백 — 항상 동작 보장

사전 설치:
  pip install Pillow

사용법:
  python thumbnail_gen.py --ch senior --ep 1
  python thumbnail_gen.py --ch senior --ep 1 --mode pillow
  python thumbnail_gen.py --ch all --ep 1
"""
import sys
import os
import json
import logging
import argparse
import textwrap
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

ROOT_SCRIPTS = Path('D:/gaon_data/scripts')
ROOT_THUMBS  = Path('D:/gaon_data/thumbs')
CONFIG_PATH  = Path('C:/gaon/config/channels.json')
FONT_PATH    = Path('C:/Windows/Fonts/malgunbd.ttf')  # 맑은고딕 Bold
LOG_DIR      = Path('C:/gaon/logs')
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'thumbnail_gen.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

THUMB_W, THUMB_H = 1280, 720  # YouTube 권장 썸네일 크기

CHANNEL_SLUGS = {
    'ch01': 'senior',  'ch02': 'finance', 'ch03': 'health',
    'ch04': 'pension', 'ch05': 'psych',   'ch06': 'realty',
    'ch07': 'parent',  'ch08': 'cooking', 'ch09': 'aitech',
    'ch10': 'travel',  'ch11': 'beauty',  'ch12': 'growth',
    'ch13': 'history', 'ch14': 'pets',    'ch15': 'home',
    'ch16': 'midlife', 'ch17': 'money',
}

# 채널 기본 색상 (channels.json의 color_theme 값과 동일)
CHANNEL_COLORS = {
    'senior':  ('#8B7355', '#F5E6D3'),
    'finance': ('#1A3A5C', '#E8F4F8'),
    'health':  ('#2E7D32', '#E8F5E9'),
    'pension': ('#1565C0', '#E3F2FD'),
    'psych':   ('#6A1B9A', '#F3E5F5'),
    'realty':  ('#E65100', '#FFF3E0'),
    'parent':  ('#F06292', '#FCE4EC'),
    'cooking': ('#FF6F00', '#FFF8E1'),
    'aitech':  ('#0D47A1', '#E8EAF6'),
    'travel':  ('#00695C', '#E0F2F1'),
    'beauty':  ('#AD1457', '#FCE4EC'),
    'growth':  ('#558B2F', '#F1F8E9'),
    'history': ('#4E342E', '#EFEBE9'),
    'pets':    ('#6D4C41', '#EFEBE9'),
    'home':    ('#37474F', '#ECEFF1'),
    'midlife': ('#7B1FA2', '#F3E5F5'),
    'money':   ('#1B5E20', '#E8F5E9'),
}


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
    except json.JSONDecodeError:
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
            except json.JSONDecodeError:
                pass
    return {}


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _generate_pillow(ch_slug: str, ep_num: int,
                      title: str, ch_cfg: dict) -> Optional[Path]:
    """Pillow로 브랜드 컬러 썸네일 생성."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.error('Pillow 미설치. pip install Pillow')
        return None

    bg_hex, fg_hex = CHANNEL_COLORS.get(ch_slug, ('#1A1A2E', '#EAEAEA'))
    bg_rgb = _hex_to_rgb(ch_cfg.get('color_theme', bg_hex).lstrip('#') and
                          ch_cfg.get('color_theme', bg_hex) or bg_hex)
    text_rgb = _hex_to_rgb('FFFFFF')
    accent_rgb = _hex_to_rgb(bg_hex)

    img  = Image.new('RGB', (THUMB_W, THUMB_H), bg_rgb)
    draw = ImageDraw.Draw(img)

    # 그라디언트 효과 (하단 어둡게)
    for y in range(THUMB_H):
        alpha = int(80 * (y / THUMB_H))
        overlay_color = tuple(max(0, c - alpha) for c in bg_rgb)
        draw.line([(0, y), (THUMB_W, y)], fill=overlay_color)

    # 채널명 레이블 (상단)
    name_kr = ch_cfg.get('name_kr', ch_slug)
    ep_str  = f'EP {ep_num:02d}'

    def _load_font(size: int):
        for font_path in [FONT_PATH,
                           Path('C:/Windows/Fonts/malgun.ttf'),
                           Path('/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf'),
                           Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')]:
            if font_path.exists():
                try:
                    return ImageFont.truetype(str(font_path), size)
                except Exception:
                    pass
        return ImageFont.load_default()

    font_label   = _load_font(36)
    font_title   = _load_font(72)
    font_ep      = _load_font(48)

    # 상단 채널명 + EP 번호
    draw.rectangle([(0, 0), (THUMB_W, 80)],
                   fill=tuple(max(0, c - 30) for c in bg_rgb))
    draw.text((40, 20), name_kr, font=font_label, fill=text_rgb)
    draw.text((THUMB_W - 160, 20), ep_str, font=font_ep, fill=text_rgb)

    # 제목 텍스트 (중앙)
    lines   = textwrap.wrap(title, width=18)[:3]
    y_start = (THUMB_H - len(lines) * 90) // 2
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_title)
        w    = bbox[2] - bbox[0]
        x    = (THUMB_W - w) // 2
        # 그림자 효과
        draw.text((x + 3, y_start + i * 90 + 3), line,
                  font=font_title, fill=(0, 0, 0, 128))
        draw.text((x, y_start + i * 90), line, font=font_title, fill=text_rgb)

    # 하단 GAONIX 브랜딩
    draw.rectangle([(0, THUMB_H - 60), (THUMB_W, THUMB_H)],
                   fill=tuple(max(0, c - 40) for c in bg_rgb))
    draw.text((40, THUMB_H - 48), 'GAONIX', font=font_label, fill=text_rgb)

    # 저장
    ch_num  = next((k for k, v in CHANNEL_SLUGS.items() if v == ch_slug), 'ch01')
    out_dir = ROOT_THUMBS / f'ch{int(ch_num[2:]):02d}_{ch_slug}'
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f'ep{ep_num:02d}_thumb.png'

    # 기존 파일 백업 (규칙 8)
    if out.exists():
        import shutil
        shutil.copy2(out, out.with_suffix('.png.bak'))

    img.save(str(out), 'PNG', optimize=True)
    logger.info(f'썸네일 생성 완료 (Pillow): {out}')
    return out


def _generate_comfyui(ch_slug: str, ep_num: int, title: str,
                       visual_prompt: str = '') -> Optional[Path]:
    """ComfyUI API로 AI 썸네일 생성."""
    import urllib.request

    comfy_url = 'http://localhost:8188'

    # ComfyUI 연결 확인
    try:
        with urllib.request.urlopen(f'{comfy_url}/system_stats', timeout=3):
            pass
    except Exception:
        logger.info('ComfyUI 오프라인 — Pillow 폴백')
        return None

    # 썸네일용 프롬프트
    ch_num  = next((k for k, v in CHANNEL_SLUGS.items() if v == ch_slug), 'ch01')
    bg_color = CHANNEL_COLORS.get(ch_slug, ('#1A1A2E', '#EAEAEA'))[0]
    prompt_text = (
        f'{visual_prompt}, youtube thumbnail, high quality, '
        f'professional photography, {ch_slug} theme, '
        f'vibrant colors, sharp focus, 16:9 aspect ratio'
    )

    # ComfyUI API 워크플로 (txt2img 기본 워크플로)
    workflow = {
        '6':  {'inputs': {'text': prompt_text, 'clip': ['4', 1]}, 'class_type': 'CLIPTextEncode'},
        '7':  {'inputs': {'text': 'blurry, low quality, watermark, text overlay', 'clip': ['4', 1]}, 'class_type': 'CLIPTextEncode'},
        '4':  {'inputs': {'ckpt_name': 'v1-5-pruned-emaonly.ckpt'}, 'class_type': 'CheckpointLoaderSimple'},
        '5':  {'inputs': {'width': 1280, 'height': 720, 'batch_size': 1}, 'class_type': 'EmptyLatentImage'},
        '3':  {'inputs': {'seed': ep_num * 1000 + 1, 'steps': 20, 'cfg': 7, 'sampler_name': 'euler',
                          'scheduler': 'normal', 'denoise': 1,
                          'model': ['4', 0], 'positive': ['6', 0], 'negative': ['7', 0],
                          'latent_image': ['5', 0]}, 'class_type': 'KSampler'},
        '8':  {'inputs': {'samples': ['3', 0], 'vae': ['4', 2]}, 'class_type': 'VAEDecode'},
        '9':  {'inputs': {'filename_prefix': f'thumb_{ch_slug}_ep{ep_num:02d}',
                          'images': ['8', 0]}, 'class_type': 'SaveImage'},
    }

    try:
        payload = json.dumps({'prompt': workflow}).encode('utf-8')
        req = urllib.request.Request(
            f'{comfy_url}/prompt',
            data=payload,
            headers={'Content-Type': 'application/json'},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            prompt_id = result.get('prompt_id', '')

        if not prompt_id:
            return None

        # 완료 대기 (최대 120s)
        import time
        for _ in range(60):
            time.sleep(2)
            with urllib.request.urlopen(f'{comfy_url}/history/{prompt_id}', timeout=5) as resp:
                history = json.loads(resp.read())
            if prompt_id in history:
                outputs = history[prompt_id].get('outputs', {})
                for node_output in outputs.values():
                    for img_info in node_output.get('images', []):
                        fname    = img_info['filename']
                        subfolder = img_info.get('subfolder', '')
                        type_    = img_info.get('type', 'output')
                        img_url  = f'{comfy_url}/view?filename={fname}&subfolder={subfolder}&type={type_}'
                        ch_dir   = ROOT_THUMBS / f'ch{int(ch_num[2:]):02d}_{ch_slug}'
                        ch_dir.mkdir(parents=True, exist_ok=True)
                        out = ch_dir / f'ep{ep_num:02d}_thumb.png'
                        with urllib.request.urlopen(img_url, timeout=30) as img_resp:
                            out.write_bytes(img_resp.read())
                        logger.info(f'썸네일 생성 완료 (ComfyUI): {out}')
                        return out

        logger.warning('ComfyUI 타임아웃')
        return None

    except Exception as e:
        logger.warning(f'ComfyUI 오류: {type(e).__name__} — Pillow 폴백')
        return None


def generate_thumbnail(ch_slug: str, ep_num: int,
                        mode: str = 'auto') -> Optional[Path]:
    """
    썸네일 생성 진입점.
    mode: 'auto' | 'comfyui' | 'pillow'
    """
    ch_cfg  = _load_channel_config(ch_slug)
    ep_data = _load_ep_data(ch_slug, ep_num)
    title   = ep_data.get('title', f'{ch_cfg.get("name_kr", ch_slug)} EP{ep_num:02d}')
    scenes  = ep_data.get('scenes', [])
    visual_prompt = next(
        (s.get('visual_prompt', '') for s in scenes if s.get('scene_num') == 1), ''
    )

    logger.info(f'썸네일 생성: {ch_slug} EP{ep_num:02d} — "{title}"')

    if mode in ('auto', 'comfyui'):
        result = _generate_comfyui(ch_slug, ep_num, title, visual_prompt)
        if result:
            return result
        if mode == 'comfyui':
            return None

    return _generate_pillow(ch_slug, ep_num, title, ch_cfg)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='GAONIX 썸네일 자동 생성')
    parser.add_argument('--ch', required=True, help='채널 슬러그 또는 all')
    parser.add_argument('--ep', type=int, required=True, help='에피소드 번호')
    parser.add_argument('--mode', default='auto',
                        choices=['auto', 'comfyui', 'pillow'],
                        help='생성 모드 (기본: auto)')
    args = parser.parse_args()

    valid_slugs = set(CHANNEL_SLUGS.values())
    if args.ch == 'all':
        slugs = sorted(valid_slugs)
    elif args.ch in valid_slugs:
        slugs = [args.ch]
    else:
        parser.error(f'알 수 없는 채널: {args.ch!r}')

    if not (1 <= args.ep <= 9999):
        parser.error(f'EP 범위 오류: {args.ep}')

    for slug in slugs:
        out = generate_thumbnail(slug, args.ep, args.mode)
        print(f'{"✅" if out else "❌"} [{slug}] EP{args.ep:02d}: {out or "실패"}')

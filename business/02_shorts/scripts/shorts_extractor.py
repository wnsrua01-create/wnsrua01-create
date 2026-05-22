#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명: shorts_extractor.py
목적: 롱폼 EP(130씬 × 6초 = 780초)에서 YouTube Shorts 3개 자동 추출
작성일: 2026-05-21
설치 위치(Windows): D:\1인기업\02_shorts\scripts\shorts_extractor.py

Shorts 추출 규칙:
  Shorts #1: 씬 1-13  (intro_hook 78초)  → 60초 트리밍 + 9:16 변환
  Shorts #2: 씬 67-90 (실패회피 138초)  → 베스트 60초 추출
  Shorts #3: 씬 118-130 (outro 78초)    → 60초 트리밍 + 9:16 변환

CLI 사용법:
  python shorts_extractor.py --ch senior --ep 1
  python shorts_extractor.py --ch senior --batch 1   (EP01-10 전체)
  python shorts_extractor.py --ch all --ep 1         (전 채널 EP01)
"""
import sys
import os
import argparse
import logging
import subprocess
from pathlib import Path

os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

if sys.platform == 'win32':
    import ctypes
    try:
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass

# ── 경로 상수 ────────────────────────────────────────────────────────────────
ROOT_FINALS = Path('D:/gaon_data/finals')
ROOT_SHORTS = Path('D:/1인기업/02_shorts/clips')

# 로그
LOG_DIR = Path('C:/gaon/logs')
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'shorts_extractor.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# 씬 1개 길이(초) — 롱폼 기준
SCENE_DURATION = 6.042

CHANNEL_SLUGS = {
    'ch01': 'senior',  'ch02': 'finance', 'ch03': 'health',
    'ch04': 'pension', 'ch05': 'psych',   'ch06': 'realty',
    'ch07': 'parent',  'ch08': 'cooking', 'ch09': 'aitech',
    'ch10': 'travel',  'ch11': 'beauty',  'ch12': 'growth',
    'ch13': 'history', 'ch14': 'pets',    'ch15': 'home',
    'ch16': 'midlife', 'ch17': 'money',
}
SLUG_TO_CHID = {v: k for k, v in CHANNEL_SLUGS.items()}

# Shorts 추출 규격
SHORTS_SPEC = [
    {
        'index':       1,
        'name':        'intro_hook',
        'start_scene': 1,
        'end_scene':   13,
        'duration':    60,     # 출력 길이(초)
        'description': '오픈루프 훅 — 비구독자 유입 최적화',
    },
    {
        'index':       2,
        'name':        'fail_avoid',
        'start_scene': 67,
        'end_scene':   90,
        'duration':    60,
        'description': '실패회피 감정 자극 — 중반부 하이라이트',
    },
    {
        'index':       3,
        'name':        'outro_cta',
        'start_scene': 118,
        'end_scene':   130,
        'duration':    60,
        'description': '성공비전 + CTA — 구독 전환 유도',
    },
]


def scene_to_seconds(scene_num: int) -> float:
    """씬 번호(1-indexed) → 영상 내 시작 시각(초)."""
    return (scene_num - 1) * SCENE_DURATION


def ffmpeg_extract_short(
    source_mp4: Path,
    output_mp4: Path,
    start_sec: float,
    duration: float,
) -> bool:
    """
    FFmpeg로 16:9 롱폼 → 9:16 Shorts 변환.

    가로 crop: (iw - ih*9/16)/2 만큼 양쪽 잘라내기
    세로 crop: 전체 높이 유지
    출력: 1080×1920
    """
    output_mp4.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        'ffmpeg', '-y',
        '-ss', f'{start_sec:.3f}',
        '-i', str(source_mp4),
        '-t', str(duration),
        '-vf', 'crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920',
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-movflags', '+faststart',
        str(output_mp4),
    ]

    logger.info(f"FFmpeg 실행: {output_mp4.name}")
    result = subprocess.run(
        cmd,
        capture_output=True,
        encoding='utf-8',
        errors='replace',
        env={**os.environ, 'PYTHONUTF8': '1'},
    )

    if result.returncode == 0:
        logger.info(f"✅ 완료: {output_mp4}")
        return True

    logger.error(f"FFmpeg 실패: {result.stderr[-500:]}")
    return False


def extract_shorts_for_episode(ch_slug: str, ep_num: int) -> dict:
    """
    단일 에피소드 → Shorts 3개 추출.

    Args:
        ch_slug: 채널 슬러그 (예: 'senior')
        ep_num:  에피소드 번호

    Returns:
        {'done': [1,2,3], 'failed': [...]}
    """
    chid = SLUG_TO_CHID.get(ch_slug, 'ch01')
    ch_num = int(chid[2:])
    ep_str = f'ep{ep_num:02d}'
    ch_dir = f'ch{ch_num:02d}_{ch_slug}'

    # 소스 롱폼 MP4 탐색 (ep01_final.mp4 또는 ep01.mp4)
    final_dir = ROOT_FINALS / ch_dir
    source_candidates = [
        final_dir / f'{ep_str}_final.mp4',
        final_dir / f'{ep_str}.mp4',
    ]
    source = next((p for p in source_candidates if p.exists()), None)

    if source is None:
        logger.error(f"롱폼 MP4 없음: {final_dir}/{ep_str}_final.mp4")
        return {'done': [], 'failed': [1, 2, 3]}

    out_dir = ROOT_SHORTS / ch_dir
    done, failed = [], []

    for spec in SHORTS_SPEC:
        start_sec = scene_to_seconds(spec['start_scene'])
        out_file = out_dir / f'{ep_str}_short{spec["index"]}_{spec["name"]}.mp4'

        if out_file.exists():
            logger.info(f"이미 존재: {out_file.name} — 건너뜀")
            done.append(spec['index'])
            continue

        ok = ffmpeg_extract_short(source, out_file, start_sec, spec['duration'])
        if ok:
            done.append(spec['index'])
        else:
            failed.append(spec['index'])

    return {'done': done, 'failed': failed}


def extract_batch(ch_slug: str, batch_start: int, batch_size: int = 10) -> None:
    """EP(batch_start) ~ EP(batch_start + batch_size - 1) 일괄 처리."""
    for ep in range(batch_start, batch_start + batch_size):
        logger.info(f"[{ch_slug}] EP{ep:02d} Shorts 추출 시작")
        result = extract_shorts_for_episode(ch_slug, ep)
        logger.info(f"  → 성공: {result['done']}, 실패: {result['failed']}")


# ── CLI 진입점 ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description='GAON NEXUS — YouTube Shorts 자동 추출기')
    parser.add_argument('--ch', required=True,
                        help='채널 슬러그 (예: senior) 또는 "all"')
    parser.add_argument('--ep', type=int, default=None,
                        help='단일 에피소드 번호 (예: 1)')
    parser.add_argument('--batch', type=int, default=None,
                        help='배치 시작 에피소드 번호 (10편 처리)')
    args = parser.parse_args()

    slugs = list(CHANNEL_SLUGS.values()) if args.ch == 'all' else [args.ch]

    for slug in slugs:
        if args.ep is not None:
            logger.info(f"[{slug}] EP{args.ep:02d} 단일 추출")
            result = extract_shorts_for_episode(slug, args.ep)
            print(f"  [{slug} EP{args.ep:02d}] 완료: {result['done']}, 실패: {result['failed']}")

        elif args.batch is not None:
            logger.info(f"[{slug}] EP{args.batch:02d}~EP{args.batch+9:02d} 배치 추출")
            extract_batch(slug, args.batch)

        else:
            parser.error("--ep 또는 --batch 중 하나를 지정하세요.")


if __name__ == '__main__':
    main()

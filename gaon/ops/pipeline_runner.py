#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명: pipeline_runner.py
목적: GAON NEXUS 전체 파이프라인 오케스트레이터
작성일: 2026-05-22
설치 위치(Windows): C:/gaon/ops/pipeline_runner.py

파이프라인 순서:
  1. script_gen      — 130씬 대본 생성 (LLM 3단계 폴백)
  2. thumbnail_gen   — 썸네일 생성 (ComfyUI / Pillow)
  3. wangp / kling   — I2V 영상 생성 (WanGP → Kling 폴백)
  4. youtube_upload  — YouTube 업로드
  5. blog_poster     — 블로그 자동 포스팅
  6. newsletter_gen  — 뉴스레터 발송
  7. affiliate       — 쿠팡 제휴링크 생성

사용법:
  python pipeline_runner.py --ch senior --ep 1
  python pipeline_runner.py --ch senior --ep 1 --from-stage 4   (4단계부터 재개)
  python pipeline_runner.py --ch senior --ep 1 --skip 3,4       (3,4단계 건너뜀)
  python pipeline_runner.py --ch senior --ep 1 --dry-run
  python pipeline_runner.py --ch all --ep 1 --stages 1,2        (대본+썸네일만)
"""
import sys
import os
import json
import time
import logging
import argparse
import subprocess
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

CODE_ROOT = Path('C:/gaon')
LOG_DIR   = Path('C:/gaon/logs')
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'pipeline_runner.log', encoding='utf-8'),
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

# 파이프라인 스테이지 정의
STAGES = {
    1: {
        'name':   '대본 생성',
        'script': CODE_ROOT / 'core/script_gen.py',
        'args':   lambda ch, ep, dr: ['--ch', ch, '--ep', str(ep)] + (['--dry-run'] if dr else []),
    },
    2: {
        'name':   '썸네일 생성',
        'script': CODE_ROOT / 'core/thumbnail_gen.py',
        'args':   lambda ch, ep, dr: ['--ch', ch, '--ep', str(ep)],
    },
    3: {
        'name':   'I2V 영상 생성 (WanGP)',
        'script': CODE_ROOT / 'core/wangp_agent.py',
        'args':   lambda ch, ep, dr: ['--ch', ch, '--ep', str(ep)],
    },
    4: {
        'name':   'YouTube 업로드',
        'script': Path('D:/1인기업/01_youtube/scripts/youtube_uploader.py'),
        'args':   lambda ch, ep, dr: ['--ch', ch, '--ep', str(ep)] + (['--dry-run'] if dr else []),
    },
    5: {
        'name':   '블로그 포스팅',
        'script': Path('D:/1인기업/06_blog/scripts/blog_poster.py'),
        'args':   lambda ch, ep, dr: ['--ch', ch, '--ep', str(ep)] + (['--dry-run'] if dr else []),
    },
    6: {
        'name':   '뉴스레터 발송',
        'script': Path('D:/1인기업/03_newsletter/scripts/newsletter_gen.py'),
        'args':   lambda ch, ep, dr: ['--ch', ch, '--ep', str(ep)] + (['--dry-run'] if dr else []),
    },
    7: {
        'name':   '제휴링크 생성',
        'script': Path('D:/1인기업/07_affiliate/scripts/affiliate_matcher.py'),
        'args':   lambda ch, ep, dr: ['--ch', ch, '--ep', str(ep)] + (['--dry-run'] if dr else []),
    },
}

PYTHON_EXE = os.environ.get('GAON_PYTHON', 'D:/programs/python.exe')


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


def _notify_discord(message: str) -> None:
    """Discord 알림 (웹훅 설정된 경우만)."""
    webhook_url = os.environ.get('DISCORD_WEBHOOK_URL', '')
    if not webhook_url:
        return
    try:
        import urllib.request
        payload = json.dumps({'content': message}).encode('utf-8')
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={'Content-Type': 'application/json'},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def _load_checkpoint(ch_slug: str, ep_num: int) -> dict:
    """이전 실행 체크포인트 로드."""
    cp_path = Path(f'D:/gaon_temp/checkpoints/{ch_slug}_ep{ep_num:02d}_pipeline.json')
    if cp_path.exists():
        try:
            with open(cp_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {}


def _save_checkpoint(ch_slug: str, ep_num: int, stage_results: dict) -> None:
    """실행 체크포인트 저장."""
    cp_dir = Path('D:/gaon_temp/checkpoints')
    cp_dir.mkdir(parents=True, exist_ok=True)
    cp_path = cp_dir / f'{ch_slug}_ep{ep_num:02d}_pipeline.json'
    with open(cp_path, 'w', encoding='utf-8') as f:
        json.dump({
            'ch_slug':       ch_slug,
            'ep_num':        ep_num,
            'last_updated':  datetime.now().isoformat(),
            'stages':        stage_results,
        }, f, ensure_ascii=False, indent=2)


def _run_stage(stage_num: int, ch_slug: str, ep_num: int,
               dry_run: bool = False) -> dict:
    """단일 스테이지 실행."""
    stage   = STAGES[stage_num]
    name    = stage['name']
    script  = stage['script']
    extra   = stage['args'](ch_slug, ep_num, dry_run)

    if not script.exists():
        logger.warning(f'[{stage_num}단계] 스크립트 없음: {script}')
        return {'status': 'skip', 'reason': f'스크립트 없음: {script.name}'}

    python = PYTHON_EXE if Path(PYTHON_EXE).exists() else sys.executable
    cmd    = [python, '-X', 'utf8', str(script)] + extra

    logger.info(f'[{stage_num}단계] {name} 시작')
    t_start = time.time()

    try:
        result = subprocess.run(
            cmd,
            shell=False,
            encoding='utf-8',
            errors='replace',
            capture_output=True,
            timeout=3600,
            env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'},
        )
        elapsed = time.time() - t_start
        ok = result.returncode == 0

        if ok:
            logger.info(f'[{stage_num}단계] {name} 완료 ({elapsed:.1f}s)')
        else:
            logger.error(f'[{stage_num}단계] {name} 실패 (rc={result.returncode})')
            if result.stderr:
                logger.error(f'  stderr: {result.stderr[:200]}')

        return {
            'status':  'ok' if ok else 'fail',
            'elapsed': round(elapsed, 1),
            'rc':      result.returncode,
        }

    except subprocess.TimeoutExpired:
        logger.error(f'[{stage_num}단계] {name} 타임아웃 (3600s)')
        return {'status': 'timeout', 'elapsed': 3600}
    except Exception as e:
        logger.error(f'[{stage_num}단계] {name} 예외: {type(e).__name__}')
        return {'status': 'error', 'reason': type(e).__name__}


def run_pipeline(ch_slug: str, ep_num: int,
                 stages_to_run: Optional[list[int]] = None,
                 skip_stages: Optional[list[int]] = None,
                 from_stage: int = 1,
                 dry_run: bool = False,
                 resume: bool = False) -> dict:
    """전체 파이프라인 실행."""
    logger.info('=' * 55)
    logger.info(f'GAON NEXUS 파이프라인: {ch_slug} EP{ep_num:02d}')
    logger.info(f'시작: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    logger.info('=' * 55)

    _notify_discord(f'🚀 파이프라인 시작: **{ch_slug}** EP{ep_num:02d}')

    # 체크포인트 로드
    checkpoint = _load_checkpoint(ch_slug, ep_num) if resume else {}
    prev_stages = checkpoint.get('stages', {})

    target_stages = stages_to_run or list(STAGES.keys())
    target_stages = [s for s in target_stages if s >= from_stage]
    if skip_stages:
        target_stages = [s for s in target_stages if s not in skip_stages]

    results = dict(prev_stages)
    t_total = time.time()

    for stage_num in sorted(target_stages):
        stage_name = STAGES[stage_num]['name']

        # 이미 성공한 스테이지 건너뜀 (resume 모드)
        if resume and str(stage_num) in prev_stages:
            if prev_stages[str(stage_num)].get('status') == 'ok':
                logger.info(f'[{stage_num}단계] {stage_name} — 이미 완료 (건너뜀)')
                continue

        result = _run_stage(stage_num, ch_slug, ep_num, dry_run)
        results[str(stage_num)] = {**result, 'name': stage_name}
        _save_checkpoint(ch_slug, ep_num, results)

        # 중요 스테이지 실패 시 중단
        if result['status'] in ('fail', 'error') and stage_num <= 3:
            logger.error(f'[{stage_num}단계] 치명 오류 — 파이프라인 중단')
            _notify_discord(f'❌ 파이프라인 실패: **{ch_slug}** EP{ep_num:02d} — {stage_name} 오류')
            break

    total_elapsed = time.time() - t_total
    ok_count   = sum(1 for r in results.values() if r.get('status') == 'ok')
    fail_count = sum(1 for r in results.values() if r.get('status') == 'fail')
    skip_count = sum(1 for r in results.values() if r.get('status') == 'skip')

    summary = (
        f'\n{"=" * 55}\n'
        f'파이프라인 완료: {ch_slug} EP{ep_num:02d}\n'
        f'소요시간: {total_elapsed:.1f}s | '
        f'성공 {ok_count} / 실패 {fail_count} / 건너뜀 {skip_count}\n'
    )

    STATUS_ICON = {'ok': '✅', 'fail': '❌', 'skip': '⏭️', 'timeout': '⏱️', 'error': '💥'}
    for num in sorted(results.keys(), key=int):
        r    = results[num]
        icon = STATUS_ICON.get(r.get('status', ''), '❓')
        elapsed_str = f" ({r['elapsed']:.1f}s)" if r.get('elapsed') else ''
        summary += f'  {icon} [{num}] {r["name"]}{elapsed_str}\n'

    summary += '=' * 55
    logger.info(summary)

    if fail_count == 0:
        _notify_discord(f'🏁 파이프라인 완료: **{ch_slug}** EP{ep_num:02d} — 전체 {total_elapsed:.0f}s')
    else:
        _notify_discord(f'⚠️ 파이프라인 부분 완료: **{ch_slug}** EP{ep_num:02d} — {fail_count}개 실패')

    return {
        'ch_slug': ch_slug,
        'ep_num':  ep_num,
        'ok':      fail_count == 0,
        'stages':  results,
        'elapsed': round(total_elapsed, 1),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='GAON NEXUS 파이프라인 오케스트레이터')
    parser.add_argument('--ch',         required=True, help='채널 슬러그 또는 all')
    parser.add_argument('--ep',         type=int, required=True, help='에피소드 번호')
    parser.add_argument('--from-stage', type=int, default=1,
                        help='시작 스테이지 번호 (기본: 1)')
    parser.add_argument('--stages',     default=None,
                        help='실행할 스테이지 번호 목록 (예: 1,2,5)')
    parser.add_argument('--skip',       default=None,
                        help='건너뜀 스테이지 번호 목록 (예: 3,4)')
    parser.add_argument('--dry-run',    action='store_true',
                        help='실제 업로드/발송 없이 구조 확인')
    parser.add_argument('--resume',     action='store_true',
                        help='체크포인트에서 재개')
    parser.add_argument('--list',       action='store_true',
                        help='스테이지 목록 출력')
    args = parser.parse_args()

    if args.list:
        print('GAON NEXUS 파이프라인 스테이지:')
        for num, stage in STAGES.items():
            print(f'  [{num}] {stage["name"]}')
        sys.exit(0)

    valid_slugs = set(CHANNEL_SLUGS.values())
    if args.ch == 'all':
        slugs = sorted(valid_slugs)
    elif args.ch in valid_slugs:
        slugs = [args.ch]
    else:
        parser.error(f'알 수 없는 채널: {args.ch!r}')

    if not (1 <= args.ep <= 9999):
        parser.error(f'EP 범위 오류: {args.ep}')

    stages_to_run = [int(s) for s in args.stages.split(',')] if args.stages else None
    skip_stages   = [int(s) for s in args.skip.split(',')]   if args.skip   else None

    all_ok = True
    for slug in slugs:
        result = run_pipeline(
            slug, args.ep,
            stages_to_run=stages_to_run,
            skip_stages=skip_stages,
            from_stage=args.from_stage,
            dry_run=args.dry_run,
            resume=args.resume,
        )
        if not result['ok']:
            all_ok = False

    sys.exit(0 if all_ok else 1)

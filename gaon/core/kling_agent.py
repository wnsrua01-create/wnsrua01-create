#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명: kling_agent.py
목적: fal.ai Kling AI 3.0 API — 3단계 I2V 폴백 (WanGP/Grok 불가 시)
작성일: 2026-05-22
설치 위치(Windows): C:/gaon/core/kling_agent.py

환경변수 (.env):
  FAL_KEY=...   (fal.ai API Key — https://fal.ai/dashboard/keys)

사용법:
  python kling_agent.py --image D:/gaon_data/thumbs/ch01_senior/ep01_s001.png --prompt "warm sunrise" --out D:/gaon_data/videos/test.mp4
  python kling_agent.py --ch senior --ep 1 --scene 1
  python kling_agent.py --ch senior --ep 1 --batch
"""
import sys
import os
import json
import time
import base64
import logging
import argparse
import urllib.request
import urllib.parse
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
ROOT_VIDEOS  = Path('D:/gaon_data/videos')
LOG_DIR      = Path('C:/gaon/logs')
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'kling_agent.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# fal.ai Kling 모델 ID (Kling AI 3.0 I2V)
KLING_MODEL        = 'fal-ai/kling-video/v1.6/image-to-video'
FAL_API_BASE       = 'https://queue.fal.run'
FAL_RESULT_BASE    = 'https://queue.fal.run'
POLL_INTERVAL_SEC  = 5
MAX_POLL_ATTEMPTS  = 120   # 최대 10분 대기

CHANNEL_SLUGS = {
    'ch01': 'senior',  'ch02': 'finance', 'ch03': 'health',
    'ch04': 'pension', 'ch05': 'psych',   'ch06': 'realty',
    'ch07': 'parent',  'ch08': 'cooking', 'ch09': 'aitech',
    'ch10': 'travel',  'ch11': 'beauty',  'ch12': 'growth',
    'ch13': 'history', 'ch14': 'pets',    'ch15': 'home',
    'ch16': 'midlife', 'ch17': 'money',
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


def _get_fal_key() -> str:
    key = os.environ.get('FAL_KEY', '')
    if not key:
        raise EnvironmentError('FAL_KEY 환경변수 미설정. C:/gaon/.env에 FAL_KEY=... 추가 필요')
    return key


def _image_to_data_uri(image_path: str) -> str:
    """로컬 이미지 → base64 data URI."""
    p = Path(image_path)
    suffix = p.suffix.lower()
    mime = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
            'webp': 'image/webp'}.get(suffix[1:], 'image/png')
    with open(p, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('ascii')
    return f'data:{mime};base64,{b64}'


def _fal_request(method: str, path: str, body: Optional[dict] = None) -> dict:
    """fal.ai HTTP 요청 헬퍼."""
    url = f'https://queue.fal.run/{path}'
    data = json.dumps(body).encode('utf-8') if body else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            'Authorization': f'Key {_get_fal_key()}',
            'Content-Type':  'application/json',
            'User-Agent':    'gaon-kling-agent/1.0',
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def submit_job(image_path: str, prompt: str,
               duration: str = '5', aspect_ratio: str = '16:9') -> str:
    """
    Kling I2V 작업 제출.
    Returns: request_id
    """
    logger.info(f'Kling 작업 제출: {Path(image_path).name} / "{prompt[:50]}"')

    # 로컬 파일이면 base64로 변환
    if Path(image_path).exists():
        image_url = _image_to_data_uri(image_path)
    else:
        image_url = image_path  # 이미 URL인 경우

    payload = {
        'image_url':    image_url,
        'prompt':       prompt,
        'duration':     duration,     # "5" or "10"
        'aspect_ratio': aspect_ratio, # "16:9" or "9:16" or "1:1"
        'negative_prompt': 'blur, distortion, watermark, text',
    }

    result = _fal_request('POST', KLING_MODEL, payload)
    request_id = result.get('request_id', '')
    if not request_id:
        raise RuntimeError(f'request_id 없음: {result}')

    logger.info(f'작업 제출 완료 — request_id: {request_id}')
    return request_id


def poll_job(request_id: str) -> Optional[str]:
    """
    작업 완료까지 폴링.
    Returns: 완성 MP4 URL (실패 시 None)
    """
    status_path = f'{KLING_MODEL}/requests/{request_id}/status'
    result_path = f'{KLING_MODEL}/requests/{request_id}'

    for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
        try:
            status_resp = _fal_request('GET', status_path)
            status = status_resp.get('status', 'unknown')

            if status == 'COMPLETED':
                result_resp = _fal_request('GET', result_path)
                video = result_resp.get('video', {})
                url = video.get('url', '')
                if url:
                    logger.info(f'Kling 완료 (시도 {attempt}): {url[:80]}')
                    return url
                logger.warning('완료됐지만 video URL 없음')
                return None

            elif status in ('FAILED', 'CANCELLED'):
                err = status_resp.get('error', '')
                logger.error(f'Kling 실패: {status} — {err}')
                return None

            else:
                if attempt % 6 == 0:
                    logger.info(f'  대기 중... ({attempt * POLL_INTERVAL_SEC}s / status={status})')
                time.sleep(POLL_INTERVAL_SEC)

        except Exception as e:
            logger.warning(f'폴링 오류 (시도 {attempt}): {type(e).__name__}')
            time.sleep(POLL_INTERVAL_SEC * 2)

    logger.error(f'폴링 타임아웃 ({MAX_POLL_ATTEMPTS * POLL_INTERVAL_SEC}s)')
    return None


def download_video(url: str, output_path: str) -> bool:
    """완성 영상 다운로드."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'gaon-kling-agent/1.0'})
        with urllib.request.urlopen(req, timeout=120) as resp:
            out.write_bytes(resp.read())
        logger.info(f'다운로드 완료: {out} ({out.stat().st_size // 1024}KB)')
        return True
    except Exception as e:
        logger.error(f'다운로드 실패: {type(e).__name__}')
        return False


def process_scene(ch_slug: str, ep_num: int, scene_num: int,
                  image_path: Optional[str] = None,
                  prompt: Optional[str] = None) -> Optional[Path]:
    """단일 씬 I2V 처리."""
    ch_num = next((k for k, v in CHANNEL_SLUGS.items() if v == ch_slug), 'ch01')
    ep_str = f'ep{ep_num:02d}'
    sc_str = f's{scene_num:03d}'

    # 이미지 경로 자동 탐색
    if not image_path:
        ch_dir  = ROOT_THUMBS / f'ch{int(ch_num[2:]):02d}_{ch_slug}'
        for fname in [f'{ep_str}_{sc_str}.png', f'{ep_str}_{sc_str}.jpg',
                      f'{ep_str}_thumb.png']:
            p = ch_dir / fname
            if p.exists():
                image_path = str(p)
                break

    if not image_path or not Path(image_path).exists():
        logger.error(f'이미지 없음: {ch_slug} EP{ep_num} 씬{scene_num}')
        return None

    # 프롬프트 자동 로드
    if not prompt:
        ep_dir = ROOT_SCRIPTS / f'ch{int(ch_num[2:]):02d}_{ch_slug}' / ep_str
        for fname in [f'{ep_str}_data.json', 'data.json']:
            p = ep_dir / fname
            if p.exists():
                try:
                    with open(p, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    scenes = data.get('scenes', [])
                    sc = next((s for s in scenes if s.get('scene_num') == scene_num), None)
                    if sc:
                        prompt = sc.get('visual_prompt', '')
                except json.JSONDecodeError:
                    pass
                break

    prompt = prompt or f'{ch_slug} scene {scene_num} cinematic'

    # 출력 경로
    out_dir = ROOT_VIDEOS / f'ch{int(ch_num[2:]):02d}_{ch_slug}' / ep_str
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f'{ep_str}_{sc_str}_kling.mp4'

    if out_path.exists():
        logger.info(f'이미 존재: {out_path.name} — 건너뜀')
        return out_path

    try:
        request_id = submit_job(image_path, prompt)
        video_url  = poll_job(request_id)
        if video_url and download_video(video_url, str(out_path)):
            return out_path
    except Exception as e:
        logger.error(f'씬 처리 실패: {type(e).__name__}: {str(e)[:80]}')

    return None


def batch_process(ch_slug: str, ep_num: int,
                  scene_range: tuple[int, int] = (1, 130)) -> dict:
    """배치 씬 처리 (WanGP 폴백용)."""
    start, end = scene_range
    done, failed = [], []

    for scene_num in range(start, end + 1):
        result = process_scene(ch_slug, ep_num, scene_num)
        if result:
            done.append(scene_num)
        else:
            failed.append(scene_num)
        # fal.ai rate limit 방어
        time.sleep(0.5)

    logger.info(f'배치 완료: 성공 {len(done)}씬 / 실패 {len(failed)}씬')
    return {'done': done, 'failed': failed}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='GAONIX Kling AI I2V 에이전트 (3단계 폴백)')
    parser.add_argument('--ch',     help='채널 슬러그')
    parser.add_argument('--ep',     type=int, help='에피소드 번호')
    parser.add_argument('--scene',  type=int, help='단일 씬 번호')
    parser.add_argument('--batch',  action='store_true', help='전체 씬 배치 처리')
    parser.add_argument('--start',  type=int, default=1,   help='배치 시작 씬')
    parser.add_argument('--end',    type=int, default=130, help='배치 종료 씬')
    parser.add_argument('--image',  help='이미지 경로 (단일 씬 직접 지정)')
    parser.add_argument('--prompt', help='Visual 프롬프트 (단일 씬 직접 지정)')
    parser.add_argument('--out',    help='출력 MP4 경로 (단일 씬 직접 지정)')
    parser.add_argument('--check',  action='store_true', help='fal.ai 연결 상태 확인')
    args = parser.parse_args()

    if args.check:
        try:
            key = _get_fal_key()
            req = urllib.request.Request(
                'https://api.fal.ai/v1/models?limit=1',
                headers={'Authorization': f'Key {key}', 'User-Agent': 'gaon-health-check'},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                print(f'✅ fal.ai 연결 OK (HTTP {resp.status})')
        except Exception as e:
            print(f'❌ fal.ai 연결 실패: {e}')
        sys.exit(0)

    # 단일 이미지 직접 처리
    if args.image and args.prompt:
        try:
            request_id = submit_job(args.image, args.prompt)
            url = poll_job(request_id)
            if url:
                out_path = args.out or f'kling_output_{int(time.time())}.mp4'
                download_video(url, out_path)
                print(f'✅ 저장: {out_path}')
            else:
                print('❌ 실패')
        except Exception as e:
            print(f'❌ 오류: {e}')
        sys.exit(0)

    if not args.ch or not args.ep:
        parser.error('--ch, --ep 필수')

    valid_slugs = set(CHANNEL_SLUGS.values())
    if args.ch not in valid_slugs:
        parser.error(f'알 수 없는 채널: {args.ch!r}')
    if not (1 <= args.ep <= 9999):
        parser.error(f'EP 범위 오류: {args.ep}')

    if args.batch:
        if not (1 <= args.start <= 130 and 1 <= args.end <= 130 and args.start <= args.end):
            parser.error(f'씬 범위 오류: {args.start}-{args.end}')
        result = batch_process(args.ch, args.ep, (args.start, args.end))
        print(f'\n완료: {len(result["done"])}씬 / 실패: {len(result["failed"])}씬')
    elif args.scene:
        if not (1 <= args.scene <= 130):
            parser.error(f'씬 범위 오류: {args.scene}')
        out = process_scene(args.ch, args.ep, args.scene)
        print(f'{"✅" if out else "❌"} {out or "실패"}')
    else:
        parser.error('--scene 또는 --batch 중 하나 필요')

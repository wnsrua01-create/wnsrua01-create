#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명: wangp_agent.py
목적: WanGP 로컬 I2V 자동화 에이전트 — Grok 100편/24h 병목 해소
작성일: 2026-05-21
설치 위치(Windows): C:\gaon\core\wangp_agent.py

WanGP v11.26 설치 경로: C:\pinokio\api\wan.git\app\
기본 포트 탐색 순서: 8080, 7860, 7861, 8000
"""
import sys
import os
import time
import json
import logging
import base64
import shutil
from pathlib import Path
from queue import Queue
from threading import Thread
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

try:
    import requests
except ImportError:
    print("requests 미설치. pip install requests 실행 후 재시도.")
    sys.exit(1)

# ── 로깅 설정 ───────────────────────────────────────────────────────────────
LOG_DIR = Path('C:/gaon/logs')
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'wangp_agent.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ── 상수 ────────────────────────────────────────────────────────────────────
WANGP_PORTS = [8080, 7860, 7861, 8000]

# 탐색할 Gradio/FastAPI 엔드포인트 후보 (실제 WanGP 버전에 따라 다름)
WANGP_ENDPOINTS = [
    '/api/predict',
    '/run/predict',
    '/api/queue/join',
    '/gradio_api/call/generate',
    '/queue/join',
]

ROOT_VIDEOS = Path('D:/gaon_data/videos')
ROOT_TEMP   = Path('D:/gaon_temp/wangp_queue')

MAX_RETRIES  = 3
POLL_INTERVAL = 10   # 초
DEFAULT_TIMEOUT = 600  # 초 (10분)


class WanGPAgent:
    """
    WanGP HTTP API 자동화 에이전트.

    사용 예:
        agent = WanGPAgent()
        if agent.health_check():
            job_id = agent.submit_job('D:/img/ep01_s001.png', 'A woman smiling', 'D:/out/s001.mp4')
            agent.poll_job(job_id)
    """

    # 허용된 호스트 목록 (로컬/내부망 전용 — 외부망 노출 금지)
    _ALLOWED_HOSTS = {'localhost', '127.0.0.1', '::1'}

    def __init__(self, host: str = 'localhost'):
        if host not in self._ALLOWED_HOSTS:
            raise ValueError(
                f'보안 정책: WanGP는 로컬호스트만 허용됩니다. '
                f'요청 host={host!r}'
            )
        self.host = host
        self.base_url: Optional[str] = None
        self.api_endpoint: Optional[str] = None
        self._discover()

    # ── 서버 자동 탐색 ─────────────────────────────────────────────────────

    def _discover(self) -> bool:
        """포트 + 엔드포인트를 순차 탐색하여 활성 WanGP 서버 감지.
        HTTP(비암호화) 사용은 로컬호스트 전용이므로 허용 (내부망, 암호화 불필요).
        """
        for port in WANGP_PORTS:
            base = f'http://{self.host}:{port}'  # 로컬 전용 HTTP — 외부망 금지
            try:
                r = requests.get(base, timeout=3)
                if r.status_code < 500:
                    self.base_url = base
                    logger.info(f"WanGP UI 발견: {base}")
                    self._find_api_endpoint()
                    return True
            except requests.exceptions.ConnectionError:
                continue
        logger.warning("WanGP 서버를 찾을 수 없습니다. 서버를 먼저 실행하세요.")
        return False

    def _find_api_endpoint(self) -> None:
        """활성 API 엔드포인트 탐색."""
        if not self.base_url:
            return
        for ep in WANGP_ENDPOINTS:
            url = self.base_url + ep
            try:
                r = requests.get(url, timeout=3)
                # 200 또는 405(POST만 허용) 모두 엔드포인트 존재로 판단
                if r.status_code in (200, 405, 422):
                    self.api_endpoint = ep
                    logger.info(f"API 엔드포인트 발견: {ep}")
                    return
            except Exception:
                continue

        # Gradio Info API로 엔드포인트 자동 감지 시도
        try:
            info_url = self.base_url + '/info'
            r = requests.get(info_url, timeout=5)
            if r.status_code == 200:
                info = r.json()
                named = info.get('named_endpoints', {})
                if named:
                    self.api_endpoint = '/run/' + list(named.keys())[0]
                    logger.info(f"Gradio Info로 엔드포인트 감지: {self.api_endpoint}")
                    return
        except Exception:
            pass

        logger.warning("API 엔드포인트 자동 감지 실패 — submit_job 시 수동 지정 필요")

    # ── 공개 메서드 ────────────────────────────────────────────────────────

    def health_check(self) -> bool:
        """WanGP 서버 상태 확인. True = 정상."""
        if not self.base_url:
            self._discover()
        if not self.base_url:
            return False
        try:
            r = requests.get(self.base_url, timeout=5)
            ok = r.status_code < 500
            logger.info(f"헬스체크 {'OK' if ok else 'FAIL'}: {self.base_url} ({r.status_code})")
            return ok
        except Exception as e:
            logger.error(f"헬스체크 오류: {e}")
            return False

    def submit_job(self, image_path: str, prompt: str, output_path: str,
                   duration: float = 6.0) -> Optional[str]:
        """
        씬 이미지 + 프롬프트 → WanGP 작업 제출.

        Args:
            image_path: 입력 이미지 PNG 경로
            prompt: 영문 모션 프롬프트
            output_path: 출력 MP4 저장 경로
            duration: 클립 길이(초), 기본 6초

        Returns:
            job_id (str) 또는 None (실패 시)
        """
        if not self.base_url:
            logger.error("WanGP 서버 미연결")
            return None

        img = Path(image_path)
        if not img.exists():
            logger.error(f"이미지 없음: {image_path}")
            return None

        # 이미지 base64 인코딩
        img_b64 = base64.b64encode(img.read_bytes()).decode('ascii')
        img_data_uri = f"data:image/png;base64,{img_b64}"

        payload = {
            "data": [
                img_data_uri,   # 입력 이미지
                prompt,         # 프롬프트
                "",             # 네거티브 프롬프트 (빈값)
                duration,       # 클립 길이
                512,            # 가로 (WanGP 기본값)
                512,            # 세로
                25,             # 추론 스텝
                7.5,            # CFG scale
                42,             # 시드
            ],
            "fn_index": 0,
        }

        endpoint = self.api_endpoint or '/run/predict'
        url = self.base_url + endpoint

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"작업 제출 시도 {attempt}/{MAX_RETRIES}: {img.name}")
                r = requests.post(url, json=payload, timeout=30)

                if r.status_code == 200:
                    result = r.json()
                    # Gradio 큐 방식: event_id 반환
                    job_id = result.get('event_id') or result.get('hash') or 'sync'
                    logger.info(f"작업 제출 성공: job_id={job_id}")

                    # 동기 응답인 경우 즉시 파일 저장
                    if job_id == 'sync' and 'data' in result:
                        self._save_output(result['data'], output_path)
                        return 'sync_done'

                    # 비동기: output_path를 job_id와 매핑하여 저장
                    self._register_job(job_id, output_path)
                    return job_id

                logger.warning(f"제출 실패 ({r.status_code}): {r.text[:200]}")

            except requests.exceptions.Timeout:
                logger.warning(f"제출 타임아웃 (시도 {attempt})")
            except Exception as e:
                logger.error(f"제출 오류: {e}")

            if attempt < MAX_RETRIES:
                time.sleep(5 * attempt)

        return None

    def poll_job(self, job_id: str, output_path: str,
                 timeout: int = DEFAULT_TIMEOUT) -> bool:
        """
        작업 완료 대기 (폴링 방식).

        Args:
            job_id: submit_job에서 반환된 ID
            output_path: 완성 MP4 저장 경로
            timeout: 최대 대기 초

        Returns:
            True = 완료, False = 실패/타임아웃
        """
        if job_id == 'sync_done':
            return True

        status_url = self.base_url + f'/queue/status?hash={job_id}'
        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                r = requests.get(status_url, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    status = data.get('status', '')

                    if status == 'complete':
                        output_data = data.get('output', {}).get('data', [])
                        self._save_output(output_data, output_path)
                        logger.info(f"작업 완료: {job_id}")
                        return True
                    elif status in ('error', 'failed'):
                        logger.error(f"작업 실패: {job_id} — {data}")
                        return False

                    logger.debug(f"대기 중: {job_id} ({status})")

            except Exception as e:
                logger.warning(f"폴링 오류: {e}")

            time.sleep(POLL_INTERVAL)

        logger.error(f"타임아웃: {job_id} ({timeout}초 초과)")
        return False

    def batch_process(self, ch_id_or_slug: str, ep_num: int,
                      scene_range: tuple[int, int] = (1, 130),
                      prompt_fn=None) -> dict:
        """
        에피소드 전체 씬 배치 처리.

        Args:
            ch_id_or_slug: 'ch01' 또는 'senior'
            ep_num: 에피소드 번호
            scene_range: (시작씬, 끝씬) 기본 (1, 130)
            prompt_fn: scene_num → prompt 함수 (None이면 기본 프롬프트 사용)

        Returns:
            {'done': [...], 'failed': [...]} 딕트
        """
        from pathlib import Path as _P
        sys.path.insert(0, str(_P(__file__).parent.parent / 'utils'))
        try:
            from path_utils import get_ep_path, get_video_path, safe_mkdir
        except ImportError:
            logger.error("path_utils.py 없음 — C:\\gaon\\utils\\ 확인")
            return {'done': [], 'failed': list(range(scene_range[0], scene_range[1] + 1))}

        ep_path = get_ep_path(ch_id_or_slug, ep_num)
        vid_path = get_video_path(ch_id_or_slug, ep_num)
        safe_mkdir(vid_path)

        ep_str = f'ep{ep_num:02d}'
        done, failed = [], []

        start, end = scene_range
        for scene in range(start, end + 1):
            img = ep_path / f'{ep_str}_s{scene:03d}.png'
            out = vid_path / f'{ep_str}_s{scene:03d}.mp4'

            if out.exists():
                logger.info(f"이미 존재: {out.name} — 건너뜀")
                done.append(scene)
                continue

            prompt = prompt_fn(scene) if prompt_fn else (
                "A person speaking naturally, subtle facial movement, realistic"
            )

            job_id = self.submit_job(str(img), prompt, str(out))
            if job_id is None:
                logger.error(f"제출 실패: 씬 {scene:03d}")
                failed.append(scene)
                continue

            if job_id != 'sync_done':
                success = self.poll_job(job_id, str(out))
                if not success:
                    failed.append(scene)
                    continue

            done.append(scene)
            logger.info(f"완료: 씬 {scene:03d}/{end} — {out.name}")

        logger.info(f"배치 완료 — 성공: {len(done)}, 실패: {len(failed)}")
        return {'done': done, 'failed': failed}

    # ── 내부 헬퍼 ──────────────────────────────────────────────────────────

    def _save_output(self, data: list, output_path: str) -> None:
        """Gradio 응답 data 배열에서 MP4 파일 저장."""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        for item in data:
            if isinstance(item, dict):
                # Gradio FileData 형식: {"path": "...", "name": "..."}
                tmp_path = item.get('path') or item.get('name', '')
                if tmp_path and Path(tmp_path).exists():
                    shutil.copy2(tmp_path, out)
                    logger.info(f"저장 완료: {out}")
                    return
            elif isinstance(item, str) and item.startswith('data:video'):
                # base64 인코딩된 비디오
                b64 = item.split(',', 1)[1]
                out.write_bytes(base64.b64decode(b64))
                logger.info(f"저장 완료 (base64): {out}")
                return

        type_summary = [type(x).__name__ for x in data]
        logger.warning(f"출력 파일 저장 불가 — 응답 데이터 형식 확인 필요: {type_summary}")

    def _register_job(self, job_id: str, output_path: str) -> None:
        """비동기 작업 정보를 임시 JSON에 기록."""
        ROOT_TEMP.mkdir(parents=True, exist_ok=True)
        registry = ROOT_TEMP / 'jobs.json'
        jobs = {}
        if registry.exists():
            try:
                with open(registry, 'r', encoding='utf-8') as f:
                    jobs = json.load(f)
            except Exception:
                pass
        jobs[job_id] = {'output_path': output_path, 'submitted_at': time.time()}
        with open(registry, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)


# ── CLI 진입점 ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='WanGP I2V 자동화 에이전트')
    parser.add_argument('--check', action='store_true', help='서버 상태 확인')
    parser.add_argument('--ch', default='senior', help='채널 슬러그 (예: senior)')
    parser.add_argument('--ep', type=int, default=1, help='에피소드 번호')
    parser.add_argument('--start', type=int, default=1, help='시작 씬 번호')
    parser.add_argument('--end', type=int, default=130, help='끝 씬 번호')
    args = parser.parse_args()

    if not (1 <= args.start <= 130 and 1 <= args.end <= 130 and args.start <= args.end):
        parser.error(f'씬 범위 오류: --start {args.start} --end {args.end} (유효: 1-130)')
    if not (1 <= args.ep <= 9999):
        parser.error(f'에피소드 번호 범위 오류: {args.ep} (1-9999)')

    agent = WanGPAgent()

    if args.check:
        ok = agent.health_check()
        print(f"WanGP 상태: {'✅ 정상' if ok else '❌ 연결 불가'}")
        if agent.base_url:
            print(f"  URL: {agent.base_url}")
        if agent.api_endpoint:
            print(f"  API: {agent.api_endpoint}")
        sys.exit(0 if ok else 1)

    result = agent.batch_process(args.ch, args.ep, (args.start, args.end))
    print(f"\n완료: {len(result['done'])}씬 / 실패: {len(result['failed'])}씬")
    if result['failed']:
        print(f"실패 씬: {result['failed']}")

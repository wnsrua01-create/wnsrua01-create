#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명: path_utils.py
목적: GAON NEXUS 한글 경로 안전 유틸리티 — Windows CP949/UTF-8 충돌 완전 해결
작성일: 2026-05-21
설치 위치(Windows): C:/gaon/utils/path_utils.py
"""
import sys
import os
import json
import subprocess
import shutil
from pathlib import Path

# ── Windows UTF-8 강제 설정 (임포트 즉시 실행) ─────────────────────────────
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

if sys.platform == 'win32':
    import ctypes
    import io
    try:
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    try:
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

# ── 경로 상수 ──────────────────────────────────────────────────────────────
ROOT_CODE    = Path('C:/gaon')
ROOT_SCRIPTS = Path('D:/gaon_data/scripts')
ROOT_VIDEOS  = Path('D:/gaon_data/videos')
ROOT_FINALS  = Path('D:/gaon_data/finals')
ROOT_THUMBS  = Path('D:/gaon_data/thumbs')
ROOT_TEMP    = Path('D:/gaon_temp')
ROOT_1PERSON = Path('D:/1인기업')

# ── 채널 슬러그 매핑 ───────────────────────────────────────────────────────
CHANNEL_SLUGS: dict[str, str] = {
    'ch01': 'senior',  'ch02': 'finance', 'ch03': 'health',
    'ch04': 'pension', 'ch05': 'psych',   'ch06': 'realty',
    'ch07': 'parent',  'ch08': 'cooking', 'ch09': 'aitech',
    'ch10': 'travel',  'ch11': 'beauty',  'ch12': 'growth',
    'ch13': 'history', 'ch14': 'pets',    'ch15': 'home',
    'ch16': 'midlife', 'ch17': 'money',
}

SLUG_TO_CHID: dict[str, str] = {v: k for k, v in CHANNEL_SLUGS.items()}

# ── 채널 번호 추출 헬퍼 ────────────────────────────────────────────────────
def _ch_num(ch_id_or_slug: str) -> int:
    """'ch01' 또는 'senior' → 1"""
    if ch_id_or_slug.startswith('ch'):
        try:
            return int(ch_id_or_slug[2:])
        except ValueError:
            pass
    chid = SLUG_TO_CHID.get(ch_id_or_slug, '')
    if chid:
        try:
            return int(chid[2:])
        except ValueError:
            pass
    return 0


def _slug(ch_id_or_slug: str) -> str:
    """'ch01' 또는 'senior' → 'senior'"""
    if ch_id_or_slug in CHANNEL_SLUGS:
        return CHANNEL_SLUGS[ch_id_or_slug]
    return ch_id_or_slug


# ── 핵심 경로 함수 ─────────────────────────────────────────────────────────

def get_ep_path(ch_id_or_slug: str, ep_num: int) -> Path:
    """채널ID 또는 슬러그 + 에피소드 번호 → 표준 스크립트 경로.

    예) get_ep_path('ch01', 1) → D:/gaon_data/scripts/ch01_senior/ep01
        get_ep_path('senior', 1) → 동일
    """
    num = _ch_num(ch_id_or_slug)
    slug = _slug(ch_id_or_slug)
    return ROOT_SCRIPTS / f'ch{num:02d}_{slug}' / f'ep{ep_num:02d}'


def get_video_path(ch_id_or_slug: str, ep_num: int) -> Path:
    """채널 + 에피소드 → 비디오 클립 저장 경로"""
    num = _ch_num(ch_id_or_slug)
    slug = _slug(ch_id_or_slug)
    return ROOT_VIDEOS / f'ch{num:02d}_{slug}' / f'ep{ep_num:02d}'


def get_final_path(ch_id_or_slug: str, ep_num: int) -> Path:
    """채널 + 에피소드 → 완성본 경로"""
    num = _ch_num(ch_id_or_slug)
    slug = _slug(ch_id_or_slug)
    return ROOT_FINALS / f'ch{num:02d}_{slug}'


# ── 파일 존재/생성 ──────────────────────────────────────────────────────────

def safe_exists(path) -> bool:
    return Path(path).exists()


def safe_mkdir(path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def safe_listdir(folder) -> list[str]:
    p = Path(folder)
    if not p.exists():
        return []
    return [str(f) for f in p.iterdir()]


# ── JSON I/O ────────────────────────────────────────────────────────────────

def safe_read_json(path) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def safe_write_json(path, data: dict, indent: int = 2) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def safe_read_text(path) -> str:
    return Path(path).read_text(encoding='utf-8')


def safe_write_text(path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')


# ── subprocess 안전 실행 ────────────────────────────────────────────────────

def safe_subprocess(cmd: list, cwd=None, timeout: int = 300) -> subprocess.CompletedProcess:
    """한글 경로 포함 subprocess 안전 실행 (shell=False 강제, encoding=utf-8)."""
    env = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}
    return subprocess.run(
        cmd,
        capture_output=True,
        encoding='utf-8',
        errors='replace',
        env=env,
        cwd=str(cwd) if cwd else None,
        timeout=timeout,
    )


# ── 씬 누락 스캔 ───────────────────────────────────────────────────────────

def scan_missing(ch_id_or_slug: str, ep_num: int, ext: str = 'png',
                 total: int = 130) -> list[int]:
    """total개 씬 파일 중 누락된 씬 번호 리스트 반환 (1-indexed)."""
    ep = get_ep_path(ch_id_or_slug, ep_num)
    ep_str = f'ep{ep_num:02d}'
    return [i for i in range(1, total + 1)
            if not (ep / f'{ep_str}_s{i:03d}.{ext}').exists()]


def scan_missing_videos(ch_id_or_slug: str, ep_num: int,
                        total: int = 130) -> list[int]:
    """비디오 클립 누락 씬 번호 리스트."""
    vp = get_video_path(ch_id_or_slug, ep_num)
    ep_str = f'ep{ep_num:02d}'
    return [i for i in range(1, total + 1)
            if not (vp / f'{ep_str}_s{i:03d}.mp4').exists()]


# ── 파일 복사 (send2trash 대신 shutil 활용) ────────────────────────────────

def safe_backup(path) -> Path:
    """파일을 .bak으로 백업. os.remove 사용 금지 규칙 준수."""
    src = Path(path)
    dst = src.with_suffix(src.suffix + '.bak')
    shutil.copy2(src, dst)
    return dst


# ── 자가 테스트 ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("=== path_utils.py 자가 테스트 ===")

    # 임포트 확인
    assert safe_read_json is not None
    print("✅ 임포트 OK")

    # 경로 생성 테스트
    p1 = get_ep_path('ch01', 1)
    assert str(p1).endswith('ep01'), f"경로 오류: {p1}"
    assert 'ch01_senior' in str(p1), f"슬러그 오류: {p1}"
    print(f"✅ get_ep_path OK → {p1}")

    p2 = get_ep_path('senior', 3)
    assert str(p2).endswith('ep03'), f"슬러그→경로 변환 오류: {p2}"
    print(f"✅ slug 변환 OK → {p2}")

    # JSON 읽기/쓰기 테스트 (ROOT_TEMP 없으면 현재 폴더 임시 사용)
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    test_path = tmp / 'test_utf8.json'
    test_data = {'test': '한글테스트', 'channel': '시니어보물창고', 'num': 42}
    safe_write_json(test_path, test_data)
    loaded = safe_read_json(test_path)
    assert loaded['test'] == '한글테스트', "한글 JSON 읽기 실패"
    assert loaded['num'] == 42
    print(f"✅ 한글 JSON 읽기/쓰기 OK")

    # 누락 스캔 (경로 없으면 전부 누락으로 반환)
    missing = scan_missing('ch01', 1)
    print(f"✅ scan_missing OK (결과: {len(missing)}개 누락 — D:/gaon_data 없으면 130개 정상)")

    # subprocess 테스트
    result = safe_subprocess([sys.executable, '-c', 'print("한글출력테스트")'])
    assert '한글출력테스트' in result.stdout, f"subprocess 출력 오류: {result.stdout}"
    print(f"✅ safe_subprocess OK")

    print("\n=== ALL TESTS PASSED ===")

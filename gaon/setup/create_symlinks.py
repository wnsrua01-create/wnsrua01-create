#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명: create_symlinks.py
목적: GAON NEXUS <-> D:\1인기업\ 심볼릭 링크 생성 (한글 경로 처리)
작성일: 2026-05-21
설치 위치(Windows): C:/gaon/setup/create_symlinks.py

gaon_link_setup.bat에서 호출됨 (관리자 권한 필요)
직접 실행: D:\programs\python.exe -X utf8 C:\gaon\setup\create_symlinks.py
"""
import sys
import os
import subprocess
import shutil
import json
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

# ── 심볼릭 링크 정의 ─────────────────────────────────────────────────────────
# (소스, 대상, 타입) — 타입: 'dir' | 'file'
SYMLINKS = [
    (
        'D:/gaon_data/scripts',
        'D:/1인기업/01_youtube/channels/data',
        'dir',
        '유튜브 채널 대본 데이터 연결',
    ),
    (
        'D:/gaon_data/finals',
        'D:/1인기업/02_shorts/source_finals',
        'dir',
        'Shorts 소스용 완성본 연결',
    ),
    (
        'D:/gaon_data/scripts',
        'D:/1인기업/04_ebooks/source_scripts',
        'dir',
        '전자책 소스용 대본 연결',
    ),
    (
        'D:/gaon_data/finals',
        'D:/1인기업/06_blog/source_finals',
        'dir',
        '블로그 소스용 완성본 연결',
    ),
]

# 파일 복사 대상 (심볼릭 링크보다 안정적)
FILE_COPIES = [
    (
        'C:/gaon/utils/path_utils.py',
        'D:/1인기업/09_tools/path_utils.py',
        'path_utils 공용 유틸 복사',
    ),
    (
        'C:/gaon/utils/discord_notify.py',
        'D:/1인기업/09_tools/discord_notify.py',
        'Discord 알림 유틸 복사',
    ),
]

# 사전 생성 필요 디렉토리 (gaon_data가 아직 없을 경우)
ENSURE_DIRS = [
    'D:/gaon_data/scripts',
    'D:/gaon_data/videos',
    'D:/gaon_data/finals',
    'D:/gaon_data/thumbs',
    'D:/gaon_temp/wangp_queue',
    'D:/gaon_temp/grok_inbox',
    'D:/gaon_temp/processing',
]


def _make_symlink_win(src: str, dst: str, link_type: str) -> bool:
    """
    Windows mklink으로 심볼릭 링크 생성.
    mklink /D = 디렉토리, mklink = 파일
    """
    flag = '/D' if link_type == 'dir' else ''
    cmd = f'mklink {flag} "{dst}" "{src}"'.strip()

    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        encoding='utf-8',
        errors='replace',
        env={**os.environ, 'PYTHONUTF8': '1'},
    )
    return result.returncode == 0


def _make_symlink_unix(src: str, dst: str, link_type: str) -> bool:
    """Linux/Mac 심볼릭 링크 (테스트용)."""
    try:
        os.symlink(src, dst)
        return True
    except Exception:
        return False


def ensure_dirs() -> None:
    """gaon_data 사전 디렉토리 생성."""
    print('[INIT] 기본 디렉토리 확인 중...')
    for d in ENSURE_DIRS:
        p = Path(d)
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            print(f'  ✅ 생성: {d}')
        else:
            print(f'  (기존) {d}')


def check_business_root() -> bool:
    """D:\1인기업\ 존재 확인."""
    root = Path('D:/1인기업')
    if not root.exists():
        print('[ERROR] D:\\1인기업\\ 없음')
        print('        먼저 실행: python C:\\gaon\\setup\\create_business_dirs.py')
        return False
    return True


def create_symlinks() -> dict:
    """모든 심볼릭 링크 생성."""
    results = {'ok': 0, 'skip': 0, 'fail': 0}
    is_win = sys.platform == 'win32'

    print('[LINK] 심볼릭 링크 생성 중...')
    for src, dst, link_type, desc in SYMLINKS:
        dst_path = Path(dst)
        src_path = Path(src)

        if dst_path.exists() or dst_path.is_symlink():
            print(f'  ⏭️  이미 존재: {dst}')
            results['skip'] += 1
            continue

        dst_path.parent.mkdir(parents=True, exist_ok=True)

        ok = _make_symlink_win(src, dst, link_type) if is_win else False

        if ok:
            print(f'  ✅ 링크 생성: {dst}')
            print(f'      → {src} ({desc})')
            results['ok'] += 1
        else:
            print(f'  ❌ 링크 실패: {dst} → {src}')
            print(f'      원인: 관리자 권한 필요 또는 소스 없음')
            results['fail'] += 1

    return results


def copy_tools() -> dict:
    """공용 도구 파일 복사 (링크보다 안정적)."""
    results = {'ok': 0, 'skip': 0, 'fail': 0}

    print('\n[COPY] 공용 도구 복사 중...')
    for src, dst, desc in FILE_COPIES:
        src_path = Path(src)
        dst_path = Path(dst)

        if dst_path.exists():
            print(f'  ⏭️  이미 존재: {dst_path.name}')
            results['skip'] += 1
            continue

        if not src_path.exists():
            print(f'  ⚠️  소스 없음: {src} — P0-A 완료 후 재실행')
            results['fail'] += 1
            continue

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dst_path)
        print(f'  ✅ 복사: {dst_path.name} ({desc})')
        results['ok'] += 1

    return results


def verify_links() -> None:
    """생성된 링크/파일 최종 검증."""
    print('\n[VERIFY] 최종 확인...')
    all_targets = (
        [(dst, '링크') for _, dst, _, _ in SYMLINKS] +
        [(dst, '파일') for _, dst, _ in FILE_COPIES]
    )
    ok, miss = 0, 0
    for target, kind in all_targets:
        p = Path(target)
        exists = p.exists() or p.is_symlink()
        if exists:
            print(f'  ✅ {kind}: {target}')
            ok += 1
        else:
            print(f'  ❌ {kind} 없음: {target}')
            miss += 1

    print(f'\n  결과: {ok}개 OK / {miss}개 실패')


def save_setup_record() -> None:
    """설치 완료 기록 저장."""
    from datetime import datetime
    record = {
        'setup_date': datetime.now().isoformat(),
        'symlinks': [{'src': s, 'dst': d, 'type': t} for s, d, t, _ in SYMLINKS],
        'copies': [{'src': s, 'dst': d} for s, d, _ in FILE_COPIES],
    }
    out = Path('C:/gaon/logs/link_setup_record.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    print(f'\n[LOG] 설치 기록 저장: {out}')


if __name__ == '__main__':
    print('=' * 60)
    print('GAON NEXUS 심볼릭 링크 설정')
    print('=' * 60)

    if not check_business_root():
        sys.exit(1)

    ensure_dirs()
    link_results = create_symlinks()
    copy_results = copy_tools()
    verify_links()
    save_setup_record()

    print('\n' + '=' * 60)
    total_ok   = link_results['ok']   + copy_results['ok']
    total_skip = link_results['skip'] + copy_results['skip']
    total_fail = link_results['fail'] + copy_results['fail']
    print(f'완료: {total_ok}개 성공 / {total_skip}개 건너뜀 / {total_fail}개 실패')
    print('=' * 60)

    sys.exit(1 if total_fail > 0 else 0)

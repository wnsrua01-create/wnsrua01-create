#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명: scan_installed.py
목적: GAON NEXUS 필요 프로그램 전체 설치 현황 스캔
실행: D:\programs\python.exe C:\gaon\ops\scan_installed.py
"""
import sys
import os
import shutil
import subprocess
import json
from pathlib import Path
from datetime import datetime

os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

if sys.platform == 'win32':
    import ctypes
    try:
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass

OK   = '[OK]  '
MISS = '[MISS]'
WARN = '[WARN]'

results = {'ok': [], 'miss': [], 'warn': []}

def _check(label, ok, detail='', warn=False):
    icon = WARN if warn else (OK if ok else MISS)
    line = f'{icon} {label:<35} {detail}'
    print(line)
    if ok:
        results['ok'].append(label)
    elif warn:
        results['warn'].append(label)
    else:
        results['miss'].append(label)


print('=' * 60)
print(f'GAON NEXUS 설치 스캔  {datetime.now().strftime("%Y-%m-%d %H:%M")}')
print('=' * 60)

# ── 1. 실행파일 ──────────────────────────────────────────────
print('\n[실행파일]')

# Python
py = shutil.which('python') or shutil.which('python3')
_check('Python', bool(py), sys.version.split()[0] if py else '없음')

# Python at D:/programs/python.exe
py_gaon = Path('D:/programs/python.exe')
_check('Python (D:/programs/)', py_gaon.exists(),
       str(py_gaon) if py_gaon.exists() else '없음')

# FFmpeg
ffmpeg = shutil.which('ffmpeg')
if ffmpeg:
    try:
        out = subprocess.run(['ffmpeg', '-version'], capture_output=True,
                             encoding='utf-8', timeout=5).stdout.split('\n')[0]
        _check('FFmpeg', True, out[:50])
    except Exception:
        _check('FFmpeg', True, ffmpeg)
else:
    _check('FFmpeg', False, 'PATH에 없음 — ffmpeg.org')

# Git
git = shutil.which('git')
if git:
    try:
        ver = subprocess.run(['git', '--version'], capture_output=True,
                             encoding='utf-8', timeout=5).stdout.strip()
        _check('Git', True, ver)
    except Exception:
        _check('Git', True, git)
else:
    _check('Git', False, 'git-scm.com')

# Docker
docker = shutil.which('docker')
if docker:
    try:
        ver = subprocess.run(['docker', '--version'], capture_output=True,
                             encoding='utf-8', timeout=5).stdout.strip()
        _check('Docker', True, ver[:50])
    except Exception:
        _check('Docker', True, docker)
else:
    _check('Docker', False, 'docker.com')

# ── 2. Python 패키지 ─────────────────────────────────────────
print('\n[Python 패키지]')

pkgs = [
    ('requests',                  'HTTP 통신'),
    ('PIL',                       'Pillow 썸네일'),
    ('reportlab',                 'PDF 전자책'),
    ('google.auth',               'YouTube OAuth2'),
    ('google_auth_oauthlib',      'YouTube OAuth2'),
    ('googleapiclient',           'YouTube API'),
    ('anthropic',                 'Claude API'),
    ('selenium',                  '브라우저 자동화'),
]

for pkg_import, desc in pkgs:
    try:
        mod = __import__(pkg_import)
        ver = getattr(mod, '__version__', '버전미상')
        _check(f'{pkg_import} ({desc})', True, ver)
    except ImportError:
        _check(f'{pkg_import} ({desc})', False, f'pip install {pkg_import}')

# ── 3. AI 엔진 (로컬 서버) ──────────────────────────────────
print('\n[AI 엔진 — 로컬 서버]')

import urllib.request

def _ping(label, url, timeout=3):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            _check(label, r.status < 500, f'HTTP {r.status} ({url})')
    except Exception as e:
        _check(label, False, f'오프라인 ({url})')

_ping('Ollama',   'http://localhost:11434/api/tags')
_ping('WanGP',    'http://localhost:7860/')
_ping('WanGP',    'http://localhost:8080/')
_ping('ComfyUI',  'http://localhost:8188/system_stats')
_ping('n8n',      'http://localhost:5678/healthz')

# Ollama 모델 확인
try:
    with urllib.request.urlopen('http://localhost:11434/api/tags', timeout=3) as r:
        data = json.loads(r.read())
        models = [m['name'] for m in data.get('models', [])]
        has_gemma = any('gemma4' in m for m in models)
        _check('gemma4:e4b 모델', has_gemma,
               ', '.join(models[:5]) + ('...' if len(models) > 5 else ''),
               warn=not has_gemma)
except Exception:
    _check('gemma4:e4b 모델', False, 'Ollama 오프라인 — 확인 불가')

# ── 4. 디렉토리 구조 ─────────────────────────────────────────
print('\n[디렉토리 — C:\\gaon\\]')

c_dirs = [
    Path('C:/gaon'),
    Path('C:/gaon/core'),
    Path('C:/gaon/utils'),
    Path('C:/gaon/ops'),
    Path('C:/gaon/config'),
    Path('C:/gaon/logs'),
    Path('C:/gaon/config/channels.json'),
    Path('C:/gaon/.env'),
]
for p in c_dirs:
    kind = '파일' if p.suffix else '폴더'
    _check(f'{kind}: {p}', p.exists())

print('\n[디렉토리 — D:\\]')

d_dirs = [
    Path('D:/gaon_data'),
    Path('D:/gaon_data/scripts'),
    Path('D:/gaon_data/videos'),
    Path('D:/gaon_data/finals'),
    Path('D:/gaon_data/thumbs'),
    Path('D:/gaon_temp'),
    Path('D:/1인기업'),
    Path('D:/1인기업/01_youtube'),
    Path('D:/1인기업/06_blog'),
    Path('D:/1인기업/07_affiliate'),
    Path('D:/ComfyUI'),
    Path('D:/programs/python.exe'),
]
for p in d_dirs:
    _check(str(p), p.exists())

# ── 5. .env 키 설정 여부 ────────────────────────────────────
print('\n[환경변수 — C:\\gaon\\.env]')

env_path = Path('C:/gaon/.env')
if env_path.exists():
    env_keys = {}
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                env_keys[k.strip()] = v.strip().strip('"').strip("'")

    check_keys = [
        ('GEMINI_API_KEY_01',    'Gemini LLM tier1'),
        ('ANTHROPIC_API_KEY',    'Claude API tier3'),
        ('FAL_KEY',              'Kling AI I2V'),
        ('DISCORD_WEBHOOK_URL',  'Discord 알림'),
        ('COUPANG_AF_ID',        '쿠팡파트너스'),
        ('TISTORY_ACCESS_TOKEN', '티스토리'),
        ('NAVER_BLOG_TOKEN',     '네이버 블로그'),
        ('STIBEE_API_KEY',       'Stibee 뉴스레터'),
        ('BEEHIIV_API_KEY',      'Beehiiv 뉴스레터'),
        ('MAILCHIMP_API_KEY',    'Mailchimp'),
    ]

    gemini_count = sum(1 for i in range(1, 14)
                       if env_keys.get(f'GEMINI_API_KEY_{i:02d}', ''))
    _check(f'Gemini API 키', gemini_count > 0,
           f'{gemini_count}/13개 설정됨',
           warn=(gemini_count < 13))

    for key, desc in check_keys[1:]:
        val = env_keys.get(key, '')
        _check(f'{key} ({desc})', bool(val),
               '설정됨' if val else '.env에 추가 필요')
else:
    _check('C:/gaon/.env', False, '파일 없음 — .env.example 복사 필요')

# ── 6. 스크립트 파일 존재 ────────────────────────────────────
print('\n[GAON NEXUS 스크립트]')

scripts = [
    (Path('C:/gaon/utils/path_utils.py'),          'path_utils'),
    (Path('C:/gaon/utils/discord_notify.py'),      'discord_notify'),
    (Path('C:/gaon/core/wangp_agent.py'),          'wangp_agent'),
    (Path('C:/gaon/core/script_gen.py'),           'script_gen'),
    (Path('C:/gaon/core/kling_agent.py'),          'kling_agent'),
    (Path('C:/gaon/core/thumbnail_gen.py'),        'thumbnail_gen'),
    (Path('C:/gaon/ops/daily_health_check.py'),    'daily_health_check'),
    (Path('C:/gaon/ops/pipeline_runner.py'),       'pipeline_runner'),
    (Path('C:/gaon/setup/create_symlinks.py'),     'create_symlinks'),
    (Path('D:/1인기업/01_youtube/scripts/youtube_uploader.py'), 'youtube_uploader'),
    (Path('D:/1인기업/06_blog/scripts/blog_poster.py'),         'blog_poster'),
    (Path('D:/1인기업/03_newsletter/scripts/newsletter_gen.py'),'newsletter_gen'),
    (Path('D:/1인기업/07_affiliate/scripts/affiliate_matcher.py'),'affiliate_matcher'),
]

for path, name in scripts:
    _check(name, path.exists(), str(path) if path.exists() else '없음 — 배포 필요')

# ── 최종 요약 ────────────────────────────────────────────────
print('\n' + '=' * 60)
print(f'결과: ✅ {len(results["ok"])}개 OK  '
      f'⚠️ {len(results["warn"])}개 경고  '
      f'❌ {len(results["miss"])}개 누락')

if results['miss']:
    print('\n누락 항목:')
    for m in results['miss']:
        print(f'  ❌ {m}')

# JSON 결과 저장
out_dir = Path('C:/gaon/logs')
out_dir.mkdir(parents=True, exist_ok=True)
out = out_dir / f'scan_{datetime.now().strftime("%Y%m%d_%H%M")}.json'
with open(out, 'w', encoding='utf-8') as f:
    json.dump({
        'scanned_at': datetime.now().isoformat(),
        'ok':   results['ok'],
        'warn': results['warn'],
        'miss': results['miss'],
    }, f, ensure_ascii=False, indent=2)
print(f'\n결과 저장: {out}')
print('=' * 60)

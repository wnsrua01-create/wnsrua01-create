#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명: script_gen.py
목적: 채널+EP 정보 → 130씬 YouTube 대본 JSON 자동 생성 (3단계 LLM 폴백)
작성일: 2026-05-22
설치 위치(Windows): C:/gaon/core/script_gen.py

LLM 티어:
  tier1: Gemini 2.0 Flash Free (GEMINI_API_KEY_01~13 순환)
  tier2: Gemma4 E4B via Ollama (localhost:11434)
  tier3: Claude API (ANTHROPIC_API_KEY)

사용법:
  python script_gen.py --ch senior --ep 1
  python script_gen.py --ch senior --ep 1 --dry-run
  python script_gen.py --ch all --ep-start 1 --ep-end 5
"""
import sys
import os
import json
import time
import logging
import argparse
import re
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
CONFIG_PATH  = Path('C:/gaon/config/channels.json')
LOG_DIR      = Path('C:/gaon/logs')
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'script_gen.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

GEMINI_KEY_ENV_NAMES = [f'GEMINI_API_KEY_{i:02d}' for i in range(1, 14)]
GEMINI_MODEL         = 'gemini-2.0-flash'
OLLAMA_MODEL         = 'gemma4:e4b'
CLAUDE_MODEL         = 'claude-sonnet-4-6'

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


def _load_channel_config(ch_slug: str) -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f'channels.json 파싱 오류: {e}')
        return {}
    for _, info in cfg.get('channels', {}).items():
        if info.get('slug') == ch_slug:
            return info
    return {}


def _build_prompt(ch_slug: str, ep_num: int, ch_cfg: dict) -> str:
    """130씬 대본 생성용 LLM 프롬프트."""
    name_kr  = ch_cfg.get('name_kr', ch_slug)
    topics   = ch_cfg.get('topics', [])
    tone     = ch_cfg.get('tone', '친근하고 유익한 어조')
    bg       = ch_cfg.get('background', '스튜디오')
    gender   = ch_cfg.get('gender', 'neutral')
    topic    = topics[(ep_num - 1) % len(topics)] if topics else '일반 정보'

    return f"""당신은 한국 유튜브 채널 "{name_kr}"의 대본 작가입니다.
채널 성격: {tone}
배경: {bg}
화자 성별: {gender}

EP{ep_num:02d} 주제: {topic}

아래 JSON 형식으로 130씬 대본을 작성하세요. 총 영상 길이는 약 13분(씬당 6초)입니다.

씬 구성:
- 씬 1-13: 인트로 (주제 소개, 핵심 요약 예고)
- 씬 14-50: 본론1 (주제의 핵심 내용)
- 씬 51-90: 본론2 (심화 내용, 사례, 데이터)
- 씬 91-117: 본론3 (실천 방법, 팁)
- 씬 118-130: 아웃트로 (요약, CTA, 구독 유도)

반드시 다음 JSON 형식만 출력하세요 (설명 없이):
{{
  "title": "영상 제목 (40자 이내)",
  "topic": "{topic}",
  "ch_slug": "{ch_slug}",
  "ep_num": {ep_num},
  "scenes": [
    {{
      "scene_num": 1,
      "narration": "나레이션 텍스트 (2-4문장, 자연스러운 구어체)",
      "visual_prompt": "영문 이미지 생성 프롬프트 (Stable Diffusion용, 20단어 이내)",
      "speaker": "gaon",
      "emotion": "warm"
    }}
  ]
}}

emotion 값: warm / serious / excited / calm / empathetic 중 하나
speaker 값: gaon (고정)
scenes 배열은 정확히 130개여야 합니다."""


def _parse_scenes_json(raw: str) -> Optional[dict]:
    """LLM 응답에서 JSON 추출."""
    # 마크다운 코드블록 제거
    raw = re.sub(r'```(?:json)?', '', raw).strip()
    # 첫 { 부터 마지막 } 까지
    start = raw.find('{')
    end   = raw.rfind('}')
    if start == -1 or end == -1:
        return None
    try:
        data = json.loads(raw[start:end + 1])
        if 'scenes' in data and isinstance(data['scenes'], list):
            return data
    except json.JSONDecodeError:
        pass
    return None


# ── LLM 티어 1: Gemini Flash Free ────────────────────────────────────────────

def _call_gemini(prompt: str) -> Optional[str]:
    """Gemini Flash API 호출 (13개 키 순환)."""
    import urllib.request

    for env_name in GEMINI_KEY_ENV_NAMES:
        api_key = os.environ.get(env_name, '')
        if not api_key:
            continue
        try:
            url = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent'
            payload = json.dumps({
                'contents': [{'parts': [{'text': prompt}]}],
                'generationConfig': {'temperature': 0.7, 'maxOutputTokens': 8192},
            }).encode('utf-8')
            req = urllib.request.Request(url, data=payload, headers={
                'Content-Type':  'application/json',
                'x-goog-api-key': api_key,
            })
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read())
                text = result['candidates'][0]['content']['parts'][0]['text']
                logger.info(f'[Gemini/{env_name}] 응답 성공 ({len(text)}자)')
                return text
        except Exception as e:
            logger.warning(f'[Gemini/{env_name}] 실패: {type(e).__name__}')
            time.sleep(1)

    logger.warning('[Gemini] 모든 키 소진 — tier2로 전환')
    return None


# ── LLM 티어 2: Ollama (gemma4:e4b) ──────────────────────────────────────────

def _call_ollama(prompt: str) -> Optional[str]:
    """Ollama gemma4:e4b 로컬 호출."""
    import urllib.request

    try:
        url     = 'http://localhost:11434/api/generate'
        payload = json.dumps({
            'model':  OLLAMA_MODEL,
            'prompt': prompt,
            'stream': False,
            'options': {'temperature': 0.7, 'num_predict': 8192},
        }).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read())
            text = result.get('response', '')
            logger.info(f'[Ollama/{OLLAMA_MODEL}] 응답 성공 ({len(text)}자)')
            return text
    except Exception as e:
        logger.warning(f'[Ollama] 실패: {type(e).__name__} — tier3로 전환')
        return None


# ── LLM 티어 3: Claude API ───────────────────────────────────────────────────

def _call_claude(prompt: str) -> Optional[str]:
    """Claude API 폴백."""
    import urllib.request

    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        logger.error('[Claude] ANTHROPIC_API_KEY 미설정 — 모든 LLM 소진')
        return None
    try:
        url     = 'https://api.anthropic.com/v1/messages'
        payload = json.dumps({
            'model':      CLAUDE_MODEL,
            'max_tokens': 8192,
            'messages':   [{'role': 'user', 'content': prompt}],
        }).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={
            'Content-Type':      'application/json',
            'x-api-key':         api_key,
            'anthropic-version': '2023-06-01',
        })
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            text = result['content'][0]['text']
            logger.info(f'[Claude/{CLAUDE_MODEL}] 응답 성공 ({len(text)}자)')
            return text
    except Exception as e:
        logger.error(f'[Claude] 실패: {type(e).__name__}')
        return None


# ── 대본 생성 메인 ────────────────────────────────────────────────────────────

def generate_script(ch_slug: str, ep_num: int, dry_run: bool = False) -> Optional[dict]:
    """3단계 LLM 폴백으로 130씬 대본 생성."""
    logger.info(f'대본 생성 시작: {ch_slug} EP{ep_num:02d}')
    ch_cfg = _load_channel_config(ch_slug)
    if not ch_cfg:
        logger.error(f'채널 설정 없음: {ch_slug}')

    if dry_run:
        logger.info('[dry-run] 더미 대본 생성')
        return _make_dummy_script(ch_slug, ep_num, ch_cfg)

    prompt  = _build_prompt(ch_slug, ep_num, ch_cfg)
    callers = [
        ('Gemini', _call_gemini),
        ('Ollama', _call_ollama),
        ('Claude', _call_claude),
    ]

    for tier_name, caller in callers:
        raw = caller(prompt)
        if not raw:
            continue
        data = _parse_scenes_json(raw)
        if data and len(data.get('scenes', [])) >= 100:
            logger.info(f'[{tier_name}] 씬 {len(data["scenes"])}개 파싱 성공')
            data['generated_by'] = tier_name
            data['generated_at'] = datetime.now().isoformat()
            return data
        logger.warning(f'[{tier_name}] JSON 파싱 실패 또는 씬 부족')

    logger.error('모든 LLM 실패 — 더미 대본으로 대체')
    return _make_dummy_script(ch_slug, ep_num, ch_cfg)


def _make_dummy_script(ch_slug: str, ep_num: int, ch_cfg: dict) -> dict:
    """LLM 전체 실패 시 최소 구조 더미 대본."""
    topics   = ch_cfg.get('topics', ['일반 정보'])
    topic    = topics[(ep_num - 1) % len(topics)]
    name_kr  = ch_cfg.get('name_kr', ch_slug)
    scenes   = []
    for i in range(1, 131):
        if i <= 13:
            section = 'intro'
        elif i <= 117:
            section = 'body'
        else:
            section = 'outro'
        scenes.append({
            'scene_num':     i,
            'narration':     f'[{section}] {topic} 씬 {i} — {name_kr} EP{ep_num:02d}',
            'visual_prompt': f'{topic} scene {i}, Korean style, cinematic',
            'speaker':       'gaon',
            'emotion':       'calm',
        })
    return {
        'title':        f'{name_kr} EP{ep_num:02d} — {topic}',
        'topic':        topic,
        'ch_slug':      ch_slug,
        'ep_num':       ep_num,
        'scenes':       scenes,
        'generated_by': 'dummy',
        'generated_at': datetime.now().isoformat(),
    }


def save_script(script: dict, ch_slug: str, ep_num: int) -> Path:
    """대본 JSON 저장."""
    ch_num = next((k for k, v in CHANNEL_SLUGS.items() if v == ch_slug), 'ch01')
    num    = int(ch_num[2:])
    ep_str = f'ep{ep_num:02d}'
    out_dir = ROOT_SCRIPTS / f'ch{num:02d}_{ch_slug}' / ep_str
    out_dir.mkdir(parents=True, exist_ok=True)

    out = out_dir / f'{ep_str}_data.json'
    # 기존 파일 백업 (규칙 8)
    if out.exists():
        bak = out.with_suffix('.json.bak')
        import shutil
        shutil.copy2(out, bak)
        logger.info(f'기존 대본 백업: {bak.name}')

    with open(out, 'w', encoding='utf-8') as f:
        json.dump(script, f, ensure_ascii=False, indent=2)
    logger.info(f'대본 저장 완료: {out}')
    return out


def run(ch_slug: str, ep_num: int, dry_run: bool = False) -> dict:
    script = generate_script(ch_slug, ep_num, dry_run)
    if not script:
        return {'ok': False, 'path': ''}
    path = save_script(script, ch_slug, ep_num)
    return {
        'ok':         True,
        'path':       str(path),
        'scenes':     len(script.get('scenes', [])),
        'title':      script.get('title', ''),
        'generated_by': script.get('generated_by', ''),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='GAONIX 대본 자동 생성')
    parser.add_argument('--ch', required=True, help='채널 슬러그 또는 all')
    parser.add_argument('--ep', type=int, help='에피소드 번호 (단일)')
    parser.add_argument('--ep-start', type=int, default=1, help='배치 시작 EP')
    parser.add_argument('--ep-end',   type=int, default=1, help='배치 종료 EP')
    parser.add_argument('--dry-run', action='store_true', help='더미 대본 생성 (LLM 호출 없음)')
    args = parser.parse_args()

    valid_slugs = set(CHANNEL_SLUGS.values())
    if args.ch == 'all':
        slugs = sorted(valid_slugs)
    elif args.ch in valid_slugs:
        slugs = [args.ch]
    else:
        parser.error(f'알 수 없는 채널: {args.ch!r}')

    ep_list = [args.ep] if args.ep else list(range(args.ep_start, args.ep_end + 1))
    for ep_num in ep_list:
        if not (1 <= ep_num <= 9999):
            parser.error(f'EP 범위 오류: {ep_num}')

    total_ok, total_fail = 0, 0
    for slug in slugs:
        for ep_num in ep_list:
            result = run(slug, ep_num, args.dry_run)
            status = '✅' if result['ok'] else '❌'
            print(f'{status} [{slug}] EP{ep_num:02d}: {result.get("title", "")} ({result.get("scenes", 0)}씬, {result.get("generated_by", "")})')
            if result['ok']:
                total_ok += 1
            else:
                total_fail += 1

    print(f'\n완료: {total_ok}개 성공 / {total_fail}개 실패')

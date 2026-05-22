# GAON NEXUS — 현황 종합 보고서
> 작성일: 2026-05-21 | 환경: Claude Code (원격 Linux) ↔ 실제 운영: Windows 11

---

## 1. 현재 실행 환경 이해

```
┌─────────────────────────────────────────────────────────┐
│  Claude Code 원격 환경 (Linux, 이 화면)                  │
│  /home/user/wnsrua01-create/  ← Git 저장소               │
│                                                          │
│  ✅ 할 수 있는 것: 코드 작성, 검증, 커밋, 푸시           │
│  ❌ 할 수 없는 것: Windows 실행, 실제 API 호출           │
└────────────────────┬────────────────────────────────────┘
                     │ git pull
                     ▼
┌─────────────────────────────────────────────────────────┐
│  해피진 Windows 11 (실제 운영 PC)                        │
│  C:\gaon\       ← 코드 루트                              │
│  D:\gaon_data\  ← 영상/대본 데이터                       │
│  D:\1인기업\    ← GAONIX 사업 폴더                       │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Claude Code가 할 수 있는 일 ✅

| 분류 | 가능한 작업 |
|------|------------|
| **코드 작성** | Python, JSON, BAT, n8n 워크플로우 파일 생성/수정 |
| **구문 검증** | AST 파싱으로 문법 오류 100% 사전 차단 |
| **로직 검증** | mock/임시 디렉토리로 핵심 함수 단위 테스트 |
| **Git 관리** | 커밋, 푸시, PR 생성, 브랜치 관리 |
| **PR 모니터링** | CI 실패/리뷰 코멘트 감지 후 자동 대응 |
| **문서 작성** | 설계서, 가이드, 체크리스트 작성 |
| **코드 분석** | 기존 코드 리뷰, 버그 탐지, 개선안 제시 |
| **아키텍처 설계** | 폴더 구조, API 인터페이스, 워크플로우 설계 |

---

## 3. Claude Code가 할 수 없는 일 ❌

| 분류 | 불가능한 이유 | 대안 |
|------|-------------|------|
| **Windows 경로 실행** | Linux 환경 — `C:\`, `D:\` 없음 | Git pull 후 Windows에서 실행 |
| **실제 한글 경로 테스트** | CP949 인코딩 환경 재현 불가 | Windows에서 `path_utils.py` 자가테스트 실행 |
| **WanGP API 연결** | `http://localhost:8080` 서버 없음 | Windows에서 `wangp_agent.py --check` 실행 |
| **Discord 실발송** | Webhook URL 없음 | `.env` 설정 후 Windows에서 테스트 |
| **YouTube API 실호출** | 인증 파일(`yt_credentials.json`) 없음 | Google Cloud Console에서 OAuth 설정 |
| **FFmpeg 영상 처리** | 이 환경에 FFmpeg/영상 파일 없음 | Windows에서 `shorts_extractor.py` 실행 |
| **ComfyUI/Ollama** | 로컬 GPU 서버 연결 불가 | Windows 직접 실행 |
| **n8n 워크플로우 실행** | Docker 컨테이너 접근 불가 | n8n UI에서 JSON 임포트 |
| **실제 PDF 생성** | `reportlab` 미설치 + 한글 폰트 없음 | Windows에서 `pip install reportlab` 후 실행 |

---

## 4. 완료된 작업 현황 ✅

### P0 — 즉시 (완료)

| 파일 | 위치 | 상태 |
|------|------|------|
| `path_utils.py` | `gaon/utils/` | ✅ 완료 · 검증 ALL PASS |
| `wangp_agent.py` | `gaon/core/` | ✅ 완료 · 구조 검증 PASS |
| `create_business_dirs.py` | `gaon/setup/` | ✅ 완료 · 41개 폴더 생성 검증 |

### P1 — 단기 (완료)

| 파일 | 위치 | 상태 |
|------|------|------|
| `shorts_extractor.py` | `business/02_shorts/scripts/` | ✅ 완료 · 타임스탬프 로직 검증 |
| `discord_notify.py` | `gaon/utils/` | ✅ 완료 · 11종 템플릿 검증 |
| `n8n_business_workflow.json` | `business/09_tools/` | ✅ 완료 · n8n 임포트용 |

### P2 — 중기 (완료)

| 파일 | 위치 | 상태 |
|------|------|------|
| `ebook_gen.py` | `business/04_ebooks/scripts/` | ✅ 완료 · 씬 범위 로직 검증 |
| `performance_loop.py` | `gaon/analytics/` | ✅ 완료 · 4가지 규칙 검증 |

---

## 5. 지금 당장 해야 할 일 (Windows에서 해피진이 직접) 🔴

### Step 1 — Git Pull (오늘)
```batch
cd C:\gaon
git pull origin claude/coding-session-wN8cW
```

### Step 2 — P0-A: 한글 경로 유틸 적용 (오늘)
```batch
REM 자가 테스트 실행
D:\programs\python.exe C:\gaon\utils\path_utils.py
REM 예상 출력: === ALL TESTS PASSED ===
```

### Step 3 — P0-C: 1인기업 폴더 생성 (오늘)
```batch
D:\programs\python.exe C:\gaon\setup\create_business_dirs.py
REM D:\1인기업\ 41개 폴더 자동 생성
```

### Step 4 — Discord 알림 설정 (오늘)
```
C:\gaon\.env 파일 생성:
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN
```
```batch
D:\programs\python.exe C:\gaon\utils\discord_notify.py --test
```

### Step 5 — WanGP 연결 확인 (WanGP 서버 기동 후)
```batch
D:\programs\python.exe C:\gaon\core\wangp_agent.py --check
REM 예상 출력: WanGP 상태: ✅ 정상 / URL: http://localhost:8080
```

### Step 6 — n8n 워크플로우 임포트
```
n8n UI (http://localhost:5678) →
  Settings → Import Workflow →
  business/09_tools/n8n_business_workflow.json 선택
```

### Step 7 — Shorts 추출 테스트 (완성본 있는 경우)
```batch
D:\programs\python.exe D:\1인기업\02_shorts\scripts\shorts_extractor.py ^
  --ch senior --ep 1
REM D:\1인기업\02_shorts\clips\ 에 3개 Shorts 생성
```

### Step 8 — 전자책 생성 (배치 완성 후)
```batch
pip install reportlab
D:\programs\python.exe D:\1인기업\04_ebooks\scripts\ebook_gen.py ^
  --ch senior --batch-start 1
```

---

## 6. 앞으로 Claude Code가 추가로 만들 수 있는 것 🟡

| 우선순위 | 파일 | 내용 |
|---------|------|------|
| 🔴 높음 | `gaon/config/channels.json` | 17채널 전체 설정 (채널ID, 슬러그, 성별, 톤 프리셋) |
| 🔴 높음 | `gaon/ops/daily_health_check.py` | 매일 09:00 자동 헬스체크 + Discord 리포트 |
| 🔴 높음 | `gaon/setup/gaon_link_setup.bat` | 심볼릭 링크 자동 생성 배치 (관리자 권한) |
| 🟠 중간 | `gaon/utils/channels_config.py` | 채널별 tone/background 프리셋 (YouTube 차별화) |
| 🟠 중간 | `business/06_blog/scripts/blog_poster.py` | 네이버/티스토리 자동 포스팅 |
| 🟠 중간 | `business/03_newsletter/scripts/newsletter_gen.py` | 뉴스레터 자동 생성 |
| 🟠 중간 | `business/07_affiliate/scripts/affiliate_matcher.py` | 쿠팡파트너스 키워드 자동 매핑 |
| 🟡 낮음 | `gaon/analytics/ab_test_manager.py` | 썸네일 A/B 테스트 자동화 |
| 🟡 낮음 | `gaon/core/assembly_agent.py` | FFmpeg 조립 에이전트 모듈화 |
| 🟡 낮음 | `business/05_smartstore/scripts/smartstore_writer.py` | 스마트스토어 상품설명 자동 생성 |

---

## 7. 해결 불가 항목 (외부 의존) ⚫

| 항목 | 이유 | 필요 조건 |
|------|------|----------|
| **Grok I2V 병목** | 계정 정책 — 100편/24h 한도 | WanGP 로컬 완전 가동으로 대체 (P0-B) |
| **YouTube 수익화** | 1,000 구독자 조건 | 채널별 콘텐츠 축적 후 신청 |
| **쿠팡파트너스 API** | API 승인 대기 중 (AF7354598) | 쿠팡 파트너스 센터 승인 대기 |
| **Chrome CDP 취약성** | Grok UI 변경 시 selector 무효화 | WanGP 전환 완료 후 의존도 제거 |
| **NAS EUC-KR 인코딩** | Z:\ 드라이브 하드웨어 설정 | Python Path 객체 사용 시 우회 가능 |

---

## 8. 작업 로드맵 요약

```
현재 (2026-05-21)
  ✅ P0~P2 코드 전체 작성 완료 (GitHub PR #5)
  ✅ 구문/로직 검증 7/7 PASS
  ⏳ Windows 실환경 테스트 대기 중

이번 주 (해피진 직접 실행)
  □ git pull → path_utils.py 자가테스트
  □ create_business_dirs.py → D:\1인기업\ 생성
  □ discord_notify.py --test → 알림 확인
  □ wangp_agent.py --check → WanGP 연결 확인

다음 주 (Claude Code 추가 작성)
  □ channels.json + daily_health_check.py
  □ gaon_link_setup.bat (심볼릭 링크)
  □ blog_poster.py + newsletter_gen.py

1개월 후
  □ YouTube Shorts 파이프라인 실가동
  □ 쿠팡파트너스 API 연동 (승인 후)
  □ 17채널 배치2 동시 가동
```

---

> **핵심 원칙**: Claude Code는 "설계·작성·검증·버전관리" 담당.
> Windows 실행·API 연결·실데이터 처리는 해피진이 직접 수행.
> 두 환경의 역할을 명확히 나눠야 효율적으로 협업 가능합니다.

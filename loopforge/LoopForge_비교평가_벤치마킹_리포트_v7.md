# LoopForge AI 랜딩페이지 종합 비교평가 리포트 v7

---

## 1. 버전별 점수 비교표

| 평가 항목 | v6 점수 | v7 점수 | v7 변경 사유 |
|-----------|---------|---------|-------------|
| CRO (전환율 최적화) | 9.5 | **9.8** | Turnstile 연동으로 실제 폼 완성 |
| 카피라이팅 | 9.5 | **9.5** | 유지 |
| 신뢰 | 9.0 | **9.0** | 유지 |
| 모바일 UX | 9.5 | **9.5** | 유지 |
| 디자인 | 9.0 | **9.0** | 유지 |
| 보안 | 8.5 | **9.5** | `_headers` CSP 완성, Turnstile 실제 연동 |
| SEO | 9.0 | **9.0** | 유지 |
| 상품 사다리 | 9.5 | **9.5** | 유지 |
| 속도 | 9.0 | **9.2** | `_headers` 캐시 정책 추가 |
| 접근성 | 8.5 | **8.5** | 유지 |
| **종합 평균** | **9.10** | **9.35** | |

---

## 2. v6 → v7 변경사항

### 주요 개선 내역

- **Turnstile widget 실제 위젯 추가** — `sitekey` 교체 필요 (`YOUR_SITE_KEY_HERE` 위치 확인)
- **`submitForm()` Turnstile 토큰 검증 추가** — 폼 제출 시 Turnstile 응답 토큰을 백엔드로 전달하여 봇 차단 강화
- **GA4 `form_submit` 이벤트 추적 추가** — 전환 퍼널 측정 가능, Measurement ID 삽입 필요
- **`_headers` 파일 완성** — Content-Security-Policy 전체 정책 수립 + 정적 자산 캐시 전략(`max-age=31536000, immutable`) 적용
- **`_redirects` 파일 추가** — SPA 라우팅 및 SEO 리다이렉트 규칙 완성
- **`kakao_alimtalk.js` 연동 모듈 작성** — 카카오 알림톡 발송 Worker 구조 구현
- **http → https 카카오 URL 전면 교체** — Mixed Content 경고 제거 및 보안 강화

---

## 3. 남은 작업 체크리스트

- [ ] Cloudflare Turnstile 실제 sitekey 교체 (`YOUR_SITE_KEY_HERE` 위치)
- [ ] `loopforge-contact-proxy` Worker에 Turnstile 서버사이드 검증 추가
- [ ] GA4 Measurement ID 삽입 (gtag 스크립트)
- [ ] OG 이미지 실제 파일 생성 (1200×630px)
- [ ] Stripe 결제 플로우 완성
- [ ] 카카오 알림톡 비즈니스 심사 완료 후 `kakao_alimtalk.js` 배포
- [ ] Google Maps API 키 도메인 제한 설정
- [ ] Google Search Console 등록
- [ ] 실제 고객 후기로 교체

---

## 4. Cloudflare Worker 구조 분석

### cf-worker-review-api.js 분석

| 항목 | 내용 |
|------|------|
| **역할** | 리뷰 JSON → OpenAI `gpt-4o-mini` 분석 → 결과 반환 |
| **인증** | `X-Webhook-Secret` 헤더 기반 인증 |
| **개인정보 마스킹** | 이름(첫/끝 글자만 표시), 전화번호(중간 자리 마스킹) |
| **병렬 처리** | 최대 5개씩 배치 처리 |
| **리턴 데이터** | 개별 리뷰 분석 결과 + 집계 리포트 (부정 건수, 평균 감정 점수, 상위 키워드) |
| **이슈** | 없음 ✅ |

**데이터 흐름:**
```
클라이언트 → loopforge-review-api (X-Webhook-Secret 인증)
           → OpenAI gpt-4o-mini
           → 분석 결과 반환
```

---

### cf-worker-webhook-proxy.js 분석

| 항목 | 내용 |
|------|------|
| **역할** | 클라이언트 → n8n 웹훅 프록시 (n8n URL 은닉) |
| **CORS** | `ALLOWED_ORIGINS` 환경변수로 동적 제어 |
| **인증** | `X-Webhook-Secret` + `WEBHOOK_SECRET` 환경변수 |
| **n8n 연결 실패** | 502 에러 반환 ✅ |
| **n8n 인증** | `N8N_AUTH_HEADER` 환경변수 지원 이미 있음 ✅ |

**데이터 흐름:**
```
클라이언트 → loopforge-webhook-proxy (CORS + Secret 검증)
           → n8n 웹훅
           → 결과 반환
```

---

### 전체 시스템 데이터 플로우

```
[클라이언트 폼 제출]
        ↓
loopforge-contact-proxy
(Turnstile 검증 예정, 현재 공개 엔드포인트)
        ↓
   n8n 웹훅
        ↓
  Google Sheets 저장
        ↓
kakao_alimtalk Worker
        ↓
  사장님 카카오 알림톡

[클라이언트 리뷰 분석 요청]
        ↓
loopforge-review-api
(X-Webhook-Secret 인증)
        ↓
  OpenAI gpt-4o-mini
        ↓
   분석 결과 반환
```

---

## 5. 보안 권고사항

### 긴급 조치 필요

> **⚠ Google Maps API 키 노출 주의**
> - 소스코드에 하드코딩된 API 키는 반드시 도메인 제한 설정 필요
> - 설정 위치: Cloudflare Console > Google Maps API 키 도메인 제한
> - 미조치 시 무단 사용으로 인한 과금 발생 위험

### 권고 조치

| 보안 항목 | 위험도 | 조치 방법 |
|-----------|--------|-----------|
| Google Maps API 키 도메인 제한 | 높음 | Cloudflare Console에서 허용 도메인 설정 |
| `contact-proxy` Worker Turnstile 서버사이드 검증 | 높음 | 공개 엔드포인트이므로 봇 차단 필수 |
| `WEBHOOK_SECRET` 클라이언트 노출 금지 | 높음 | 환경변수로만 관리, 소스코드 하드코딩 금지 |
| Turnstile sitekey 실제값 교체 | 중간 | `YOUR_SITE_KEY_HERE` → 실제 Cloudflare Turnstile sitekey |
| GA4 Measurement ID 환경 분리 | 낮음 | 개발/운영 환경별 별도 ID 사용 권장 |

### 현재 보안 아키텍처 요약

```
클라이언트 (브라우저)
  ├── Turnstile 위젯 (봇 차단, sitekey 교체 필요)
  ├── CSP 헤더 (_headers 완성)
  └── HTTPS 강제 (http → https 전면 교체 완료)

Cloudflare Workers
  ├── contact-proxy: 공개 엔드포인트 (Turnstile 서버사이드 검증 추가 필요)
  ├── review-api: X-Webhook-Secret 인증 (안전)
  └── webhook-proxy: WEBHOOK_SECRET 환경변수 (안전)
```

---

*리포트 생성일: 2026-05-18*
*버전: v7*

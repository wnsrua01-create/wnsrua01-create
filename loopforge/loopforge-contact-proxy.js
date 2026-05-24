/**
 * LoopForge AI — Cloudflare Worker
 * loopforge-contact-proxy
 *
 * 역할: 문의 폼 수신 → Turnstile 검증 → n8n 웹훅 전달 → Google Sheets 저장
 *
 * 환경변수 (Cloudflare Dashboard > Settings > Variables):
 *   TURNSTILE_SECRET_KEY  — Cloudflare Turnstile Secret Key (Secret)
 *   N8N_WEBHOOK_URL       — n8n 웹훅 전체 URL (Secret)
 *   ALLOWED_ORIGINS       — 허용 도메인 (Variable)
 *                           예: https://loopforge-2v1.pages.dev,https://yourdomain.com
 */

const TURNSTILE_VERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify';

export default {
  async fetch(request, env, ctx) {

    // ── CORS ──────────────────────────────────────────────────
    const origin = request.headers.get('Origin') || '';
    const allowedOrigins = (env.ALLOWED_ORIGINS || '')
      .split(',').map(s => s.trim()).filter(Boolean);

    const isAllowed = allowedOrigins.length === 0
      || allowedOrigins.includes('*')
      || allowedOrigins.includes(origin);

    const corsHeaders = {
      'Access-Control-Allow-Origin': isAllowed ? (origin || '*') : 'null',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Access-Control-Max-Age': '86400',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    if (request.method !== 'POST') {
      return Response.json(
        { success: false, error: 'POST 요청만 허용됩니다.' },
        { status: 405, headers: corsHeaders }
      );
    }

    // ── 요청 파싱 ─────────────────────────────────────────────
    let body;
    try {
      body = await request.json();
    } catch {
      return Response.json(
        { success: false, error: '잘못된 JSON 형식입니다.' },
        { status: 400, headers: corsHeaders }
      );
    }

    // ── 필수 필드 검증 ────────────────────────────────────────
    const { business_name, business_type, contact, turnstile_token } = body;

    if (!business_name || !business_type || !contact) {
      return Response.json(
        { success: false, error: '업체명, 업종, 연락처는 필수입니다.' },
        { status: 400, headers: corsHeaders }
      );
    }

    // ── Turnstile 서버사이드 검증 ─────────────────────────────
    if (!env.TURNSTILE_SECRET_KEY) {
      // 개발/테스트 환경에서 TURNSTILE_SECRET_KEY 미설정 시 경고만 출력
      console.warn('[TURNSTILE] TURNSTILE_SECRET_KEY 환경변수가 설정되지 않았습니다.');
    } else {
      if (!turnstile_token) {
        return Response.json(
          { success: false, error: '보안 검증 토큰이 없습니다. 페이지를 새로고침 후 다시 시도해주세요.' },
          { status: 400, headers: corsHeaders }
        );
      }

      // Cloudflare Turnstile 검증 API 호출
      const clientIP = request.headers.get('CF-Connecting-IP') || '';
      const verifyForm = new FormData();
      verifyForm.append('secret', env.TURNSTILE_SECRET_KEY);
      verifyForm.append('response', turnstile_token);
      if (clientIP) verifyForm.append('remoteip', clientIP);

      let turnstileResult;
      try {
        const verifyResp = await fetch(TURNSTILE_VERIFY_URL, {
          method: 'POST',
          body: verifyForm,
        });
        turnstileResult = await verifyResp.json();
      } catch (err) {
        console.error('[TURNSTILE] 검증 API 호출 실패:', err.message);
        return Response.json(
          { success: false, error: '보안 검증 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.' },
          { status: 503, headers: corsHeaders }
        );
      }

      if (!turnstileResult.success) {
        console.warn('[TURNSTILE] 검증 실패:', turnstileResult['error-codes']);
        return Response.json(
          { success: false, error: '보안 검증에 실패했습니다. 페이지를 새로고침 후 다시 시도해주세요.' },
          { status: 403, headers: corsHeaders }
        );
      }
    }

    // ── n8n 웹훅 전달 ─────────────────────────────────────────
    if (!env.N8N_WEBHOOK_URL) {
      console.error('[N8N] N8N_WEBHOOK_URL 환경변수가 설정되지 않았습니다.');
      return Response.json(
        { success: false, error: '서버 설정 오류입니다. 잠시 후 다시 시도해주세요.' },
        { status: 503, headers: corsHeaders }
      );
    }

    // turnstile_token은 n8n으로 전달하지 않음 (보안)
    const { turnstile_token: _removed, ...safeBody } = body;

    let n8nResp;
    try {
      n8nResp = await fetch(env.N8N_WEBHOOK_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'User-Agent': 'LoopForge-Contact-Proxy/1.0',
        },
        body: JSON.stringify({
          ...safeBody,
          forwarded_ip: request.headers.get('CF-Connecting-IP') || '',
          country: request.headers.get('CF-IPCountry') || '',
        }),
      });
    } catch (err) {
      console.error('[N8N] 전달 실패:', err.message);
      return Response.json(
        { success: false, error: 'n8n 서버 연결 실패. 카카오 채널로 직접 문의해 주세요.' },
        { status: 502, headers: corsHeaders }
      );
    }

    // n8n 응답 그대로 전달
    const responseText = await n8nResp.text();
    let responseData;
    try {
      responseData = JSON.parse(responseText);
    } catch {
      responseData = { success: true };
    }

    return Response.json(
      { success: true, ...responseData },
      { status: 200, headers: corsHeaders }
    );
  },
};

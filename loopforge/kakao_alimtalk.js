/**
 * LoopForge AI — Kakao Alimtalk Cloudflare Worker
 * =================================================
 * 카카오 비즈메시지(알림톡) API를 통해 사장님 알림 및 고객 확인 메시지를 발송합니다.
 *
 * 필수 환경 변수 (Cloudflare Dashboard → Workers → Settings → Variables):
 *   KAKAO_ACCESS_TOKEN  : 카카오 비즈메시지 REST API 액세스 토큰
 *   KAKAO_SENDER_KEY    : 알림톡 채널의 발신 프로필 키 (senderKey)
 *   KAKAO_PLUS_FRIEND_ID: 카카오 플러스친구 ID (예: @loopforge)
 *   OWNER_PHONE         : 사장님(운영자) 휴대폰 번호 (예: 01012345678, 하이픈 없이)
 *
 * ─────────────────────────────────────────────────────────────
 * n8n HTTP Request 노드 연동 방법
 * ─────────────────────────────────────────────────────────────
 * 1. n8n 워크플로우에서 "HTTP Request" 노드를 추가합니다.
 * 2. Method: POST
 * 3. URL: https://<your-worker-subdomain>.workers.dev/n8n
 *    (이 Worker를 Cloudflare Pages/Workers에 배포한 후 URL을 입력하세요)
 * 4. Body Content Type: JSON
 * 5. Body (JSON):
 *    {
 *      "contact": "{{ $json.contact }}",
 *      "business_name": "{{ $json.business_name }}",
 *      "business_type": "{{ $json.business_type }}",
 *      "review_sample": "{{ $json.review_sample }}"
 *    }
 *    (웹훅 폼 제출 데이터를 그대로 매핑합니다)
 * 6. Authentication: None (필요시 Authorization 헤더에 Bearer 토큰 추가)
 * 7. 응답 성공 시 { success: true, owner: {...}, user: {...} } 를 반환합니다.
 *
 * 직접 호출 방법 (curl 예시):
 *   curl -X POST https://<worker-url> \
 *     -H "Content-Type: application/json" \
 *     -d '{"to":"01012345678","template_code":"REVIEW_OWNER_01","variables":{"#{업체명}":"블루문 카페"},"type":"owner_notify"}'
 * ─────────────────────────────────────────────────────────────
 */

// ─── 카카오 비즈메시지 API 기본 URL ──────────────────────────────────────────
const KAKAO_API_BASE = 'https://kakaoapi.aligo.in/akv10/alimtalk/send/';

/**
 * 카카오 알림톡 API 호출 함수
 * @param {object} env        - Cloudflare Worker 환경 변수 바인딩
 * @param {string} to         - 수신자 휴대폰 번호 (하이픈 없이, 예: 01012345678)
 * @param {string} templateCode - 카카오 알림톡 템플릿 코드
 * @param {object} variables  - 템플릿 변수 객체 (예: { "#{업체명}": "블루문 카페" })
 * @returns {Promise<object>} - API 응답 JSON
 */
async function sendAlimtalk(env, to, templateCode, variables) {
  // 템플릿 변수를 카카오 API 형식의 문자열로 변환합니다.
  // 예: { "#{업체명}": "블루문 카페" } → "#{업체명}": "블루문 카페"
  const templateParams = Object.entries(variables)
    .map(([key, value]) => `"${key}": "${String(value).replace(/"/g, '\\"')}"`)
    .join(', ');

  // 카카오 비즈메시지 API는 multipart/form-data 형식으로 요청합니다.
  const formData = new FormData();
  formData.append('apikey', env.KAKAO_ACCESS_TOKEN);       // API 인증 키
  formData.append('userid', env.KAKAO_PLUS_FRIEND_ID);    // 플러스친구 아이디
  formData.append('senderkey', env.KAKAO_SENDER_KEY);     // 발신 프로필 키
  formData.append('tpl_code', templateCode);              // 알림톡 템플릿 코드
  formData.append('sender', env.OWNER_PHONE);             // 발신자 번호 (채널 등록 번호)
  formData.append('receiver_1', to);                      // 수신자 번호
  formData.append('subject_1', '알림');                   // 메시지 제목 (내부용)
  formData.append('message_1', buildTemplateMessage(templateCode, variables)); // 메시지 본문
  formData.append('failover', 'N');                       // 실패 시 SMS 대체 발송 여부

  // 카카오 알림톡 API에 POST 요청을 보냅니다.
  const response = await fetch(KAKAO_API_BASE, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    // HTTP 레벨 오류 처리
    const errorText = await response.text();
    throw new Error(`카카오 API HTTP 오류 ${response.status}: ${errorText}`);
  }

  const result = await response.json();

  // 카카오 API는 HTTP 200이어도 result_code가 0이 아니면 실패입니다.
  if (result.result_code !== 0 && result.result_code !== '0') {
    throw new Error(`카카오 API 오류 (code ${result.result_code}): ${result.message}`);
  }

  return result;
}

/**
 * 템플릿 코드와 변수로 알림톡 메시지 본문을 조립합니다.
 * 실제 운영 시에는 카카오 비즈니스 채널에서 심사 승인된 템플릿 내용을 그대로 사용해야 합니다.
 *
 * @param {string} templateCode - 카카오 알림톡 템플릿 코드
 * @param {object} variables    - 템플릿에 삽입할 변수 객체
 * @returns {string} - 완성된 메시지 본문 문자열
 */
function buildTemplateMessage(templateCode, variables) {
  // 기본 템플릿 맵 — 카카오 채널 심사에서 승인된 실제 템플릿 내용으로 교체하세요.
  const templates = {
    // 사장님(운영자)에게 보내는 신규 문의 알림 템플릿
    REVIEW_OWNER_NOTIFY: [
      '[LoopForge AI] 새 무료 진단 신청이 도착했습니다.',
      '',
      '업체명: #{업체명}',
      '업종: #{업종}',
      '연락처: #{연락처}',
      '리뷰 샘플: #{리뷰샘플}',
      '',
      '24시간 내 연락해 주세요.',
    ].join('\n'),

    // 고객(신청자)에게 보내는 접수 확인 템플릿
    REVIEW_USER_CONFIRM: [
      '[LoopForge AI] 무료 진단 신청이 접수되었습니다.',
      '',
      '안녕하세요, #{업체명} 사장님!',
      '무료 진단 신청이 정상적으로 접수되었습니다.',
      '24시간 내에 입력하신 연락처(#{연락처})로 연락드리겠습니다.',
      '',
      '카카오 채널로 바로 문의하시려면 아래 링크를 이용해 주세요.',
      'https://pf.kakao.com/_wLasX/chat',
    ].join('\n'),
  };

  // 선택된 템플릿 문자열 가져오기 (없으면 빈 문자열)
  let message = templates[templateCode] || '';

  // 변수 치환: #{변수명} 형식을 실제 값으로 교체합니다.
  for (const [key, value] of Object.entries(variables)) {
    // key가 이미 #{...} 형식인 경우와 아닌 경우 모두 처리합니다.
    const placeholder = key.startsWith('#{') ? key : `#{${key}}`;
    message = message.split(placeholder).join(String(value));
  }

  return message;
}

/**
 * CORS 헤더를 포함한 JSON 응답을 생성합니다.
 * @param {object|string} body   - 응답 본문 (객체는 자동으로 JSON 직렬화됨)
 * @param {number} status        - HTTP 상태 코드 (기본값: 200)
 * @returns {Response}
 */
function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      // CORS: 모든 출처 허용 (필요에 따라 특정 도메인으로 제한하세요)
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    },
  });
}

/**
 * n8n 스타일 웹훅 바디를 받아 사장님 알림과 고객 확인 메시지를 동시에 발송하는 헬퍼 함수.
 *
 * n8n HTTP Request 노드에서 이 Worker의 /n8n 경로로 POST 요청을 보내면
 * 아래 함수가 호출되어 두 종류의 알림톡을 자동으로 발송합니다.
 *
 * @param {object} env  - Cloudflare Worker 환경 변수 바인딩
 * @param {object} body - n8n 웹훅 바디
 *   @param {string} body.contact       - 고객 연락처 (휴대폰 번호 또는 카카오 ID)
 *   @param {string} body.business_name - 업체명
 *   @param {string} body.business_type - 업종
 *   @param {string} [body.review_sample] - 리뷰 샘플 (선택)
 * @returns {Promise<object>} - { ownerResult, userResult } 또는 오류 정보
 */
export async function n8nWebhookHandler(env, body) {
  const { contact, business_name, business_type, review_sample } = body;

  // 연락처에서 숫자만 추출하여 휴대폰 번호 형식으로 정리합니다.
  // 카카오 ID가 입력된 경우에는 사장님 번호(OWNER_PHONE)로만 알림을 보냅니다.
  const isPhoneNumber = /^[0-9]{10,11}$/.test(contact.replace(/[-\s]/g, ''));
  const cleanPhone = contact.replace(/[-\s]/g, '');

  // 공통 템플릿 변수
  const commonVars = {
    '#{업체명}': business_name || '(업체명 없음)',
    '#{업종}': business_type || '(업종 없음)',
    '#{연락처}': contact || '(연락처 없음)',
    '#{리뷰샘플}': review_sample
      ? review_sample.slice(0, 100) + (review_sample.length > 100 ? '…' : '')
      : '(샘플 없음)',
  };

  // 1단계: 사장님에게 신규 문의 알림 발송
  // 운영자 전화번호(OWNER_PHONE)로 항상 발송됩니다.
  const ownerResult = await sendAlimtalk(
    env,
    env.OWNER_PHONE,
    'REVIEW_OWNER_NOTIFY',
    commonVars
  );

  // 2단계: 고객에게 접수 확인 메시지 발송
  // 고객이 유효한 휴대폰 번호를 입력한 경우에만 발송합니다.
  // 카카오 ID만 입력한 경우에는 userResult를 null로 설정합니다.
  let userResult = null;
  if (isPhoneNumber) {
    userResult = await sendAlimtalk(
      env,
      cleanPhone,
      'REVIEW_USER_CONFIRM',
      commonVars
    );
  }

  return { ownerResult, userResult };
}

/**
 * Cloudflare Worker 기본 핸들러 (fetch event)
 * 모든 HTTP 요청의 진입점입니다.
 */
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // ── CORS Preflight 요청 처리 ─────────────────────────────────────────────
    // 브라우저가 실제 요청 전에 보내는 OPTIONS 요청에 CORS 헤더를 응답합니다.
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        status: 204,
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'POST, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type, Authorization',
          'Access-Control-Max-Age': '86400',
        },
      });
    }

    // ── POST 요청만 허용 ──────────────────────────────────────────────────────
    if (request.method !== 'POST') {
      return jsonResponse({ success: false, error: 'POST 요청만 허용됩니다.' }, 405);
    }

    // ── 요청 본문 파싱 ────────────────────────────────────────────────────────
    let body;
    try {
      body = await request.json();
    } catch (e) {
      return jsonResponse({ success: false, error: '유효하지 않은 JSON 본문입니다.' }, 400);
    }

    // ── 라우팅: /n8n 경로 → n8n 웹훅 핸들러 ─────────────────────────────────
    if (url.pathname === '/n8n') {
      // n8n HTTP Request 노드에서 호출되는 전용 엔드포인트입니다.
      // 필수 필드 검증
      if (!body.contact || !body.business_name) {
        return jsonResponse(
          { success: false, error: 'contact, business_name 필드는 필수입니다.' },
          400
        );
      }

      try {
        const result = await n8nWebhookHandler(env, body);
        return jsonResponse({ success: true, ...result });
      } catch (err) {
        // 카카오 API 호출 실패 시 오류 메시지 반환
        console.error('[n8n handler error]', err.message);
        return jsonResponse(
          { success: false, error: err.message },
          502
        );
      }
    }

    // ── 기본 라우팅: 직접 알림톡 발송 ────────────────────────────────────────
    // POST / 또는 POST /send 로 호출 시 단건 알림톡을 발송합니다.
    //
    // 요청 바디 형식:
    // {
    //   "to": "01012345678",          // 수신자 전화번호 (필수)
    //   "template_code": "REVIEW_OWNER_NOTIFY", // 템플릿 코드 (필수)
    //   "variables": { "#{업체명}": "블루문 카페" }, // 템플릿 변수 (선택)
    //   "type": "owner_notify"        // 발송 유형: "owner_notify" | "user_confirm"
    // }

    // 필수 필드 검증
    if (!body.to || !body.template_code) {
      return jsonResponse(
        {
          success: false,
          error: 'to(수신자 번호)와 template_code(템플릿 코드)는 필수입니다.',
        },
        400
      );
    }

    // 발송 유형에 따른 수신자 번호 결정
    // type이 "owner_notify"인 경우 환경 변수의 OWNER_PHONE을 사용합니다.
    const recipientPhone =
      body.type === 'owner_notify' ? env.OWNER_PHONE : body.to;

    // 수신자 번호 유효성 검사 (숫자 10~11자리)
    const normalizedPhone = recipientPhone.replace(/[-\s]/g, '');
    if (!/^[0-9]{10,11}$/.test(normalizedPhone)) {
      return jsonResponse(
        {
          success: false,
          error: `유효하지 않은 전화번호 형식입니다: ${recipientPhone}`,
        },
        400
      );
    }

    // 카카오 알림톡 발송 실행
    try {
      const result = await sendAlimtalk(
        env,
        normalizedPhone,
        body.template_code,
        body.variables || {}
      );
      return jsonResponse({ success: true, result });
    } catch (err) {
      // 카카오 API 오류 또는 네트워크 오류 처리
      console.error('[sendAlimtalk error]', err.message);
      return jsonResponse(
        { success: false, error: err.message },
        502
      );
    }
  },
};

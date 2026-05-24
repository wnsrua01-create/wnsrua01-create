/**
 * LoopForge AI — OG 이미지 생성 스크립트 (Node.js)
 *
 * 사용법:
 *   node generate-og-image.js
 *
 * 출력: og-image.png (1200×630px)
 *
 * 설치:
 *   npm install canvas
 */

const { createCanvas } = require('canvas');
const fs = require('fs');

const W = 1200, H = 630;
const canvas = createCanvas(W, H);
const ctx = canvas.getContext('2d');

// ── 배경 ──────────────────────────────────────────────────────
const bg = ctx.createLinearGradient(0, 0, W, H);
bg.addColorStop(0, '#080c10');
bg.addColorStop(1, '#0d1117');
ctx.fillStyle = bg;
ctx.fillRect(0, 0, W, H);

// 액센트 글로우 (좌상단)
const glow = ctx.createRadialGradient(300, 100, 0, 300, 100, 500);
glow.addColorStop(0, 'rgba(0,229,160,0.15)');
glow.addColorStop(1, 'rgba(0,229,160,0)');
ctx.fillStyle = glow;
ctx.fillRect(0, 0, W, H);

// ── 로고 ──────────────────────────────────────────────────────
ctx.font = 'bold 52px -apple-system, sans-serif';
ctx.fillStyle = '#f2f4f7';
ctx.fillText('Loop', 80, 120);
const loopWidth = ctx.measureText('Loop').width;
ctx.fillStyle = '#00E5A0';
ctx.fillText('Forge', 80 + loopWidth, 120);
ctx.fillStyle = '#f2f4f7';
ctx.fillText(' AI', 80 + loopWidth + ctx.measureText('Forge').width, 120);

// ── 메인 헤드라인 ─────────────────────────────────────────────
ctx.font = 'bold 68px -apple-system, sans-serif';
ctx.fillStyle = '#f2f4f7';
ctx.fillText('리뷰 답글, AI가 초안을', 80, 270);
ctx.fillStyle = '#00E5A0';
ctx.fillText('만들어드립니다', 80, 355);

// ── 서브 텍스트 ───────────────────────────────────────────────
ctx.font = '32px -apple-system, sans-serif';
ctx.fillStyle = '#8896a8';
ctx.fillText('카페·음식점 사장님 전용 AI 리뷰 자동화', 80, 430);

// ── 배지 ──────────────────────────────────────────────────────
const badges = ['✅ AI 초안 제공', '🚫 자동 게시 없음', '⚡ 10분 무료 진단'];
let bx = 80;
badges.forEach(badge => {
  ctx.font = 'bold 24px -apple-system, sans-serif';
  const tw = ctx.measureText(badge).width;
  const pad = 20;
  // 배지 배경
  ctx.fillStyle = 'rgba(0,229,160,0.12)';
  roundRect(ctx, bx, 490, tw + pad * 2, 44, 22);
  ctx.fill();
  // 배지 테두리
  ctx.strokeStyle = 'rgba(0,229,160,0.35)';
  ctx.lineWidth = 1;
  roundRect(ctx, bx, 490, tw + pad * 2, 44, 22);
  ctx.stroke();
  // 배지 텍스트
  ctx.fillStyle = '#00E5A0';
  ctx.fillText(badge, bx + pad, 519);
  bx += tw + pad * 2 + 16;
});

// ── 우측 장식 ─────────────────────────────────────────────────
ctx.font = '200px sans-serif';
ctx.fillStyle = 'rgba(0,229,160,0.06)';
ctx.fillText('🤖', 820, 420);

// ── 하단 URL ──────────────────────────────────────────────────
ctx.font = '24px -apple-system, sans-serif';
ctx.fillStyle = '#4a5568';
ctx.fillText('loopforge-2v1.pages.dev', 80, 600);

// ── 저장 ──────────────────────────────────────────────────────
const out = fs.createWriteStream('og-image.png');
canvas.createPNGStream().pipe(out);
out.on('finish', () => console.log('✅ og-image.png 생성 완료 (1200×630px)'));

// ── 헬퍼: 둥근 사각형 ─────────────────────────────────────────
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

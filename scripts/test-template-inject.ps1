#!/usr/bin/env pwsh
# test-template-inject.ps1
# Connect AI Bridge의 /api/template-inject 엔드포인트를 테스트합니다.
# 결과: 두뇌/.connect-ai-brain/40_템플릿/developer/landing-kit/ 에 파일 생성

$ErrorActionPreference = 'Stop'
$BridgeUrl = 'http://127.0.0.1:4825/api/template-inject'

$payload = @{
    agent       = 'developer'
    name        = 'landing-kit'
    displayName = 'Landing Kit'
    description = 'SaaS 랜딩 페이지 boilerplate (Hero + CTA 6 섹션)'
    source      = 'test-template-inject.ps1'
    manifest    = @{
        name    = 'Landing Kit'
        version = '1.0.0'
        tags    = @('landing', 'saas', 'html')
    }
    readme      = @"
# Landing Kit

SaaS 랜딩 페이지용 boilerplate. Hero, Features, Pricing, CTA 6개 섹션 포함.

## 사용법
1. `files/index.html` 을 프로젝트에 복사
2. 텍스트·색상 수정 후 배포
"@
    files       = @{
        'index.html' = @"
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>랜딩 페이지</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-white text-gray-900 font-sans">
  <!-- Hero -->
  <section class="min-h-screen flex flex-col items-center justify-center text-center px-6">
    <h1 class="text-5xl font-bold mb-4">당신의 제품 이름</h1>
    <p class="text-xl text-gray-500 mb-8 max-w-xl">한 줄 가치 제안. 고객이 얻는 것을 명확하게.</p>
    <a href="#" class="bg-indigo-600 text-white px-8 py-3 rounded-full text-lg hover:bg-indigo-700 transition">무료로 시작하기</a>
  </section>
  <!-- Features -->
  <section class="py-20 px-6 bg-gray-50">
    <h2 class="text-3xl font-bold text-center mb-12">주요 기능</h2>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto">
      <div class="bg-white rounded-2xl p-6 shadow"><h3 class="font-semibold text-lg mb-2">⚡ 기능 1</h3><p class="text-gray-500">기능 설명을 여기에.</p></div>
      <div class="bg-white rounded-2xl p-6 shadow"><h3 class="font-semibold text-lg mb-2">🎯 기능 2</h3><p class="text-gray-500">기능 설명을 여기에.</p></div>
      <div class="bg-white rounded-2xl p-6 shadow"><h3 class="font-semibold text-lg mb-2">🚀 기능 3</h3><p class="text-gray-500">기능 설명을 여기에.</p></div>
    </div>
  </section>
  <!-- CTA -->
  <section class="py-20 px-6 text-center">
    <h2 class="text-3xl font-bold mb-4">지금 바로 시작하세요</h2>
    <a href="#" class="bg-indigo-600 text-white px-10 py-4 rounded-full text-lg hover:bg-indigo-700 transition">무료 체험 →</a>
  </section>
</body>
</html>
"@
        'tailwind.config.js' = @"
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./**/*.html'],
  theme: { extend: {} },
  plugins: [],
}
"@
    }
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri $BridgeUrl -Method POST `
        -ContentType 'application/json' `
        -Body $payload -TimeoutSec 10
} catch {
    if ($_.Exception.Response -ne $null) {
        $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
        $errBody = $reader.ReadToEnd()
        Write-Error "Bridge 오류 ($([int]$_.Exception.Response.StatusCode)): $errBody"
    } else {
        Write-Error "연결 실패 — Bridge가 실행 중인지 확인하세요 (포트 4825).`n$($_.Exception.Message)"
    }
    exit 1
}

# 저장 위치 계산 (Bridge와 동일한 경로 규칙)
$brainDir = Join-Path $env:USERPROFILE '.connect-ai-brain'
$savedPath = Join-Path $brainDir '40_템플릿\developer\landing-kit'

Write-Host '성공!' -ForegroundColor Green
Write-Host "저장 위치: $savedPath"

$fileCount = 0
if (Test-Path $savedPath) {
    $fileCount = (Get-ChildItem -Path $savedPath -Recurse -File).Count
}
Write-Host "파일 수:   $fileCount"

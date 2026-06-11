param(
    [string]$ProjectDir = "D:\Connect AI\connect-ai-main\connect-ai-main"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok([string]$msg)   { Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Fail([string]$msg) { Write-Host "`n[FAIL] $msg" -ForegroundColor Red }

Write-Step "1/5  프로젝트 폴더로 이동: $ProjectDir"
if (-not (Test-Path $ProjectDir)) { Write-Fail "폴더 없음: $ProjectDir"; exit 1 }
Set-Location $ProjectDir
Write-Ok (Get-Location)

Write-Step "2/5  git pull origin main"
git config core.longpaths true
git fetch origin main
if ($LASTEXITCODE -ne 0) { Write-Fail "git fetch 실패"; exit $LASTEXITCODE }
git reset --hard origin/main
if ($LASTEXITCODE -ne 0) { Write-Fail "git reset 실패"; exit $LASTEXITCODE }
Write-Ok "동기화 완료"

Write-Step "3/5  npm install"
npm install
if ($LASTEXITCODE -ne 0) { Write-Fail "npm install 실패"; exit $LASTEXITCODE }
Write-Ok "의존성 설치 완료"

Write-Step "4/5  npm run compile"
npm run compile
if ($LASTEXITCODE -ne 0) { Write-Fail "빌드 실패"; exit $LASTEXITCODE }
Write-Ok "빌드 완료"

Write-Step "5/5  npx vsce package --no-dependencies"
npx vsce package --no-dependencies
if ($LASTEXITCODE -ne 0) { Write-Fail "패키징 실패"; exit $LASTEXITCODE }

$vsix = Get-ChildItem -Path $ProjectDir -Filter "*.vsix" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
if ($vsix) {
    Write-Host "  완료! 생성된 파일: $($vsix.Name)" -ForegroundColor Green
    Write-Host "  경로: $($vsix.FullName)" -ForegroundColor Green
} else {
    Write-Host "  패키징 성공 (vsix 파일 확인 필요)" -ForegroundColor Yellow
}
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow

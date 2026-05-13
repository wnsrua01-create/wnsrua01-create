# Connect AI - /api/template-inject 테스트 스크립트
# 사용법: .\test-template-inject.ps1
# VS Code에서 Connect AI 확장이 실행 중이어야 합니다 (포트 4825).

$uri = "http://localhost:4825/api/template-inject"

$payload = @{
    agent       = "developer"
    name        = "landing-kit"
    displayName = "Landing Kit 테스트"
    description = "PowerShell 주입 테스트"
    manifest    = @{
        version = "1.0.0"
        stack   = "react"
    }
    readme      = "# Landing Kit`n`nPowerShell에서 주입된 테스트 템플릿"
    files       = @{
        "Hero.tsx"  = "export default function Hero() { return <h1>Hero</h1>; }"
        "Footer.tsx" = "export default function Footer() { return <footer>Footer</footer>; }"
    }
    source      = "powershell-test"
} | ConvertTo-Json -Depth 5

Write-Host "POST $uri ..." -ForegroundColor Cyan

try {
    $res = Invoke-WebRequest -Uri $uri -Method POST `
        -ContentType "application/json" `
        -Body ([System.Text.Encoding]::UTF8.GetBytes($payload)) `
        -UseBasicParsing

    $json = $res.Content | ConvertFrom-Json
    Write-Host "성공!" -ForegroundColor Green
    Write-Host "저장 위치: $($json.location)"
    Write-Host "파일 수:   $($json.filesWritten)"
} catch {
    Write-Host "실패: $_" -ForegroundColor Red
    if ($_.Exception.Response) {
        $stream = $_.Exception.Response.GetResponseStream()
        $reader = New-Object System.IO.StreamReader($stream)
        Write-Host $reader.ReadToEnd() -ForegroundColor Yellow
    }
}

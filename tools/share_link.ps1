# Makes the running IPO RRG app reachable by anyone through a Cloudflare quick tunnel.
# The link works only while this window stays open and this PC is on.
# (Same method as the help folder's RRG Graph app\tools\share_link.ps1, port 8502.)
$ErrorActionPreference = "Stop"
$app  = Split-Path -Parent $PSScriptRoot
$port = 8502
$url  = "http://127.0.0.1:$port"
$host.UI.RawUI.WindowTitle = "IPO Daily RRG - public link (keep open while sharing)"

function Test-App {
    try { (Invoke-WebRequest -UseBasicParsing "$url/_stcore/health" -TimeoutSec 3).Content -eq "ok" }
    catch { $false }
}

if (-not (Test-App)) {
    Write-Host "Starting the IPO RRG app..."
    Start-Process -FilePath (Join-Path $app "Start IPO RRG App.bat") -WorkingDirectory $app -WindowStyle Minimized
    for ($i = 0; $i -lt 90 -and -not (Test-App); $i++) { Start-Sleep 1 }
    if (-not (Test-App)) { Write-Host "The app did not start. Run 'Start IPO RRG App.bat' to see the error."; Read-Host "Press Enter to close"; exit 1 }
}

$log = Join-Path $env:TEMP "ipo_rrg_tunnel.log"
Remove-Item $log -ErrorAction SilentlyContinue
Write-Host "Opening the public link..."
$tunnel = Start-Process -FilePath (Join-Path $PSScriptRoot "cloudflared.exe") -PassThru -WindowStyle Hidden `
    -ArgumentList "tunnel", "--url", $url, "--no-autoupdate" -RedirectStandardError $log

$link = $null
for ($i = 0; $i -lt 60 -and -not $link; $i++) {
    Start-Sleep 1
    if (Test-Path $log) {
        $m = Select-String -Path $log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -First 1
        if ($m) { $link = $m.Matches[0].Value }
    }
}
if (-not $link) {
    Write-Host "Could not open a public link. Details are in $log"
    Stop-Process -Id $tunnel.Id -ErrorAction SilentlyContinue
    Read-Host "Press Enter to close"; exit 1
}

Set-Clipboard -Value $link
Write-Host ""
Write-Host "  Public link (copied to clipboard):" -ForegroundColor Green
Write-Host ""
Write-Host "      $link" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Anyone with this link can open the app while this window is open."
Write-Host "  It usually starts working within 10-20 seconds."
Write-Host "  The link is new every time you run this."
Write-Host ""
Read-Host "Press Enter to stop sharing"
Stop-Process -Id $tunnel.Id -ErrorAction SilentlyContinue

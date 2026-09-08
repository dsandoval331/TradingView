# PMPD V5 9J VWAP Event-Path V2 — local package locator / preflight
# Run from the TradingResearch repository root in PowerShell.
$ErrorActionPreference = "Stop"
Write-Host "PMPD V5 9J VWAP Event-Path V2 preflight" -ForegroundColor Cyan
Write-Host "Repository: $(Get-Location)"

$patterns = @(
  '*PMPD_V5_9H_RESEARCH_DATASET_V1*',
  '*PMPD_V5*ALPHA*0_2*',
  '*decision*', '*event*', '*session_level*',
  '*VWAP*V1*', '*market*cache*', '*.parquet'
)

$files = foreach ($pat in $patterns) {
  Get-ChildItem -Path . -Recurse -File -Filter $pat -ErrorAction SilentlyContinue |
    Select-Object FullName,Length,LastWriteTime
}
$files | Sort-Object FullName -Unique | Format-Table -AutoSize

Write-Host "`nLikely Python research scripts:" -ForegroundColor Cyan
Get-ChildItem -Path . -Recurse -File -Include *.py -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match 'pmpd|v5|9h|9j|vwap' } |
  Select-Object FullName,Length,LastWriteTime |
  Sort-Object FullName | Format-Table -AutoSize

Write-Host "`nDo not advance to 9K. Return this complete output to the PM+PD V5 research thread." -ForegroundColor Yellow

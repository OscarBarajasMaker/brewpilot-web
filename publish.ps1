# BrewPilot beta publish - Windows PowerShell
# Run from the folder where you downloaded index.html
# Requires: git installed, and a GitHub repo named brewpilot-web (public)
#
# Normal use (serves at oscarbarajasmaker.github.io/brewpilot-web/):
#     .\publish.ps1
#
# ONLY after the is-a.dev pull request has MERGED:
#     .\publish.ps1 -Domain
# Adding CNAME before the domain exists takes your site OFFLINE, because Pages
# stops serving the github.io URL and redirects to a domain that does not resolve.

param(
  [switch]$Domain,
  [string]$Message = ""
)

$ErrorActionPreference = "Stop"
$env:GIT_REDIRECT_STDERR = "2>&1"
$repo = "brewpilot-web"
$user = "OscarBarajasMaker"

Write-Host "1. checking index.html is here" -ForegroundColor Cyan
if (-not (Test-Path ".\index.html")) { throw "index.html not found in this folder" }

if ($Domain) {
  Write-Host "2. writing CNAME (is-a.dev mode)" -ForegroundColor Cyan
  "brewpilot.is-a.dev" | Out-File -FilePath ".\CNAME" -Encoding ascii -NoNewline
} else {
  Write-Host "2. no CNAME (serving from github.io). Use -Domain after the is-a.dev PR merges." -ForegroundColor Cyan
  if (Test-Path ".\CNAME") {
    Remove-Item ".\CNAME"
    git rm --cached CNAME 2>$null | Out-Null
    Write-Host "   removed a stale CNAME that would have taken the site offline" -ForegroundColor Yellow
  }
}


Write-Host "2b. checking encoding is intact" -ForegroundColor Cyan
$utf8 = New-Object System.Text.UTF8Encoding($false)
$check = [System.IO.File]::ReadAllText((Join-Path (Get-Location) "index.html"), $utf8)
if (-not $check.Contains([char]0x25C9)) {
  throw "index.html encoding looks damaged (tab icons are mangled). Re-download index.html and run this again."
}

Write-Host "3. writing .nojekyll (stops GitHub touching your files)" -ForegroundColor Cyan
"" | Out-File -FilePath ".\.nojekyll" -Encoding ascii -NoNewline

Write-Host "4. git init and push" -ForegroundColor Cyan
if (-not (Test-Path ".\.git")) { git init | Out-Null }
$pwa = @("manifest.json","sw.js","icon-192.png","icon-512.png","icon-512-maskable.png","apple-touch-icon.png")
$missing = @()
foreach ($f in $pwa) { if (-not (Test-Path ".\$f")) { $missing += $f } }
if ($missing.Count -gt 0) {
  Write-Host "   WARNING: add-to-home-screen files missing, install will not work:" -ForegroundColor Yellow
  foreach ($m in $missing) { Write-Host ("     " + $m) -ForegroundColor Yellow }
}
git add index.html .nojekyll
foreach ($f in $pwa) { if (Test-Path ".\$f") { git add $f } }
if ($Domain) { git add CNAME }
if (-not $Message) { $Message = "BrewPilot update " + (Get-Date -Format "yyyy-MM-dd HH:mm") }
# pass the message as an argument, not inside a quoted string, so apostrophes and
# quotes in the description cannot break the command
git -c user.name="$user" -c user.email="oscarjpbarajas@gmail.com" commit -m $Message | Out-Null
git branch -M main
$remote = git remote 2>$null
if (-not $remote) { git remote add origin "https://github.com/$user/$repo.git" }
git push -u origin main --force

Write-Host ""
Write-Host "DONE. Now do this once in the browser:" -ForegroundColor Green
Write-Host "  https://github.com/$user/$repo/settings/pages"
Write-Host "  Source: Deploy from a branch -> main -> /(root) -> Save"
Write-Host ""
Write-Host "Live in about 1 minute at:" -ForegroundColor Green
if ($Domain) { Write-Host "  https://brewpilot.is-a.dev/" }
else { Write-Host "  https://$($user.ToLower()).github.io/$repo/" }

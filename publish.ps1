# BrewPilot publish - Windows PowerShell
# Run from the repo root (C:\Users\oscar\BrewPilot).
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
  [string]$Message = "",
  [switch]$ForcePush
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

Write-Host "4. staging" -ForegroundColor Cyan
if (-not (Test-Path ".\.git")) { throw "no .git here. Run this from the repo root." }

$pwa = @("manifest.json","sw.js","icon-192.png","icon-512.png","icon-512-maskable.png","apple-touch-icon.png")
$missing = @()
foreach ($f in $pwa) { if (-not (Test-Path ".\$f")) { $missing += $f } }
if ($missing.Count -gt 0) {
  Write-Host "   WARNING: add-to-home-screen files missing, install will not work:" -ForegroundColor Yellow
  foreach ($m in $missing) { Write-Host ("     " + $m) -ForegroundColor Yellow }
}

# This used to stage an explicit allowlist: index.html, .nojekyll and the six PWA
# files. Nothing else was ever staged by a publish, so every other tracked file
# was in the repo only because someone had committed it by hand once. audit.py
# drifted from v7 to v10 that way and CI gated on the stale copy for three
# versions while reporting green, because an old audit passes.
#
# One list decides what belongs in this repo now, and it is .gitignore. An
# allowlist that has to be kept in sync with a second list is the same shape as
# the copy list that 404'd client-id.js in production.
git add -A

# Nothing tracked may still differ after staging. If it does, a gate file could
# ship stale, which is exactly the failure above.
$dirty = @(git diff --name-only)
if ($dirty.Count -gt 0) {
  throw ("tracked files still differ after git add -A: " + ($dirty -join ' '))
}

Write-Host "5. commit" -ForegroundColor Cyan
if (-not $Message) { $Message = "BrewPilot update " + (Get-Date -Format "yyyy-MM-dd HH:mm") }
# The message goes in as an argument, not inside a quoted string, so apostrophes
# and quotes in the description cannot break the command.
$out = & git -c user.name="$user" -c user.email="oscarjpbarajas@gmail.com" commit -m $Message 2>&1
$committed = ($LASTEXITCODE -eq 0)
if (-not $committed) {
  if (($out | Out-String) -match 'nothing to commit') {
    Write-Host "   nothing new to commit, will still push in case the remote is behind" -ForegroundColor Yellow
  } else {
    Write-Host ($out | Out-String)
    throw "git commit failed"
  }
} else {
  Write-Host ("   " + (git log --oneline -1))
}

Write-Host "6. gate parity" -ForegroundColor Cyan
# CI runs audit.py and undef.js FROM THE REPO. If the committed copies are not
# byte-for-byte the ones that just passed on this machine, the gate is theatre.
# Comparing git blob hashes rather than file hashes so that .gitattributes
# filters are applied the same way on both sides.
foreach ($g in @("audit.py","undef.js")) {
  if (-not (Test-Path ".\$g")) { throw "$g is missing from the repo root. CI needs it." }
  $work = (git hash-object -- $g | Out-String).Trim()
  $head = (git rev-parse ("HEAD:" + $g) 2>$null | Out-String).Trim()
  if (-not $head) { throw "$g is not committed. CI would run nothing." }
  if ($work -ne $head) {
    throw "$g on disk differs from the committed copy. CI would gate on the old one."
  }
  Write-Host ("   " + $g + "  " + $work.Substring(0,12) + "  matches HEAD")
}

Write-Host "7. push" -ForegroundColor Cyan
git branch -M main
$remote = git remote 2>$null
if (-not $remote) { git remote add origin "https://github.com/$user/$repo.git" }

# The old version pushed with --force every time. That silently discards
# anything pushed from elsewhere, and this repo IS published from elsewhere:
# index.html can go up from a phone through Working Copy. Plain push by default;
# --force-with-lease behind a switch, which refuses if the remote moved.
if ($ForcePush) {
  git push -u origin main --force-with-lease
} else {
  git push -u origin main
}
if ($LASTEXITCODE -ne 0) {
  Write-Host ""
  Write-Host "  push rejected. The remote has commits you do not have locally." -ForegroundColor Yellow
  Write-Host "  Look before you overwrite:" -ForegroundColor Yellow
  Write-Host "    git fetch origin; git log --oneline HEAD..origin/main"
  Write-Host "  Then either merge, or if you are certain the remote is wrong:"
  Write-Host "    .\publish.ps1 -ForcePush"
  throw "push failed"
}

Write-Host ""
Write-Host "DONE." -ForegroundColor Green
Write-Host "Watch the gates run:" -ForegroundColor Green
Write-Host "  https://github.com/$user/$repo/actions"
Write-Host ""
Write-Host "Live in about 1 minute at:" -ForegroundColor Green
if ($Domain) { Write-Host "  https://brewpilot.is-a.dev/" }
else { Write-Host "  https://$($user.ToLower()).github.io/$repo/" }

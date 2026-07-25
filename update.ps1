# Verify the BrewPilot files in this folder, then publish. Handles the
# "index (1).html" duplicates Chrome creates by promoting them over index.html.
# Defaults to THIS folder. Use -From to pull from elsewhere, e.g.
#   .\update.ps1 -From $HOME\Downloads
# Pulling from Downloads is risky: a stale index.html there overwrites a newer
# one here, which is how a publish can silently ship an old build.
#
# Run it from your repo folder (the one with .git), e.g. C:\Users\oscar\Downloads\Publish
#     .\update.ps1
#
# After the is-a.dev PR merges, add the domain:
#     .\update.ps1 -Domain
#
# DOWNLOAD this file. Do not copy-paste it.

param(
  [switch]$Domain,
  [string]$Message = "",
  [string]$From = (Get-Location),
  [switch]$SkipAudit,
  # Deliberately publish with Google sign in switched off. You have to type
  # this. It is not a default, because the default cost a live outage.
  [switch]$AllowNoClientId
)

$ErrorActionPreference = "Stop"
$utf8 = New-Object System.Text.UTF8Encoding($false)

$wanted = @(
  "index.html",
  "manifest.json",
  "sw.js",
  "icon-192.png",
  "icon-512.png",
  "icon-512-maskable.png",
  "apple-touch-icon.png"
)

if (-not (Test-Path (Join-Path (Get-Location) ".git"))) {
  throw "No .git here. Run this from your repo folder."
}
if (-not (Test-Path $From)) { throw "Source folder not found: $From" }

# Clear the Mark of the Web from every script in this folder, first thing.
#
# Windows tags downloaded files, and under the RemoteSigned execution policy a
# tagged script refuses to run. This script CALLS publish.ps1, so a freshly
# downloaded publish.ps1 that was never unblocked lets the run get all the way
# through both gates and then die at the push, with the client ID already
# rewritten on disk. Unblocking here is not a security decision: you already
# chose to download and run this file, and this only touches .ps1 files sitting
# next to it. Unblock-File does not exist off Windows, hence the guard.
if (Get-Command Unblock-File -ErrorAction SilentlyContinue) {
  $unblocked = 0
  Get-ChildItem -Path $PSScriptRoot -Filter '*.ps1' -File -ErrorAction SilentlyContinue | ForEach-Object {
    try {
      if (Get-Item -Path $_.FullName -Stream Zone.Identifier -ErrorAction SilentlyContinue) {
        Unblock-File -Path $_.FullName -ErrorAction SilentlyContinue
        $unblocked++
      }
    } catch {}
  }
  if ($unblocked -gt 0) {
    Write-Host ('  unblocked ' + $unblocked + ' downloaded script(s) in this folder') -ForegroundColor DarkGray
  }
}

Write-Host "Looking in $From" -ForegroundColor Cyan
Write-Host ""

$copied = 0
$skipped = @()

foreach ($name in $wanted) {
  $base = [System.IO.Path]::GetFileNameWithoutExtension($name)
  $ext  = [System.IO.Path]::GetExtension($name)
  # match index.html and "index (1).html" and "index(2).html"
  $pattern = $base + "*" + $ext
  $hits = Get-ChildItem -Path $From -Filter $pattern -File -ErrorAction SilentlyContinue |
          Where-Object { $_.BaseName -match ("^" + [regex]::Escape($base) + "( ?\(\d+\))?$") } |
          Sort-Object LastWriteTime -Descending

  if ($hits.Count -eq 0) { $skipped += $name; continue }

  $newest = $hits[0]
  $dest = Join-Path (Get-Location) $name
  $same = $false
  if (Test-Path $dest) {
    $a = (Get-FileHash $newest.FullName -Algorithm SHA256).Hash
    $b = (Get-FileHash $dest -Algorithm SHA256).Hash
    $same = ($a -eq $b)
  }
  if ($newest.FullName -eq $dest) {
    Write-Host ("  = " + $name + "  already in place") -ForegroundColor DarkGray
  } elseif ($same) {
    Write-Host ("  = " + $name + "  unchanged") -ForegroundColor DarkGray
  } elseif ((Test-Path $dest) -and ((Get-Item $dest).LastWriteTime -gt $newest.LastWriteTime)) {
    $mins = [math]::Round(((Get-Item $dest).LastWriteTime - $newest.LastWriteTime).TotalMinutes)
    Write-Host ("  ! " + $name + "  SKIPPED - the file here is " + $mins + " min NEWER than '" + $newest.Name + "'") -ForegroundColor Yellow
    Write-Host "      keeping the newer one so a stale download cannot overwrite it" -ForegroundColor DarkGray
  } else {
    Copy-Item $newest.FullName $dest -Force
    $age = [math]::Round(((Get-Date) - $newest.LastWriteTime).TotalMinutes)
    Write-Host ("  + " + $name + "   from '" + $newest.Name + "'  (" + $age + " min old)") -ForegroundColor Green
    $copied++
  }
}

Write-Host ""
if ($skipped.Count -gt 0) {
  Write-Host "Not found in $From (keeping whatever is already here):" -ForegroundColor Yellow
  foreach ($s in $skipped) {
    if (Test-Path (Join-Path (Get-Location) $s)) { Write-Host ("  " + $s + "  already present") -ForegroundColor DarkGray }
    else { Write-Host ("  " + $s + "  MISSING - add to home screen will not work") -ForegroundColor Red }
  }
  Write-Host ""
}

Write-Host "Verifying index.html" -ForegroundColor Cyan
# One path, used by the read and by the client-id write-back below. These used to
# be written out separately, and $PSScriptRoot vs (Get-Location) disagree the
# moment this is run from anywhere but the folder it lives in.
$idxPath = Join-Path (Get-Location) "index.html"
$html = [System.IO.File]::ReadAllText($idxPath, $utf8)
if (-not $html.Contains([char]0x25C9)) {
  throw "index.html encoding is damaged (tab icons mangled). Re-download it, do not paste it."
}
Write-Host "  encoding intact" -ForegroundColor Green
# The template link must point at the SHARED TEMPLATE, never at a working sheet.
# This shipped wrong once: the generator had BrewPilot_Log (Oscar's own sheet)
# baked in, so testers would have copied his personal sheet and his data. It was
# only ever PRINTED here, in green, so it read like a pass and slid through.
# Now it is checked, and a wrong id stops the publish.
# Static audit. Refuses to publish a build with a silent no-op in it.
#
# Every bug that reached Oscar's phone this session had the same shape: code
# referring to a name that did not exist. getElementById returns null, JS does
# not throw, the feature is simply dead. Five of those shipped before anyone
# noticed, always via a screenshot. audit.py checks the BUILT file, which is
# the only text that is actually true.
# undef.js: scope analysis, which audit.py structurally cannot do.
#
# audit.py is regex over the built file. It catches a getElementById of an id that
# does not exist, but not a JS identifier that was never declared. That gap shipped:
# wizTemplateLink() read a deleted SHEET_TEMPLATE_URL at bootstrap - a ReferenceError
# that kills every line after it - and audit.py, node --check and a human review all
# passed it. adv2.js would have caught it, but adv2 is not part of this gate.
#
# It also found INV: read 11 times, declared 0 times, assigned 0 times, every read
# hidden behind a typeof guard that was therefore always false. Two features had
# never worked for anyone and nothing had ever reported it.
#
# A hand-rolled regex version of this flagged 134 false positives on a clean build.
# A real parser flags 0. That is the whole argument for acorn being here.
$undefJs = Join-Path $PSScriptRoot 'undef.js'
if (Test-Path $undefJs) {
  $undefOut = & node $undefJs (Join-Path $PSScriptRoot 'index.html') 2>&1
  $undefOut | ForEach-Object { Write-Host $_ }
  $undefBad = $LASTEXITCODE -ne 0
  if (-not $undefBad -and ($undefOut -join ' ') -notmatch 'undeclared identifiers:\s*0') {
    $undefBad = $true
  }
  if ($undefBad) {
    Write-Host ''
    Write-Host '  PUBLISH STOPPED: an identifier is used but never declared.' -ForegroundColor Red
    Write-Host '  At bootstrap that is a ReferenceError and every line after it dies.' -ForegroundColor DarkGray
    Write-Host '  Override with -SkipAudit if you are certain.' -ForegroundColor DarkGray
    if (-not $SkipAudit) { exit 1 }
  }
} else {
  Write-Host '  undef.js not found: skipping scope analysis' -ForegroundColor DarkYellow
}

$auditPy = Join-Path $PSScriptRoot 'audit.py'
if (Test-Path $auditPy) {
  $auditOut = & python $auditPy (Join-Path $PSScriptRoot 'index.html') 2>&1
  $auditOut | ForEach-Object { Write-Host $_ }
  if ($LASTEXITCODE -ne 0) {
    Write-Host ''
    Write-Host '  PUBLISH STOPPED by audit.py. Fix the failures above.' -ForegroundColor Red
    Write-Host '  Override with -SkipAudit if you are certain.' -ForegroundColor DarkGray
    if (-not $SkipAudit) { exit 1 }
    Write-Host '  -SkipAudit given, continuing anyway.' -ForegroundColor Yellow
  }
} else {
  Write-Host '  WARNING: audit.py not found next to this script. Publishing unchecked.' -ForegroundColor Yellow
}

# Google client ID survival.
# Every index.html Claude ships has GOOGLE_CLIENT_ID empty, because the ID is
# baked in locally. Without this, each new build silently un-configures Google
# sign in and the app reverts to the old paste-an-/exec flow with no error.
#
# An earlier version read a deployed_index.html that NOTHING EVER WROTE, so the
# carry-over could never fire. set-client-id.ps1 now writes client_id.txt.
# Build stamp. Print what is being published so you can compare it against the
# 'build ...' line at the bottom of Settings in the live app. Same idea as
# FW_VERSION in the firmware: answer 'which build is live' without guessing.
if ($html -match 'BUILD\s*=\s*[''"]([^''"]+)[''"]') {
  $buildStamp = $matches[1]
  Write-Host ('  build: ' + $buildStamp) -ForegroundColor Cyan
  # sw.js is NOT stamped any more. index.html registers sw.js?v=<BUILD> and sw.js
  # derives its own cache name from that query. The old code rewrote a literal in
  # sw.js, which meant any publish that skipped THIS SCRIPT left the cache name
  # frozen. That is exactly what happened: live sw.js said df3100 while
  # index.html said 12a3b2. Verify the derivation is intact, do not write.
  $swFile = Join-Path $PSScriptRoot 'sw.js'
  if (-not (Test-Path $swFile)) {
    Write-Host '  STOP: sw.js not found next to this script.' -ForegroundColor Red
    exit 1
  }
  $sw = Get-Content $swFile -Raw -Encoding UTF8
  if ($sw -match '__BUILD_STAMP__') {
    Write-Host '  STOP: sw.js still contains the __BUILD_STAMP__ placeholder.' -ForegroundColor Red
    Write-Host '        Download the current sw.js.' -ForegroundColor Yellow
    exit 1
  }
  if ($sw -notmatch "searchParams\.get\('v'\)") {
    Write-Host '  STOP: sw.js does not derive its cache name from the ?v= query.' -ForegroundColor Red
    Write-Host '        That is the old stamped sw.js. A phone upload would freeze the cache name.' -ForegroundColor Yellow
    Write-Host '        Download the current sw.js.' -ForegroundColor Yellow
    exit 1
  }
  if ($html -notmatch "sw\.js\?v=") {
    Write-Host '  STOP: index.html does not register sw.js with a ?v= version.' -ForegroundColor Red
    Write-Host '        That is an old build. Download the current index.html.' -ForegroundColor Yellow
    exit 1
  }
  Write-Host ('  sw.js cache: derived at runtime, will be brewpilot-' + $buildStamp) -ForegroundColor DarkGray
  Write-Host '         (open Settings in the live app, bottom line, and check it matches)' -ForegroundColor DarkGray
} else {
  Write-Host '  build: no stamp found. This index.html predates build stamping.' -ForegroundColor Yellow
}

$idFile = Join-Path $PSScriptRoot 'client_id.txt'
$cidJs  = Join-Path $PSScriptRoot 'client-id.js'
$cidPat = 'BREWPILOT_CLIENT_ID\s*=\s*(''[^'']*''|"[^"]*")'

# HARD STOP, not a warning. Rewritten 2026-07-23 after build 12a3b2 went live
# with an empty client ID.
#
# The ID no longer lives in index.html. It lives in client-id.js, which
# index.html loads in <head>. That is what makes a phone upload of index.html
# safe: there is nothing in that file left to lose. This block now checks the
# file that actually holds the ID, and refuses to publish without it.

function Stop-NoClientId([string]$why) {
  Write-Host ''
  Write-Host ('  STOP: ' + $why) -ForegroundColor Red
  Write-Host '        Publishing this would ship an app that cannot reach Google Drive.' -ForegroundColor Yellow
  Write-Host '        There is no /exec fallback any more, so sign in would simply not work.' -ForegroundColor DarkGray
  Write-Host ''
  Write-Host '  Fix:  .\set-client-id.ps1 -ClientId ''NNNNNN.apps.googleusercontent.com''' -ForegroundColor Cyan
  Write-Host '        then run this script again.' -ForegroundColor DarkGray
  Write-Host ''
  Write-Host '  To publish without Google sign in on purpose, re-run with -AllowNoClientId' -ForegroundColor DarkGray
  Write-Host ''
  if (-not $AllowNoClientId) { exit 1 }
  Write-Host '  -AllowNoClientId given, publishing without Google sign in.' -ForegroundColor Yellow
}

# 1. the build in hand has to be one that reads the external file at all
if ($html -notmatch 'client-id\.js') {
  Stop-NoClientId 'index.html does not load client-id.js. That is an old build that bakes the ID inline.'
}

# 2. client-id.js must exist. If it does not but client_id.txt does, rebuild it
#    rather than making you re-type the ID.
if (-not (Test-Path $cidJs)) {
  $rawId = Get-Content $idFile -Raw -ErrorAction SilentlyContinue
  $saved = ''
  if ($rawId) { $saved = ([string]$rawId).Trim() }
  if ($saved) {
    $body = "// Google OAuth client ID for BrewPilot. Regenerated by update.ps1 from client_id.txt.`r`n" +
            "window.BREWPILOT_CLIENT_ID = '" + $saved + "';`r`n"
    [System.IO.File]::WriteAllText($cidJs, $body, $utf8)
    Write-Host '  client-id.js was missing, regenerated from client_id.txt.' -ForegroundColor Yellow
  } else {
    Stop-NoClientId 'client-id.js does not exist and client_id.txt is missing or empty.'
  }
}

# 3. post-condition, read from disk, on the bytes that will be committed
$cidVal = ''
if (Test-Path $cidJs) {
  $cidTxt = [System.IO.File]::ReadAllText($cidJs, $utf8)
  if ($cidTxt -match $cidPat) { $cidVal = $matches[1].Trim("'", '"') }
}
if (-not $cidVal) {
  Write-Host ''
  Write-Host '  STOP: client-id.js ON DISK does not set a client ID.' -ForegroundColor Red
  Write-Host '        Nothing is being pushed.' -ForegroundColor Yellow
  Write-Host ''
  if (-not $AllowNoClientId) { exit 1 }
  Write-Host '  -AllowNoClientId given, publishing anyway.' -ForegroundColor Yellow
} else {
  Write-Host ('  client ID verified on disk before push: ' + $cidVal.Substring(0,[Math]::Min(22,$cidVal.Length)) + '...') -ForegroundColor Green
}

# SHEET_TEMPLATE_URL check REMOVED 2026-07-17 with the /exec amputation.
#
# It guarded the legacy copy-a-template flow: that the link was present, was not
# Oscar's personal working sheet, and pointed at the shared template. All three
# mattered while users set up by copying a sheet and deploying Apps Script.
# They do not any more. The app creates its own sheet through drive.file, the
# template is unused, and SHEET_TEMPLATE_URL is gone from the build.
#
# Leaving this in place would have STOPPED every publish from here on:
#   else { Write-Host "STOP: no SHEET_TEMPLATE_URL found in index.html"; exit }
# an amputation and its release script have to move together.
#
# The leak guard it also provided is NOT lost: audit.py check 9 fails the build
# if the personal working sheet id appears anywhere in the shipped file, and
# audit.py runs above and blocks the publish on a non-zero exit.

$kb = [math]::Round($html.Length / 1024)
Write-Host ("  size: " + $kb + " KB")

Write-Host ""
# Ask AFTER the copy report above, so you can see what actually changed before
# describing it. -Message skips the prompt for scripted runs.
if (-not $Message) {
  if ($copied -eq 0) {
    Write-Host "Nothing changed. No files were copied." -ForegroundColor Yellow
    $go = Read-Host "Publish anyway? (y/N)"
    if ($go -ne "y") { Write-Host "Stopped."; exit }
  }
  Write-Host "What changed? (Enter for a timestamp)" -ForegroundColor Cyan
  $Message = Read-Host "  commit"
  $Message = $Message.Trim()
}
if (-not $Message) { $Message = "BrewPilot update " + (Get-Date -Format "yyyy-MM-dd HH:mm") }
Write-Host ("  commit message: " + $Message) -ForegroundColor DarkGray

Write-Host ""
Write-Host "Publishing" -ForegroundColor Cyan
if ($Domain) { .\publish.ps1 -Domain -Message $Message } else { .\publish.ps1 -Message $Message }

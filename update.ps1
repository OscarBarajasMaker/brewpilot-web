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
  [switch]$SkipAudit
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
  # Stamp sw.js with the same build, so each release gets a fresh cache and the
  # activate handler evicts the previous one. Without this the cache name never
  # changes and old entries are kept forever.
  $swFile = Join-Path $PSScriptRoot 'sw.js'
  if (Test-Path $swFile) {
    $sw = Get-Content $swFile -Raw -Encoding UTF8
    $sw = $sw -replace "var CACHE = '[^']*';", ("var CACHE = 'brewpilot-" + $buildStamp + "';")
    [System.IO.File]::WriteAllText($swFile, $sw, (New-Object System.Text.UTF8Encoding $false))
    Write-Host ('  sw.js cache: brewpilot-' + $buildStamp) -ForegroundColor DarkGray
  } else {
    Write-Host '  WARNING: sw.js not found next to this script. Offline support will not update.' -ForegroundColor Yellow
  }
  Write-Host '         (open Settings in the live app, bottom line, and check it matches)' -ForegroundColor DarkGray
} else {
  Write-Host '  build: no stamp found. This index.html predates build stamping.' -ForegroundColor Yellow
}

$idFile = Join-Path $PSScriptRoot 'client_id.txt'
$cidPat = 'GOOGLE_CLIENT_ID\s*=\s*(''[^'']*''|"[^"]*")'
if ($html -match $cidPat) {
  $cur = [regex]::Match($html, $cidPat).Groups[1].Value.Trim("'", '"')
  if (-not $cur) {
    if (Test-Path $idFile) {
      $saved = (Get-Content $idFile -Raw).Trim()
      if ($saved) {
        $html = [regex]::Replace($html, $cidPat, ('GOOGLE_CLIENT_ID = "' + $saved + '"'), 1)
        # WRITE IT BACK. This line did not exist, and without it the whole block
        # was theatre: the replace only ever touched the in-memory $html, while
        # publish.ps1 does `git add index.html` and pushes the file ON DISK, which
        # still had GOOGLE_CLIENT_ID = "". Every build downloaded from Claude ships
        # the id empty by design, so every publish silently un-configured Google
        # sign in and the app fell back to the paste-an-/exec flow with no error.
        # It never bit because set-client-id.ps1 writes index.html itself, so the
        # id was only ever correct on builds that had not been re-downloaded.
        # The comment above this block describes this exact failure - a carry-over
        # that could never fire - being fixed once already, at the other end.
        [System.IO.File]::WriteAllText($idxPath, $html, $utf8)
        # Verify rather than trust the replace. set-client-id.ps1 already does this
        # and it is why that script never had this bug.
        $recheck = [System.IO.File]::ReadAllText($idxPath, $utf8)
        if ($recheck -notmatch [regex]::Escape($saved)) {
          Write-Host '  STOP: wrote index.html but the client ID is not in it.' -ForegroundColor Red
          exit 1
        }
        Write-Host ('  Google client ID re-applied from client_id.txt, verified on disk: ' + $saved.Substring(0,[Math]::Min(22,$saved.Length)) + '...') -ForegroundColor Green
      }
    } else {
      Write-Host '  Google sign in: NOT configured.' -ForegroundColor Yellow
      Write-Host '    The app will show the old paste-an-/exec flow.' -ForegroundColor DarkGray
      Write-Host '    Run set-client-id.ps1 first to enable one tap setup.' -ForegroundColor DarkGray
    }
  } else {
    Write-Host ('  Google sign in: configured (' + $cur.Substring(0,[Math]::Min(22,$cur.Length)) + '...)') -ForegroundColor Green
  }
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

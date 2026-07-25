#Requires -Version 5.1
<#
  bp-sync.ps1

  Takes whatever was just downloaded out of Downloads and puts every file where
  it belongs. Then publishes, if given a message.

      .\bp-sync.ps1                            route the files, do not publish
      .\bp-sync.ps1 -Message 'what changed'    route, then run publish.ps1
      .\bp-sync.ps1 -DryRun                    show the plan, touch nothing

  No config file. No setup. No prompts. This script lives in the repo root, so
  the repo root is wherever this script is. That is the whole configuration, and
  it is why the previous version's setup step is gone: a config file describing
  a folder layout is one more thing that can silently describe the wrong one.

  Files are MOVED out of Downloads, not copied. A stale index.html left sitting
  there is how the wrong build gets published a week later.

  The previous copy of each file goes to _scratch\_bak, which is gitignored. The
  old version wrote backups into the destination folder itself and git swept
  them into the generator history, which is the same duplicate-copy problem this
  is meant to prevent.
#>
[CmdletBinding()]
param(
  [string]$Message = '',
  [string]$Downloads = '',
  [string]$FirmwareDir = 'C:\Users\oscar\Downloads\espressocopilot',
  [int]$MaxAgeHours = 24,
  [switch]$DryRun,
  [switch]$Force
)

$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# ROUTING TABLE. Dest is relative to the repo root, or the literal FIRMWARE.
# ---------------------------------------------------------------------------
$ROUTES = @(
  @{ Name = 'index.html';            Dest = '.' },
  @{ Name = 'audit.py';              Dest = '.' },
  @{ Name = 'undef.js';              Dest = '.' },
  @{ Name = 'update.ps1';            Dest = '.' },
  @{ Name = 'publish.ps1';           Dest = '.' },
  @{ Name = 'sw.js';                 Dest = '.' },
  @{ Name = 'manifest.json';         Dest = '.' },
  @{ Name = 'client-id.js';          Dest = '.' },
  @{ Name = 'bp-sync.ps1';           Dest = '.' },
  @{ Name = 'bp-clean.ps1';          Dest = '.' },
  @{ Name = 'icon-192.png';          Dest = '.' },
  @{ Name = 'icon-512.png';          Dest = '.' },
  @{ Name = 'icon-512-maskable.png'; Dest = '.' },
  @{ Name = 'apple-touch-icon.png';  Dest = '.' },
  @{ Name = 'build_v5.py';           Dest = 'generator' },
  @{ Name = 'src_v5.html';           Dest = 'generator' },
  @{ Name = 'adv2.js';               Dest = 'generator' },
  @{ Name = 'prep.py';               Dest = '.github' },
  @{ Name = 'verify_site.py';        Dest = '.github' },
  @{ Name = 'main.cpp';              Dest = 'FIRMWARE\src' },
  @{ Name = 'scale.h';               Dest = 'FIRMWARE\src' },
  @{ Name = 'panel.h';               Dest = 'FIRMWARE\src' },
  @{ Name = 'panel_v5.h';            Dest = 'FIRMWARE\src' },
  @{ Name = 'platformio.ini';        Dest = 'FIRMWARE' }
)

# ---------------------------------------------------------------------------
$Root = $PSScriptRoot
if (-not $Root) { $Root = (Get-Location).Path }

# Refuse to run anywhere that is not the repo. Routing files into the wrong
# folder is worse than not routing them, because it looks like it worked.
if (-not (Test-Path -LiteralPath (Join-Path $Root '.git'))) {
  Write-Host ('  no .git in ' + $Root) -ForegroundColor Red
  Write-Host '  bp-sync.ps1 must live in the repo root. Move it there and run it again.' -ForegroundColor Red
  exit 1
}
if (-not (Test-Path -LiteralPath (Join-Path $Root 'index.html'))) {
  Write-Host ('  no index.html in ' + $Root + ', this does not look like the BrewPilot repo.') -ForegroundColor Red
  exit 1
}

function Get-DownloadsFolder {
  try {
    $k = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders'
    $g = '{374DE290-123F-4565-9164-39C4925E467B}'
    $v = (Get-ItemProperty -Path $k -Name $g -ErrorAction Stop).$g
    if ($v) {
      $x = [Environment]::ExpandEnvironmentVariables($v)
      if (Test-Path -LiteralPath $x -PathType Container) { return $x }
    }
  } catch { }
  return (Join-Path $env:USERPROFILE 'Downloads')
}

function Find-Download {
  # Browsers append " (1)" on a repeat download. Match those and take the newest.
  param([string]$Dir, [string]$Name)
  $base = [System.IO.Path]::GetFileNameWithoutExtension($Name)
  $ext  = [System.IO.Path]::GetExtension($Name)
  $rx = '^' + [regex]::Escape($base) + '( \(\d+\))?' + [regex]::Escape($ext) + '$'
  return Get-ChildItem -LiteralPath $Dir -File -ErrorAction SilentlyContinue |
         Where-Object { $_.Name -match $rx } |
         Sort-Object LastWriteTime -Descending |
         Select-Object -First 1
}

if (-not $Downloads) { $Downloads = Get-DownloadsFolder }
if (-not (Test-Path -LiteralPath $Downloads -PathType Container)) {
  Write-Host ('  Downloads folder not found: ' + $Downloads) -ForegroundColor Red
  exit 1
}

$BakDir = Join-Path $Root '_scratch\_bak'

Write-Host ''
Write-Host ('  from  ' + $Downloads) -ForegroundColor DarkGray
Write-Host ('  into  ' + $Root) -ForegroundColor DarkGray
if ($DryRun) { Write-Host '  DRY RUN, nothing will be written' -ForegroundColor Yellow }
Write-Host ''

$moved = @()
$skipped = @()
$repoTouched = $false
$now = Get-Date

foreach ($r in $ROUTES) {
  $f = Find-Download -Dir $Downloads -Name $r.Name
  if (-not $f) { continue }

  $ageH = [math]::Round(($now - $f.LastWriteTime).TotalHours, 1)
  if ($ageH -gt $MaxAgeHours -and -not $Force) {
    $skipped += ('{0}  stale, {1}h old, use -Force to take it anyway' -f $r.Name, $ageH)
    continue
  }

  if ($r.Dest -like 'FIRMWARE*') {
    if (-not $FirmwareDir) {
      $skipped += ('{0}  no -FirmwareDir given, left in Downloads' -f $r.Name)
      continue
    }
    if (-not (Test-Path -LiteralPath $FirmwareDir -PathType Container)) {
      $skipped += ('{0}  FirmwareDir is not a folder: {1}' -f $r.Name, $FirmwareDir)
      continue
    }
    # A PlatformIO project has a platformio.ini. Without this check a wrong
    # -FirmwareDir would quietly create a src\ folder somewhere harmless-looking
    # and the flash would keep using the real, unchanged source.
    if (-not (Test-Path -LiteralPath (Join-Path $FirmwareDir 'platformio.ini'))) {
      $skipped += ('{0}  no platformio.ini in {1}, that is not the firmware project' -f $r.Name, $FirmwareDir)
      continue
    }
    $sub = $r.Dest.Substring('FIRMWARE'.Length).TrimStart('\')
    $destDir = if ($sub) { Join-Path $FirmwareDir $sub } else { $FirmwareDir }
  } else {
    $destDir = Join-Path $Root $r.Dest
    $repoTouched = $true
  }

  $target = Join-Path $destDir $r.Name
  $hash = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLower()

  if ($DryRun) {
    Write-Host ('  would place  {0,-22} -> {1}' -f $r.Name, $target)
    $moved += ('{0,-22} {1,9} bytes  {2}' -f $r.Name, $f.Length, $hash.Substring(0, 16))
    continue
  }

  try {
    if (-not (Test-Path -LiteralPath $destDir)) {
      New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }
    if (Test-Path -LiteralPath $target) {
      if (-not (Test-Path -LiteralPath $BakDir)) {
        New-Item -ItemType Directory -Path $BakDir -Force | Out-Null
      }
      $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
      Copy-Item -LiteralPath $target -Destination (Join-Path $BakDir ($r.Name + '.' + $stamp + '.bak')) -Force
    }
    Copy-Item -LiteralPath $f.FullName -Destination $target -Force
    # Only now is it safe to take it out of Downloads.
    Remove-Item -LiteralPath $f.FullName -Force
    $extra = ''
    if ($r.Name -eq 'main.cpp') {
      # Surface FW_VERSION. /state reports it, so an unbumped version is the
      # difference between knowing what is running and guessing.
      $fw = Select-String -LiteralPath $target -Pattern 'define\s+FW_VERSION\s+"([^"]+)"' |
            Select-Object -First 1
      if ($fw) { $extra = '  FW_VERSION ' + $fw.Matches[0].Groups[1].Value }
    }
    $moved += ('{0,-22} {1,9} bytes  {2}{3}' -f $r.Name, $f.Length, $hash.Substring(0, 16), $extra)
  } catch {
    $skipped += ('{0}  failed: {1}' -f $r.Name, $_.Exception.Message)
  }
}

if ($moved.Count -eq 0) {
  Write-Host '  nothing to route. No known BrewPilot files in Downloads.' -ForegroundColor Yellow
} else {
  Write-Host '  placed:' -ForegroundColor Green
  foreach ($m in $moved) { Write-Host ('    ' + $m) }
}
if ($skipped.Count -gt 0) {
  Write-Host ''
  Write-Host '  skipped:' -ForegroundColor Yellow
  foreach ($s in $skipped) { Write-Host ('    ' + $s) }
}
Write-Host ''

if ($DryRun -or $moved.Count -eq 0) { exit 0 }

if (-not $repoTouched) {
  Write-Host '  firmware only, nothing in the repo changed. Not publishing.' -ForegroundColor Cyan
  Write-Host ''
  Write-Host '  Build and flash:' -ForegroundColor Cyan
  Write-Host ("    cd '" + $FirmwareDir + "'")
  Write-Host '    python -m platformio run'
  Write-Host '    python -m platformio run --target upload'
  Write-Host ''
  exit 0
}

Push-Location -LiteralPath $Root
try {
  Write-Host '  git status' -ForegroundColor Cyan
  git status --short
  Write-Host ''
} finally {
  Pop-Location
}

if (-not $Message) {
  Write-Host '  Files are in place. Publish when ready:' -ForegroundColor Cyan
  Write-Host ''
  Write-Host ("    cd '" + $Root + "'")
  Write-Host "    .\publish.ps1 -Message 'what changed'"
  Write-Host ''
  exit 0
}

# The paste pipeline strips colons and double quotes out of a message argument,
# which silently truncates the commit message. Strip them here and say so.
$clean = ($Message -replace '[:"]', '').Trim()
if ($clean -ne $Message.Trim()) {
  Write-Host '  note: colons and double quotes removed from the message' -ForegroundColor DarkGray
}
if (-not $clean) {
  Write-Host '  message was empty after cleaning, nothing published.' -ForegroundColor Yellow
  exit 0
}

$pub = Join-Path $Root 'publish.ps1'
if (-not (Test-Path -LiteralPath $pub)) {
  Write-Host '  publish.ps1 not found, nothing published.' -ForegroundColor Yellow
  exit 0
}

Push-Location -LiteralPath $Root
try {
  & $pub -Message $clean
  $code = $LASTEXITCODE
} finally {
  Pop-Location
}
if ($code -and $code -ne 0) { exit $code }
exit 0

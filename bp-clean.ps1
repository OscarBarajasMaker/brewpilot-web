#Requires -Version 5.1
<#
  bp-clean.ps1

  Retires the stale build_v5.py / src_v5.html copies so a future session cannot
  pick the wrong one. Two stale locations as of 2026-07-25:

    C:\Users\oscar\BrewPilot-src              old source folder, superseded
    C:\Users\oscar\Downloads\Publish          generator copies inside the repo

  The current source folder is C:\Users\oscar\BrewPilot\source and this script
  refuses to touch it.

  Nothing is deleted. Everything moves to a timestamped quarantine folder, so
  every step here is reversible with a Move-Item. Delete the quarantine yourself
  in a week when nothing has gone wrong.

  Report only (default):  .\bp-clean.ps1
  Actually move:          .\bp-clean.ps1 -Apply

  Files that git is tracking are SKIPPED unless you pass -IncludeTracked,
  because moving a tracked file stages a deletion and the next publish would
  commit it. That is a change to what the repo contains and it is your call,
  not this script's.
#>
[CmdletBinding()]
param(
  [switch]$Apply,
  [switch]$IncludeTracked,
  [string]$CurrentSource = 'C:\Users\oscar\BrewPilot\source',
  [string]$OldSource     = 'C:\Users\oscar\BrewPilot-src',
  [string]$PublishDir    = 'C:\Users\oscar\Downloads\Publish'
)

$ErrorActionPreference = 'Stop'
$GEN = @('build_v5.py', 'src_v5.html')

function Norm {
  param([string]$p)
  if (-not $p) { return '' }
  if (-not (Test-Path -LiteralPath $p)) { return $p.TrimEnd('\') }
  return (Resolve-Path -LiteralPath $p).Path.TrimEnd('\')
}
function Short {
  param([string]$f)
  if (-not (Test-Path -LiteralPath $f)) { return '' }
  return (Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash.Substring(0, 12).ToLower()
}
function Stamp {
  param([string]$f)
  if (-not (Test-Path -LiteralPath $f)) { return $null }
  return (Get-Item -LiteralPath $f).LastWriteTime
}

# --------------------------------------------------------------------------
# The primary has to be sound BEFORE anything is retired. Removing the spare
# copies while the one you are keeping is missing or older is how a cleanup
# turns into a data loss.
# --------------------------------------------------------------------------
$cur = Norm $CurrentSource
if (-not (Test-Path -LiteralPath $cur -PathType Container)) {
  Write-Host ('  current source folder does not exist: ' + $cur) -ForegroundColor Red
  Write-Host '  nothing retired.' -ForegroundColor Red
  exit 1
}
$curTimes = @{}
foreach ($g in $GEN) {
  $p = Join-Path $cur $g
  if (-not (Test-Path -LiteralPath $p)) {
    Write-Host ('  current source is missing ' + $g + ' -> refusing to retire any spare copy.') -ForegroundColor Red
    exit 1
  }
  $curTimes[$g] = (Get-Item -LiteralPath $p).LastWriteTime
}

Write-Host ''
Write-Host '  keeping (current source)' -ForegroundColor Cyan
foreach ($g in $GEN) {
  $p = Join-Path $cur $g
  Write-Host ('    {0,-14} {1}  {2}' -f $g, $curTimes[$g].ToString('MM-dd HH:mm'), (Short $p))
}
Write-Host ''

# --------------------------------------------------------------------------
# Build the candidate list.
# --------------------------------------------------------------------------
$cands = @()

$old = Norm $OldSource
if ($old -eq $cur) {
  Write-Host '  OldSource resolves to the current source folder. Refusing.' -ForegroundColor Red
  exit 1
}
if (Test-Path -LiteralPath $old -PathType Container) {
  $cands += [pscustomobject]@{ Kind = 'folder'; Path = $old; Name = (Split-Path -Leaf $old); Bucket = 'BrewPilot-src' }
}

$pub = Norm $PublishDir
if ($pub -eq $cur) {
  Write-Host '  PublishDir resolves to the current source folder. Refusing.' -ForegroundColor Red
  exit 1
}
if (Test-Path -LiteralPath $pub -PathType Container) {
  foreach ($g in $GEN) {
    $p = Join-Path $pub $g
    if (Test-Path -LiteralPath $p -PathType Leaf) {
      $cands += [pscustomobject]@{ Kind = 'file'; Path = $p; Name = $g; Bucket = 'Publish' }
    }
  }
}

if ($cands.Count -eq 0) {
  Write-Host '  nothing stale found. Already clean.' -ForegroundColor Green
  exit 0
}

# --------------------------------------------------------------------------
# Refuse to retire anything NEWER than what is being kept. A newer spare is not
# a stale copy, it is work that never made it back to the source folder.
# --------------------------------------------------------------------------
$newer = @()
foreach ($c in $cands) {
  foreach ($g in $GEN) {
    $p = if ($c.Kind -eq 'folder') { Join-Path $c.Path $g } else { $c.Path }
    if ($c.Kind -eq 'file' -and $c.Name -ne $g) { continue }
    $t = Stamp $p
    if ($t -and $t -gt $curTimes[$g]) {
      $newer += ('    ' + $p + '  is ' + [math]::Round(($t - $curTimes[$g]).TotalMinutes) + ' min NEWER than the copy you are keeping')
    }
  }
}
if ($newer.Count -gt 0) {
  Write-Host '  ABORTING. A copy marked stale is newer than the current source:' -ForegroundColor Red
  $newer | ForEach-Object { Write-Host $_ -ForegroundColor Red }
  Write-Host ''
  Write-Host '  Work out which one is real before retiring anything.' -ForegroundColor Red
  exit 1
}

# --------------------------------------------------------------------------
# git tracking. Moving a tracked file stages a deletion the next publish would
# commit, which changes what the repo contains.
# --------------------------------------------------------------------------
function Test-Tracked {
  param([string]$Repo, [string]$Rel)
  if (-not (Test-Path -LiteralPath (Join-Path $Repo '.git'))) { return $false }
  Push-Location -LiteralPath $Repo
  try {
    $null = & git ls-files --error-unmatch -- $Rel 2>$null
    return ($LASTEXITCODE -eq 0)
  } catch {
    return $false
  } finally {
    Pop-Location
  }
}

$plan = @()
foreach ($c in $cands) {
  $tracked = $false
  if ($c.Bucket -eq 'Publish') { $tracked = Test-Tracked -Repo $pub -Rel $c.Name }
  $act = 'retire'
  if ($tracked -and -not $IncludeTracked) { $act = 'skip, git-tracked' }
  $plan += [pscustomobject]@{
    Path = $c.Path; Kind = $c.Kind; Bucket = $c.Bucket; Name = $c.Name
    Tracked = $tracked; Action = $act
  }
}

Write-Host '  retiring' -ForegroundColor Cyan
foreach ($p in $plan) {
  $extra = ''
  if ($p.Kind -eq 'file') {
    $extra = '  ' + (Stamp $p.Path).ToString('MM-dd HH:mm') + '  ' + (Short $p.Path)
  }
  $col = 'Gray'
  if ($p.Action -ne 'retire') { $col = 'Yellow' }
  Write-Host ('    {0,-10} {1,-52}{2}' -f $p.Action, $p.Path, $extra) -ForegroundColor $col
}
Write-Host ''

if (-not $Apply) {
  Write-Host '  REPORT ONLY. Nothing moved. Add -Apply to do it.' -ForegroundColor Yellow
  Write-Host ''
  exit 0
}

# --------------------------------------------------------------------------
# Move, never delete.
# --------------------------------------------------------------------------
$quar = Join-Path (Split-Path -Parent $cur) ('_retired\' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $quar -Force | Out-Null

$done = 0
foreach ($p in $plan) {
  if ($p.Action -ne 'retire') { continue }
  $destDir = Join-Path $quar $p.Bucket
  if (-not (Test-Path -LiteralPath $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
  $dest = Join-Path $destDir $p.Name
  try {
    Move-Item -LiteralPath $p.Path -Destination $dest -Force
    Write-Host ('    moved  ' + $p.Path) -ForegroundColor Green
    $done++
  } catch {
    Write-Host ('    FAILED ' + $p.Path + '  ' + $_.Exception.Message) -ForegroundColor Red
  }
}

Write-Host ''
Write-Host ('  ' + $done + ' item(s) retired to:') -ForegroundColor Green
Write-Host ('    ' + $quar)
Write-Host ''
Write-Host '  Nothing was deleted. To undo, move it back. To finish the job in a' -ForegroundColor DarkGray
Write-Host '  week once nothing has broken:' -ForegroundColor DarkGray
Write-Host ("    Remove-Item -Recurse -Force '" + $quar + "'") -ForegroundColor DarkGray
Write-Host ''

if ($plan | Where-Object { $_.Tracked -and $_.Action -eq 'retire' }) {
  Write-Host '  A git-tracked file was moved. Your repo now shows a staged deletion,' -ForegroundColor Yellow
  Write-Host '  which the next publish will commit. Check before you push:' -ForegroundColor Yellow
  Write-Host ("    cd '" + $pub + "'; git status --short") -ForegroundColor Yellow
  Write-Host ''
}
exit 0

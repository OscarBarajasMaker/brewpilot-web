#Requires -Version 5.1
<#
  pull-shot.ps1

  Pulls raw shot JSON straight off the Gaggiuino and saves it untouched.

      .\pull-shot.ps1 -Id 120,95
      .\pull-shot.ps1 -Id 119 -Machine 192.168.31.252
      .\pull-shot.ps1 -List

  WHY -OutFile AND NOT Invoke-RestMethod

  Invoke-RestMethod parses the body, and on this API that is destructive: the
  status endpoint comes back as a bare array and PowerShell wraps it in a fake
  value/Count object. The shot endpoint returns datapoints as an OBJECT OF
  PARALLEL ARRAYS of x10 integers, which is not what the web GUI's download
  gives you, and any reshaping on the way to disk makes the capture useless for
  checking a detector. -OutFile writes the bytes the machine sent, full stop.
  The summary afterwards parses a COPY for display only.

  Files land in _scratch\shots, which is gitignored.
#>
[CmdletBinding()]
param(
  [int[]]$Id,
  [string]$Machine = '192.168.31.252',
  [string]$OutDir = '',
  [switch]$List
)

$ErrorActionPreference = 'Stop'
$base = 'http://' + $Machine

if (-not $OutDir) {
  $root = $PSScriptRoot
  if (-not $root) { $root = (Get-Location).Path }
  $OutDir = Join-Path $root '_scratch\shots'
}
if (-not (Test-Path -LiteralPath $OutDir)) {
  New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}

function Get-LatestId {
  try {
    $r = Invoke-WebRequest -Uri ($base + '/api/shots/latest') -TimeoutSec 8 -UseBasicParsing
    # Bare array: [{"lastShotId":N}]. Parse the RAW content, not a wrapped copy.
    $j = $r.Content | ConvertFrom-Json
    if ($j -is [array]) { return [int]$j[0].lastShotId }
    return [int]$j.lastShotId
  } catch {
    return -1
  }
}

Write-Host ''
Write-Host ('  machine  ' + $base) -ForegroundColor DarkGray
$latest = Get-LatestId
if ($latest -lt 0) {
  Write-Host '  no answer. Is the machine on and on the same network?' -ForegroundColor Red
  Write-Host ('    Test-NetConnection ' + $Machine + ' -Port 80')
  Write-Host ''
  exit 1
}
Write-Host ('  latest   shot #' + $latest) -ForegroundColor DarkGray
Write-Host ('  into     ' + $OutDir) -ForegroundColor DarkGray
Write-Host ''

if ($List -or -not $Id) {
  Write-Host '  Pass the ids you want:' -ForegroundColor Cyan
  Write-Host '    .\pull-shot.ps1 -Id 120,95'
  Write-Host ''
  exit 0
}

$saved = @()
foreach ($n in $Id) {
  $out = Join-Path $OutDir ('shot' + $n + '.json')
  try {
    Invoke-WebRequest -Uri ($base + '/api/shots/' + $n) -TimeoutSec 20 -UseBasicParsing -OutFile $out
  } catch {
    Write-Host ('  shot ' + $n + '  FAILED: ' + $_.Exception.Message) -ForegroundColor Red
    continue
  }

  $bytes = (Get-Item -LiteralPath $out).Length
  if ($bytes -lt 200) {
    Write-Host ('  shot ' + $n + '  suspiciously small (' + $bytes + ' bytes), probably not a shot') -ForegroundColor Yellow
    continue
  }

  # Summary only. The file on disk is already the untouched bytes.
  $j = $null
  try { $j = Get-Content -LiteralPath $out -Raw | ConvertFrom-Json } catch { }
  Write-Host ('  shot ' + $n + '  ' + $bytes + ' bytes  -> ' + (Split-Path -Leaf $out)) -ForegroundColor Green
  if ($null -eq $j) {
    Write-Host '      could not parse for the summary, but the raw file is saved' -ForegroundColor Yellow
    $saved += $out
    continue
  }

  $dur = 0
  if ($null -ne $j.duration) { $dur = [double]$j.duration / 10.0 }
  Write-Host ('      duration ' + $dur.ToString('0.0') + 's')

  $dp = $j.datapoints
  if ($null -eq $dp) {
    Write-Host '      NO datapoints object. This is not the raw API shape.' -ForegroundColor Yellow
    $saved += $out
    continue
  }

  # Which arrays came back, and how long. The metrics that need weightFlow,
  # waterPumped or shotWeight simply cannot be computed without a scale, so an
  # empty or all-zero array here explains a missing metric better than any guess.
  $names = @('timeInShot','pressure','pumpFlow','temperature','shotWeight',
             'weightFlow','waterPumped','targetPressure','targetPumpFlow','targetTemperature')
  foreach ($k in $names) {
    $a = $dp.$k
    if ($null -eq $a) {
      Write-Host ('      ' + $k.PadRight(18) + 'absent') -ForegroundColor DarkGray
      continue
    }
    $cnt = @($a).Count
    $nz = @($a | Where-Object { $_ -ne 0 }).Count
    $line = '      ' + $k.PadRight(18) + $cnt.ToString().PadLeft(4) + ' samples, ' + $nz.ToString().PadLeft(4) + ' nonzero'
    if ($nz -eq 0) { Write-Host $line -ForegroundColor Yellow } else { Write-Host $line }
  }
  $saved += $out
}

Write-Host ''
if ($saved.Count) {
  Write-Host '  Saved:' -ForegroundColor Green
  foreach ($f in $saved) { Write-Host ('    ' + $f) }
  Write-Host ''
  Write-Host '  Upload these to the chat as they are. Do not open and re-save them:' -ForegroundColor Cyan
  Write-Host '  an editor that reformats or re-encodes changes the bytes the detector' -ForegroundColor Cyan
  Write-Host '  has to be tuned against.' -ForegroundColor Cyan
} else {
  Write-Host '  nothing saved.' -ForegroundColor Yellow
}
Write-Host ''

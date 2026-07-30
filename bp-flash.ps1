<#
  bp-flash.ps1 - build, upload and CONFIRM the firmware actually changed.

  Run bp-sync.ps1 first. That is what moves main.cpp out of Downloads into
  <FirmwareDir>\src and backs up the copy it replaces. This script does not
  touch Downloads at all; it builds what is already in the project.

      .\bp-flash.ps1 -DryRun         show every command, run none of them
      .\bp-flash.ps1                 build, upload, verify
      .\bp-flash.ps1 -Port COM5      when auto-detect picks the wrong port
      .\bp-flash.ps1 -BuildOnly      compile and stop, no upload
      .\bp-flash.ps1 -Quarantine     also move the stale root main.cpp aside

  Why the verify step exists: a flash that silently uploads the same source is
  indistinguishable from a flash that worked. FW_VERSION in the source is read
  BEFORE the build and compared against what the device reports afterwards. If
  the source version already matches what is running, the script refuses to
  start, because after that upload /state could not tell you anything.

  Nothing is ever deleted. -Quarantine MOVES, it does not remove.
#>

param(
  [string]$FirmwareDir = 'C:\Users\oscar\Downloads\espressocopilot',
  [string]$PioEnv      = 'esp32dev',
  [string]$Port        = '',
  [string]$Device      = 'brewpilot.local',
  [string]$DeviceIp    = '192.168.31.125',
  [int]   $WaitSec     = 60,
  [switch]$DryRun,
  [switch]$BuildOnly,
  [switch]$SkipVerify,
  [switch]$Quarantine,
  [switch]$Force
)

$ErrorActionPreference = 'Stop'

$Pio     = 'python -m platformio'
$SrcMain = Join-Path $FirmwareDir 'src\main.cpp'
$Ini     = Join-Path $FirmwareDir 'platformio.ini'
$RootDup = Join-Path $FirmwareDir 'main.cpp'
$QuarDir = Join-Path $FirmwareDir '_quarantine'

function Say  ([string]$m, [string]$c = 'Gray')   { Write-Host ('  ' + $m) -ForegroundColor $c }
function Die  ([string]$m) { Write-Host ''; Write-Host ('  ' + $m) -ForegroundColor Red; Write-Host ''; exit 1 }

Write-Host ''
Write-Host '  bp-flash' -ForegroundColor Cyan
Say ('project  ' + $FirmwareDir) 'DarkGray'
if ($DryRun) { Say 'DRY RUN, nothing will be built, uploaded or moved' 'Yellow' }
Write-Host ''

# ---------------------------------------------------------------------------
# 1. the project is really a PlatformIO project
# ---------------------------------------------------------------------------
if (-not (Test-Path -LiteralPath $FirmwareDir -PathType Container)) { Die ('not a folder: ' + $FirmwareDir) }
if (-not (Test-Path -LiteralPath $Ini))     { Die ('no platformio.ini in ' + $FirmwareDir + ', that is not the firmware project') }
if (-not (Test-Path -LiteralPath $SrcMain)) { Die ('no src\main.cpp in ' + $FirmwareDir + '. Run bp-sync.ps1 first.') }

# ---------------------------------------------------------------------------
# 2. FW_VERSION from the source that is about to be compiled
# ---------------------------------------------------------------------------
$m = Select-String -LiteralPath $SrcMain -Pattern 'define\s+FW_VERSION\s+"([^"]+)"' | Select-Object -First 1
if (-not $m) { Die 'no FW_VERSION define found in src\main.cpp' }
$SrcFw = $m.Matches[0].Groups[1].Value
Say ('source FW_VERSION  ' + $SrcFw) 'White'

# ---------------------------------------------------------------------------
# 3. the stale duplicate. platformio builds src\, so a main.cpp in the project
#    root is dead weight, but it is the file that gets opened by accident.
# ---------------------------------------------------------------------------
if (Test-Path -LiteralPath $RootDup) {
  $dupFw = ''
  $d = Select-String -LiteralPath $RootDup -Pattern 'define\s+FW_VERSION\s+"([^"]+)"' | Select-Object -First 1
  if ($d) { $dupFw = $d.Matches[0].Groups[1].Value }
  Say ('stale duplicate    ' + $RootDup + '  FW_VERSION ' + $dupFw) 'Yellow'
  Say 'platformio builds src\ only, so this file is never compiled. Do not edit it.' 'DarkGray'
  if ($Quarantine) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $dest  = Join-Path $QuarDir ('main.cpp.' + $stamp + '.root')
    if ($DryRun) {
      Say ('would move  ' + $RootDup + '  ->  ' + $dest) 'Yellow'
    } else {
      if (-not (Test-Path -LiteralPath $QuarDir)) { New-Item -ItemType Directory -Path $QuarDir -Force | Out-Null }
      Move-Item -LiteralPath $RootDup -Destination $dest -Force
      Say ('moved to ' + $dest) 'Green'
    }
  } else {
    Say 'pass -Quarantine to move it aside' 'DarkGray'
  }
}

# ---------------------------------------------------------------------------
# 4. what is running RIGHT NOW. Read before the flash, not after, so an
#    unbumped version is caught before the one piece of evidence is gone.
# ---------------------------------------------------------------------------
function Get-DeviceFw {
  foreach ($h in @($Device, $DeviceIp)) {
    if (-not $h) { continue }
    try {
      $r = Invoke-RestMethod -Uri ('http://' + $h + '/state') -TimeoutSec 4
      if ($r.fw) { return @{ fw = $r.fw; host = $h } }
    } catch { }
  }
  return $null
}

$before = $null
if (-not $SkipVerify) {
  $before = Get-DeviceFw
  if ($before) {
    Say ('device now says    ' + $before.fw + '   via ' + $before.host) 'White'
    if ($before.fw -eq $SrcFw -and -not $Force) {
      Write-Host ''
      Say 'REFUSING TO FLASH' 'Red'
      Say ('The source and the running device both say ' + $SrcFw + '.') 'Red'
      Say 'After this upload /state would report the same string either way, so' 'Red'
      Say 'there would be no way to tell a good flash from a failed one.' 'Red'
      Say 'Bump FW_VERSION in src\main.cpp, or pass -Force to flash blind.' 'Yellow'
      Write-Host ''
      exit 1
    }
  } else {
    Say 'device unreachable, cannot read the current version. Verify will be skipped.' 'Yellow'
  }
}

# ---------------------------------------------------------------------------
# 5. build, then upload. Separate steps so a compile error never reaches the
#    serial port and half-writes anything.
# ---------------------------------------------------------------------------
Push-Location $FirmwareDir
try {
  $buildCmd = ($Pio + ' run -e ' + $PioEnv)
  $upArgs   = ' run -e ' + $PioEnv + ' -t upload'
  if ($Port) { $upArgs += ' --upload-port ' + $Port }
  $upCmd = $Pio + $upArgs

  Write-Host ''
  Say 'build' 'Cyan'
  Say ('> ' + $buildCmd) 'DarkGray'
  if (-not $DryRun) {
    & python -m platformio run -e $PioEnv
    if ($LASTEXITCODE -ne 0) { Die ('build failed, exit ' + $LASTEXITCODE + '. Nothing was uploaded.') }
    Say 'build ok' 'Green'
  }

  # No Pop-Location here. exit runs the finally block, which pops once. Popping
  # twice would leave the caller in whatever directory was underneath.
  if ($BuildOnly) { Say 'BuildOnly, stopping here' 'Yellow'; Write-Host ''; exit 0 }

  Write-Host ''
  Say 'upload' 'Cyan'
  Say ('> ' + $upCmd) 'DarkGray'
  if (-not $DryRun) {
    if ($Port) { & python -m platformio run -e $PioEnv -t upload --upload-port $Port }
    else       { & python -m platformio run -e $PioEnv -t upload }
    if ($LASTEXITCODE -ne 0) { Die ('upload failed, exit ' + $LASTEXITCODE) }
    Say 'upload ok' 'Green'
  }
}
finally {
  Pop-Location
}

if ($DryRun) { Write-Host ''; Say 'dry run complete' 'Yellow'; Write-Host ''; exit 0 }

# ---------------------------------------------------------------------------
# 6. confirm. The device reboots, joins WiFi, then answers /state.
# ---------------------------------------------------------------------------
if ($SkipVerify) { Write-Host ''; Say 'SkipVerify, done' 'Yellow'; Write-Host ''; exit 0 }

Write-Host ''
Say ('waiting for the device to come back, up to ' + $WaitSec + 's') 'Cyan'
$deadline = (Get-Date).AddSeconds($WaitSec)
$after = $null
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 3
  $after = Get-DeviceFw
  if ($after) { break }
  Write-Host '.' -NoNewline -ForegroundColor DarkGray
}
Write-Host ''

if (-not $after) {
  Write-Host ''
  Say ('no answer from ' + $Device + ' or ' + $DeviceIp + ' within ' + $WaitSec + 's.') 'Yellow'
  Say 'The upload reported success, so it is probably still joining WiFi.' 'Yellow'
  Say ('Check by hand:  curl http://' + $DeviceIp + '/state') 'Yellow'
  Write-Host ''
  exit 2
}

Write-Host ''
if ($after.fw -eq $SrcFw) {
  Say ('CONFIRMED  running ' + $after.fw + '  via ' + $after.host) 'Green'
  if ($before) { Say ('was        ' + $before.fw) 'DarkGray' }
} else {
  Say 'VERSION MISMATCH' 'Red'
  Say ('source says  ' + $SrcFw) 'Red'
  Say ('device says  ' + $after.fw) 'Red'
  Say 'The upload succeeded but the device is not running this source. Likely a' 'Red'
  Say 'second copy of the project, or the board booted the old partition.' 'Red'
  Write-Host ''
  exit 1
}
Write-Host ''

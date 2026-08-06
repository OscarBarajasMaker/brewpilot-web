<#
  gag-ws.ps1 - find the Gaggiuino WebSocket and dump raw frames to a file.

  Purpose: capture the ACTUAL wire format before a line of firmware is written
  against it. The release notes say docs/WEBSOCKET.md exists but it is two days
  old and not reachable from where I sit, and building a parser against a
  guessed schema is how you get a green build that decodes garbage.

      .\gag-ws.ps1                    probe every candidate path, then dump 60s
      .\gag-ws.ps1 -Path /ws          skip the probe, connect straight to /ws
      .\gag-ws.ps1 -Seconds 300       dump for 5 minutes, pull a shot mid-way
      .\gag-ws.ps1 -ProbeOnly         just report which paths accept a socket

  Run it, then PULL A SHOT while it is running. The idle frames tell us the
  sensor schema; the shot frames tell us whether in-shot data actually streams,
  which is the whole question.

  Output: gag-ws-<timestamp>.log next to the script, one frame per line, each
  prefixed with milliseconds since connect. Send me that file.

  Needs PowerShell 5.1 or newer. Uses System.Net.WebSockets.ClientWebSocket,
  which ships with .NET on Windows 8 and later. No modules to install.
#>

param(
  [string]$MachineHost = '192.168.31.252',
  [string]$Path        = '',
  [int]   $Seconds     = 60,
  [switch]$ProbeOnly,
  [string]$OutFile     = ''
)

$ErrorActionPreference = 'Stop'

# Candidates, most likely first. If none connect, the endpoint is named
# something else and the log will say so rather than failing silently.
$Candidates = @('/ws', '/api/ws', '/websocket', '/api/websocket', '/socket', '/api/v1/ws')

function Say ([string]$m, [string]$c = 'Gray') { Write-Host ('  ' + $m) -ForegroundColor $c }

Write-Host ''
Write-Host '  gag-ws' -ForegroundColor Cyan
Say ('machine  ' + $MachineHost) 'DarkGray'
Write-Host ''

# ---------------------------------------------------------------------------
# reachability first, so a dead host does not look like a wrong path
# ---------------------------------------------------------------------------
try {
  $st = Invoke-RestMethod -Uri ('http://' + $MachineHost + '/api/system/status') -TimeoutSec 5
  Say 'machine reachable over HTTP' 'Green'
} catch {
  Say ('cannot reach http://' + $MachineHost + '/api/system/status') 'Red'
  Say 'Check the IP, and check the machine is on this network.' 'Red'
  Write-Host ''
  exit 1
}

# ---------------------------------------------------------------------------
# try to open a socket on one path. Returns the connected socket or $null.
# ---------------------------------------------------------------------------
function Try-Connect ([string]$p) {
  $uri = [System.Uri]('ws://' + $MachineHost + $p)
  $sock = New-Object System.Net.WebSockets.ClientWebSocket
  $cts  = New-Object System.Threading.CancellationTokenSource
  $cts.CancelAfter(4000)
  try {
    $sock.ConnectAsync($uri, $cts.Token).GetAwaiter().GetResult()
    if ($sock.State -eq 'Open') { return $sock }
    $sock.Dispose(); return $null
  } catch {
    $sock.Dispose(); return $null
  }
}

$sock = $null
$used = ''

if ($Path) {
  Say ('connecting to ws://' + $MachineHost + $Path) 'Cyan'
  $sock = Try-Connect $Path
  if ($sock) { $used = $Path }
} else {
  Say 'probing candidate paths' 'Cyan'
  foreach ($p in $Candidates) {
    $s = Try-Connect $p
    if ($s) {
      Say ('  OPEN    ' + $p) 'Green'
      if (-not $sock) { $sock = $s; $used = $p } else { $s.Dispose() }
    } else {
      Say ('  refused ' + $p) 'DarkGray'
    }
  }
}

if (-not $sock) {
  Write-Host ''
  Say 'no candidate path accepted a WebSocket.' 'Yellow'
  Say 'The endpoint is named something else. Two ways to find it:' 'Yellow'
  Say '  1. Open http://gaggiuino.local in Chrome, F12, Network tab, filter WS,' 'Yellow'
  Say '     reload. The web UI connects to it and the path will be right there.' 'Yellow'
  Say '  2. Read docs/WEBSOCKET.md in the repo.' 'Yellow'
  Say 'Then rerun with -Path /whatever' 'Yellow'
  Write-Host ''
  exit 2
}

if ($ProbeOnly) {
  Write-Host ''
  Say ('ProbeOnly, connected path is ' + $used) 'Green'
  $sock.Dispose()
  Write-Host ''
  exit 0
}

# ---------------------------------------------------------------------------
# dump
# ---------------------------------------------------------------------------
if (-not $OutFile) {
  $OutFile = Join-Path $PSScriptRoot ('gag-ws-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')
}

Write-Host ''
Say ('connected  ' + $used) 'Green'
Say ('logging to ' + $OutFile) 'White'
Say ('running for ' + $Seconds + 's. PULL A SHOT NOW.') 'Cyan'
Say 'Ctrl-C stops early and keeps whatever was captured.' 'DarkGray'
Write-Host ''

$header = @(
  '# gag-ws capture',
  ('# machine   ' + $MachineHost),
  ('# path      ' + $used),
  ('# started   ' + (Get-Date -Format 'o')),
  '# format    <ms since connect> <TAB> <frame>',
  ''
)
$header | Set-Content -LiteralPath $OutFile -Encoding UTF8

$buffer = New-Object byte[] 16384
$cts    = New-Object System.Threading.CancellationTokenSource
$sw     = [System.Diagnostics.Stopwatch]::StartNew()
$frames = 0
$bytes  = 0

try {
  while ($sw.Elapsed.TotalSeconds -lt $Seconds -and $sock.State -eq 'Open') {
    $sb  = New-Object System.Text.StringBuilder
    $end = $false
    while (-not $end) {
      $seg = New-Object System.ArraySegment[byte] -ArgumentList @(, $buffer)
      $r = $sock.ReceiveAsync($seg, $cts.Token).GetAwaiter().GetResult()
      if ($r.MessageType -eq 'Close') { $end = $true; break }
      [void]$sb.Append([System.Text.Encoding]::UTF8.GetString($buffer, 0, $r.Count))
      $bytes += $r.Count
      $end = $r.EndOfMessage
    }
    $txt = $sb.ToString()
    if ($txt.Length -gt 0) {
      $frames++
      $line = [string][int]$sw.Elapsed.TotalMilliseconds + "`t" + $txt
      Add-Content -LiteralPath $OutFile -Value $line -Encoding UTF8
      # a heartbeat so you can see it is alive without drowning the console
      if ($frames -le 3 -or $frames % 25 -eq 0) {
        $peek = $txt
        if ($peek.Length -gt 110) { $peek = $peek.Substring(0, 110) + ' ...' }
        Say ('[' + $frames + '] ' + $peek) 'DarkGray'
      }
    }
  }
}
catch [System.Management.Automation.PipelineStoppedException] {
  Say 'stopped by user' 'Yellow'
}
catch {
  Say ('receive stopped: ' + $_.Exception.Message) 'Yellow'
}
finally {
  try {
    if ($sock.State -eq 'Open') {
      $c = New-Object System.Threading.CancellationTokenSource
      $c.CancelAfter(2000)
      $sock.CloseAsync('NormalClosure', 'done', $c.Token).GetAwaiter().GetResult()
    }
  } catch { }
  $sock.Dispose()
}

Write-Host ''
Say ('frames  ' + $frames) 'Green'
Say ('bytes   ' + $bytes) 'Green'
Say ('elapsed ' + [int]$sw.Elapsed.TotalSeconds + 's') 'Green'
Say ('saved   ' + $OutFile) 'White'

if ($frames -eq 0) {
  Write-Host ''
  Say 'ZERO FRAMES. The socket opened but nothing was pushed.' 'Yellow'
  Say 'Likely one of: the stream needs a subscribe message first, the machine' 'Yellow'
  Say 'was idle the whole time, or this path is a different socket entirely.' 'Yellow'
  Say 'Rerun and pull a shot while it is running before concluding anything.' 'Yellow'
}
Write-Host ''

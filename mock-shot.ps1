#Requires -Version 5.1
<#
  mock-shot.ps1

  Fires a synthetic shot handoff at BrewPilot, exactly as the firmware would,
  without pulling a shot and without flashing anything.

      .\mock-shot.ps1                     a soup shot at the live site
      .\mock-shot.ps1 -Preset tight       an espresso shot 48% over its lane
      .\mock-shot.ps1 -Preset bare        id and version only, everything absent
      .\mock-shot.ps1 -ShowOnly           print the URL, open nothing

  WHAT THIS DOES AND DOES NOT TEST

  Tests, for real: the app ingests ?bp=1, parses every value, pre-fills the log
  form, strips the query so a reload cannot double-log, writes to your actual
  Google Sheet, files into the lane, and draws the pre-shot card. That whole
  path has only ever been tested against a fake Sheets API.

  Does NOT test: that the DEVICE emits this URL. That needs a flash. What it
  does prove is that when the device does emit it, the receiving half works.

  These parameter values are the four shots already round-tripped through the
  built index.html, so a parse failure here means something changed in the app,
  not in the fixture.

  NOTHING IS SAVED UNTIL YOU PRESS SAVE. The link only pre-fills the form. To
  get a lane you must add a coffee that is in your Inventory, plus dose and
  rating. An unknown coffee will correctly refuse to start a lane and say so.

  The default shot id is 9001 so the test row is easy to find and delete.
#>
[CmdletBinding()]
param(
  [ValidateSet('soup', 'traditional', 'tight', 'sparse', 'bare')]
  [string]$Preset = 'soup',
  [string]$Url = 'https://oscarbarajasmaker.github.io/brewpilot-web/',
  [int]$ShotId = 9001,
  [string]$Fw = 'mock-run',
  [switch]$ShowOnly
)

$ErrorActionPreference = 'Stop'

# Key names are the APP's, read out of bpHandoff(). They are not mnemonic and
# the obvious reading is wrong: t is the TYPE NAME, d is the DURATION, tc is the
# brew TEMPERATURE. There is deliberately no dose parameter; the app asks you.
$PRESETS = @{
  # a traditional shot sitting on its measured baseline (resistance 2.78)
  traditional = [ordered]@{
    t = 'espresso'; d = '31.4'; y = '56.2'; pk = '8.93'; fl = '1.81'
    rs = '2.780'; ad = '0.850'; ch = '0.020'; rt = '3.4'; pi = '2.10'
    fd = '7.8'; us = '-0.120'; te = '-0.80'
  }
  # a low-pressure soup shot, resistance at the low end of the measured pair
  soup = [ordered]@{
    t = 'soup'; d = '27.0'; y = '81.0'; pk = '1.90'; fl = '3.10'
    rs = '0.090'; ad = '0.750'; ch = '0.240'; rt = '2.8'; pi = '1.10'
    fd = '5.2'; te = '-0.40'
  }
  # deliberately 48% above the espresso baseline, so the card must say go coarser
  tight = [ordered]@{
    t = 'espresso'; d = '38.6'; y = '48.1'; pk = '9.40'; fl = '1.24'
    rs = '4.200'; ad = '0.610'; ch = '0.050'; rt = '4.9'; pi = '2.40'
    fd = '11.2'; us = '-0.480'; te = '-1.10'
  }
  # most metrics unavailable, which is what a shot with a short stable window
  # actually produces. The app must leave those columns empty, not zero them.
  sparse = [ordered]@{
    t = 'soup'; d = '27.0'; y = '81.0'; pk = '1.90'; rs = '0.090'; ch = '0.240'
  }
  # nothing but identity. Proves absent stays absent all the way through.
  bare = [ordered]@{}
}

$p = $PRESETS[$Preset]
$q = "bp=1&sid=$ShotId&fw=$Fw"
foreach ($k in $p.Keys) { $q += '&' + $k + '=' + $p[$k] }

$sep = '?'
if ($Url.Contains('?')) { $sep = '&' }
$full = $Url + $sep + $q

Write-Host ''
Write-Host ('  preset   ' + $Preset) -ForegroundColor Cyan
Write-Host ('  shot id  ' + $ShotId + '   (test row, easy to find and delete)') -ForegroundColor DarkGray
Write-Host ('  fields   ' + $(if ($p.Count) { ($p.Keys -join ' ') } else { 'none, identity only' })) -ForegroundColor DarkGray
Write-Host ''
Write-Host $full
Write-Host ''

if ($ShowOnly) {
  Write-Host '  ShowOnly, nothing opened.' -ForegroundColor Yellow
  Write-Host ''
  exit 0
}

Start-Process $full

Write-Host '  Opened. What to check, in order:' -ForegroundColor Green
Write-Host ''
Write-Host '   1. The log tab opens by itself and the banner says shot data received.'
Write-Host '   2. The method chip matches the preset above.'
Write-Host '   3. The address bar has NO ?bp=1 left on it. If it is still there,'
Write-Host '      a reload would log the same shot twice.'
Write-Host '   4. Type a coffee that IS in your Inventory, plus dose and rating,'
Write-Host '      then save. Any other coffee is meant to refuse a lane.'
Write-Host '   5. The banner should then say the lane updated, with a count.'
Write-Host '   6. Open the sheet. Shot Log gets a row at shot_id ' -NoNewline
Write-Host $ShotId -NoNewline
Write-Host ', with the'
Write-Host '      metric columns AC..AL filled. Lanes gets a row keyed coffee|method.'
Write-Host '   7. Come back to the log form, pick the same coffee and method, and'
Write-Host '      the pre-shot card should now show that history.'
Write-Host ''
Write-Host '  If step 5 says the coffee is not in your inventory, that is the'
Write-Host '  identity gate doing its job, not a bug. Register the bag first.' -ForegroundColor DarkGray
Write-Host ''
Write-Host '  Delete the test rows afterwards, or the mock numbers become part of'
Write-Host '  a real baseline.' -ForegroundColor Yellow
Write-Host ''

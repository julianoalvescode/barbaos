<#
  BarbaOS - installer (Windows)
  by Barba777

  Applies the BarbaOS customizations to an SD card that already runs
  dArkOS4Clone / ArkOS4Clone, without erasing your games.

  Usage (PowerShell, in the repo folder):
    .\install.ps1 -Boot D: -Roms E:
    .\install.ps1 -Boot D: -Roms E: -FixAudio    # R36S V20 board with no sound
    .\install.ps1 -Boot D: -Roms E: -NoTheme     # skip the EpicAeolus theme

  Everything that gets overwritten is backed up to <Roms>\backup_barbaos\installer_<date>\
#>
param(
  [Parameter(Mandatory = $true)][string]$Boot,
  [Parameter(Mandatory = $true)][string]$Roms,
  [switch]$FixAudio,
  [switch]$NoTheme
)
$ErrorActionPreference = 'Stop'
$Repo = $PSScriptRoot
$Boot = $Boot.TrimEnd('\') + '\'
$Roms = $Roms.TrimEnd('\') + '\'

function Info($m) { Write-Host "[BarbaOS] $m" -ForegroundColor Cyan }
function Ok($m) { Write-Host "  OK  $m" -ForegroundColor Green }

# ---- make sure these are the right partitions
if (-not (Test-Path "$Boot\consoles")) {
  throw "$Boot does not look like the SD card BOOT partition (consoles\ is missing)."
}
if (-not (Test-Path "$Roms\tools") -or -not (Test-Path "$Roms\themes")) {
  throw "$Roms does not look like the EASYROMS partition (tools\ or themes\ is missing)."
}

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$bk = Join-Path $Roms "backup_barbaos\installer_$stamp"
New-Item -ItemType Directory -Force $bk | Out-Null
function Backup($path, $name) {
  if (Test-Path $path) { Copy-Item $path (Join-Path $bk $name) -Force }
}

# ---- 1) boot logo
Info 'Boot logo'
Backup "$Boot\logo.bmp" 'boot_logo.bmp'
Copy-Item "$Repo\boot\logo.bmp" "$Boot\logo.bmp" -Force
if (Test-Path "$Boot\consoles\logo\480P") {
  Backup "$Boot\consoles\logo\480P\logo.bmp" 'logo_480P.bmp'
  Copy-Item "$Repo\boot\logo.bmp" "$Boot\consoles\logo\480P\logo.bmp" -Force
}
Ok 'logo.bmp'

# ---- 2) game loading screen
Info 'Loading screen'
New-Item -ItemType Directory -Force "$Roms\launchimages" | Out-Null
Backup "$Roms\launchimages\loading.jpg" 'loading.jpg'
Backup "$Roms\launchimages\loading.ascii" 'loading.ascii'
Copy-Item "$Repo\easyroms\launchimages\*" "$Roms\launchimages\" -Force
Ok 'loading.jpg / loading.ascii'

# ---- 3) apps
Info 'Apps (Options menu)'
$cfgNow = "$Roms\tools\BarbaDrop\config.json"
$keepCfg = $null
if (Test-Path $cfgNow) { $keepCfg = Get-Content $cfgNow -Raw }
Copy-Item "$Repo\easyroms\tools\*" "$Roms\tools\" -Recurse -Force
if ($keepCfg) {
  [IO.File]::WriteAllText($cfgNow, $keepCfg, (New-Object Text.UTF8Encoding $false))
  Ok 'BarbaDrop (existing config.json kept)'
} else {
  Ok 'BarbaDrop'
}
$old = "$Roms\tools\BarbaOS Marca.sh"
if (Test-Path $old) { Remove-Item $old -Force }
Ok 'BarbaOS Branding'

# ---- 4) audio fix (R36S V20 board)
if ($FixAudio) {
  Info 'Audio fix (profile "clone type1 panel1", no amplifier GPIO)'
  $profile = "$Boot\consoles\clone type1 panel1"
  if (-not (Test-Path $profile)) { throw "Profile not found: $profile" }
  Backup "$Boot\boot.ini" 'boot.ini'
  Get-ChildItem "$Boot\*.dtb" | ForEach-Object { Backup $_.FullName $_.Name }
  Copy-Item "$profile\*" $Boot -Force
  Ok 'boot.ini -> rk3326-r36s-type1-panel1-linux.dtb'
}

# ---- 5) EpicAeolus theme
if (-not $NoTheme) {
  $dest = "$Roms\themes\es-theme-EpicAeolus"
  if (Test-Path "$dest\theme.xml") {
    Info 'EpicAeolus theme already installed'
  } else {
    Info 'Downloading EpicAeolus theme (github.com/AeolusUX/es-theme-EpicAeolus)'
    $tmp = Join-Path $env:TEMP "epicaeolus_$stamp"
    New-Item -ItemType Directory -Force $tmp | Out-Null
    $zip = Join-Path $tmp 't.zip'
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest 'https://github.com/AeolusUX/es-theme-EpicAeolus/archive/refs/heads/main.zip' -OutFile $zip -UseBasicParsing
    Expand-Archive $zip $tmp -Force
    Copy-Item (Join-Path $tmp 'es-theme-EpicAeolus-main') $dest -Recurse -Force
    Remove-Item $tmp -Recurse -Force
    Ok 'es-theme-EpicAeolus (select it on the console: START > UI Settings > Theme Set)'
  }
}

Write-Host ''
Info "Done. Backup in: $bk"
Info 'Safely eject the SD card before removing it from the PC.'

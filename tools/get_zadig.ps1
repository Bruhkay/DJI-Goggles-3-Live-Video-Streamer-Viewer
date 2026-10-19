$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$dest = Join-Path $PSScriptRoot 'zadig.exe'
$releases = Invoke-RestMethod 'https://api.github.com/repos/pbatard/libwdi/releases' -Headers @{ 'User-Agent' = 'goggles3-live' }
$asset = $releases | ForEach-Object { $_.assets } | Where-Object { $_.name -like 'zadig*.exe' } | Select-Object -First 1
if (-not $asset) { exit 1 }
Invoke-WebRequest $asset.browser_download_url -OutFile $dest -UseBasicParsing

param(
    [Parameter(Mandatory=$true)][string]$GameFolder,
    [Parameter(Mandatory=$true)][string]$RunName,
    [string]$OutputFolder = '.\profiles',
    [ValidateSet('auto','on','off')][string]$Batch = 'auto',
    [ValidateSet(0,500,1000,2000,4000,8000)][int]$BatchPollUs = 2000,
    [ValidateSet('auto','off','on')][string]$Mirror = 'auto',
    [ValidateRange(0,6144)][int]$MirrorMB = 0,
    [ValidateSet('auto','0','1')][string]$AsyncImport = 'auto',
    [ValidateSet('auto','1','2','3','4','5','6','7','8')][string]$Parallel = 'auto',
    [switch]$FineTiming,
    [switch]$PassTiming
)
$ErrorActionPreference = 'Stop'
$game = (Resolve-Path $GameFolder).Path
$out = [System.IO.Path]::GetFullPath($OutputFolder)
New-Item -ItemType Directory -Force -Path $out | Out-Null
$exe = Join-Path $game 'bin\hookshot.exe'
if (!(Test-Path $exe)) { $exe = Join-Path $game 'hookshot.exe' }
if (!(Test-Path $exe)) { throw "Could not find hookshot.exe in $game or its bin folder" }
$names = @('RX_VK_BATCH','RX_VK_BATCH_POLL_US','RX_VK_MIRROR','RX_VK_MIRROR_MB','RX_VK_ASYNC_IMPORT','RX_VK_PARALLEL','RX_VK_PROF_FINE','RX_VK_PASS_TIMING','RX_VK_FRAME_LOG')
$old = @{}
foreach ($n in $names) { $old[$n] = [Environment]::GetEnvironmentVariable($n, 'Process') }
$logCopy = Join-Path $out ($RunName + '.log')
$csv = Join-Path $out ($RunName + '.csv')
try {
    if ($Batch -eq 'auto') { Remove-Item Env:RX_VK_BATCH -ErrorAction SilentlyContinue }
    else { $env:RX_VK_BATCH = if ($Batch -eq 'on') { '1' } else { '0' } }
    $env:RX_VK_BATCH_POLL_US = [string]$BatchPollUs
    if ($Mirror -eq 'auto') { Remove-Item Env:RX_VK_MIRROR -ErrorAction SilentlyContinue }
    else { $env:RX_VK_MIRROR = if ($Mirror -eq 'on') { '1' } else { '0' } }
    if ($MirrorMB -gt 0) { $env:RX_VK_MIRROR_MB = [string]$MirrorMB }
    else { Remove-Item Env:RX_VK_MIRROR_MB -ErrorAction SilentlyContinue }
    if ($AsyncImport -eq 'auto') { Remove-Item Env:RX_VK_ASYNC_IMPORT -ErrorAction SilentlyContinue }
    else { $env:RX_VK_ASYNC_IMPORT = $AsyncImport }
    if ($Parallel -eq 'auto') { Remove-Item Env:RX_VK_PARALLEL -ErrorAction SilentlyContinue } else { $env:RX_VK_PARALLEL = $Parallel }
    if ($FineTiming) { $env:RX_VK_PROF_FINE = '1' } else { Remove-Item Env:RX_VK_PROF_FINE -ErrorAction SilentlyContinue }
    if ($PassTiming) { $env:RX_VK_PASS_TIMING = '1' } else { Remove-Item Env:RX_VK_PASS_TIMING -ErrorAction SilentlyContinue }
    $env:RX_VK_FRAME_LOG = $csv
    Write-Host "Starting profile run '$RunName'. Play the same route and duration used for the other variants." -ForegroundColor Cyan
    Write-Host "Sync settings: batch=$Batch, poll=$BatchPollUs us, mirror=$Mirror/$MirrorMB MB, async-import=$AsyncImport, parallel=$Parallel"
    Write-Host 'Fine and pass timing add overhead; keep the same switches enabled for every run being compared.'
    $proc = Start-Process -FilePath $exe -WorkingDirectory $game -PassThru
    Wait-Process -Id $proc.Id
    $sourceLog = Join-Path $game 'hookshot_log.txt'
    if (Test-Path $sourceLog) { Copy-Item $sourceLog $logCopy -Force }
    else { Write-Warning "No hookshot_log.txt found in $game; CSV may still be present." }
    Write-Host "Profile captured: $logCopy" -ForegroundColor Green
    if (Test-Path $csv) { Write-Host "Frame times captured: $csv" }
} finally {
    foreach ($n in $names) {
        [Environment]::SetEnvironmentVariable($n, $old[$n], 'Process')
    }
}

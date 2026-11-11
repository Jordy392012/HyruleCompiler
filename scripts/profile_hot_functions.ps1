param(
    [Parameter(Mandatory=$true)][string]$HookshotRoot,
    [Parameter(Mandatory=$true)][string]$GameFolder
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path $HookshotRoot).Path
$game = (Resolve-Path $GameFolder).Path
$sample = Join-Path $root 'work\runs\hyrule_machine_hot_samples.txt'
$hotList = Join-Path $root 'work\hot_funcs.txt'
$sampleDir = Split-Path $sample -Parent
New-Item -ItemType Directory -Force -Path $sampleDir | Out-Null
Remove-Item $sample, ($sample + '.go') -Force -ErrorAction SilentlyContinue
$gameExe = Join-Path $game 'bin\hookshot.exe'
if (!(Test-Path $gameExe)) { $gameExe = Join-Path $game 'hookshot.exe' }
if (!(Test-Path $gameExe)) { throw "Could not find Hookshot executable in $game or its bin folder" }
Push-Location $root
try {
    $env:HOS_PROFILE = '2'
    $env:HOS_SAMPLE_ALL = $sample
    $env:RX_MAPS = Join-Path $root 'work\sa\build'
    New-Item -ItemType File -Path ($sample + '.go') | Out-Null
    Write-Host 'Launching Hookshot with all-thread CPU sampling enabled.' -ForegroundColor Cyan
    Write-Host 'Play normally for 2-5 minutes in representative areas, then return here and press Enter.'
    $proc = Start-Process -FilePath $gameExe -WorkingDirectory $game -PassThru
    Read-Host 'Press Enter after collecting a representative gameplay sample'
    Remove-Item ($sample + '.go') -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    if (!(Test-Path $sample) -or (Get-Item $sample).Length -eq 0) {
        throw 'No CPU sample was written. Check that this Hookshot build supports HOS_SAMPLE_ALL and that the game was running.'
    }
    & python -I scripts/hotlist.py $sample $hotList 0.85 1500
    if ($LASTEXITCODE -ne 0) { throw 'hotlist.py could not produce work/hot_funcs.txt' }
    Write-Host "Machine-specific hot list written to $hotList" -ForegroundColor Green
    Write-Host 'The next build_variant.ps1 run will compile these functions together using the hot-code optimization flags.'
} finally {
    Remove-Item Env:HOS_PROFILE -ErrorAction SilentlyContinue
    Remove-Item Env:HOS_SAMPLE_ALL -ErrorAction SilentlyContinue
    Remove-Item Env:RX_MAPS -ErrorAction SilentlyContinue
    Remove-Item ($sample + '.go') -Force -ErrorAction SilentlyContinue
    Pop-Location
}

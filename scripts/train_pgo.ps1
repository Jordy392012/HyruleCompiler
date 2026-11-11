param(
    [Parameter(Mandatory=$true)][string]$HookshotRoot,
    [Parameter(Mandatory=$true)][string]$GameFolder,
    [string]$RawProfile = ''
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path $HookshotRoot).Path
$game = (Resolve-Path $GameFolder).Path
if (!(Test-Path (Join-Path $root 'nx2\hyrule_pollpass.py'))) {
    throw 'Hyrule compiler pass is not installed. Run scripts\install_optimizer.py first.'
}
if (!$RawProfile) { $RawProfile = Join-Path $root 'work\hyrule_machine.profraw' }
$raw = [System.IO.Path]::GetFullPath($RawProfile)
$profdata = [System.IO.Path]::ChangeExtension($raw, '.profdata')
$gameExe = Join-Path $game 'bin\hookshot.exe'
if (!(Test-Path $gameExe)) { $gameExe = Join-Path $game 'hookshot.exe' }
if (!(Test-Path $gameExe)) { throw "Could not find Hookshot executable in $game or its bin folder" }
Push-Location $root
try {
    Write-Host 'Step 1/3: building an instrumented PGO-training version.' -ForegroundColor Cyan
    $env:RX_PGO = 'gen'
    $env:A64_POLL_INTERVAL = '1'
    $env:A64_POLL_HOT_ONLY = '1'
    & python -I nx2/make_game.py --update $game
    if ($LASTEXITCODE -ne 0) { throw "Instrumented build failed with exit code $LASTEXITCODE" }
    Write-Host 'Step 2/3: play a representative route, then dump the counters.' -ForegroundColor Cyan
    Remove-Item $raw, ($raw + '.dump'), ($raw + '.reset') -Force -ErrorAction SilentlyContinue
    $env:HOS_PGO = $raw
    New-Item -ItemType File -Path ($raw + '.reset') -Force | Out-Null
    $proc = Start-Process -FilePath $gameExe -WorkingDirectory $game -PassThru
    Read-Host 'Play for several minutes (include the areas and effects you care about), then press Enter to save the profile'
    New-Item -ItemType File -Path ($raw + '.dump') -Force | Out-Null
    Start-Sleep -Seconds 2
    if (!(Test-Path $raw) -or (Get-Item $raw).Length -eq 0) {
        throw "The game did not write $raw. Leave it running until the dump completes and check that HOS_PGO was inherited."
    }
    Write-Host 'Profile data captured. Exit the game normally before continuing.'
    if (!$proc.HasExited) {
        Read-Host 'After closing the game normally, press Enter to continue'
        try { $proc.WaitForExit() } catch {}
    }
    Write-Host 'Step 3/3: merging the raw counters into a compiler profile.' -ForegroundColor Cyan
    $llvmProf = Get-Command llvm-profdata.exe -ErrorAction SilentlyContinue
    if (!$llvmProf) { $llvmProf = Get-Command llvm-profdata -ErrorAction SilentlyContinue }
    if (!$llvmProf -and $env:HOOKSHOT_MINGW) {
        $candidate = Join-Path $env:HOOKSHOT_MINGW 'bin\llvm-profdata.exe'
        if (Test-Path $candidate) { $llvmProf = @{ Source = $candidate } }
    }
    if (!$llvmProf) { throw 'llvm-profdata was not found on PATH or in HOOKSHOT_MINGW\bin. Add the LLVM toolchain bin folder to PATH, then merge the raw profile.' }
    & $llvmProf.Source merge -o $profdata $raw
    if ($LASTEXITCODE -ne 0 -or !(Test-Path $profdata)) { throw 'llvm-profdata merge failed.' }
    Write-Host "Machine-specific profile created: $profdata" -ForegroundColor Green
    Write-Host 'Now build the optimized variant with scripts\build_variant.ps1 -PgoProfile <profdata> -PollInterval 4 or 8.'
} finally {
    Remove-Item Env:RX_PGO -ErrorAction SilentlyContinue
    Remove-Item Env:A64_POLL_INTERVAL -ErrorAction SilentlyContinue
    Remove-Item Env:A64_POLL_HOT_ONLY -ErrorAction SilentlyContinue
    Remove-Item Env:HOS_PGO -ErrorAction SilentlyContinue
    Pop-Location
}

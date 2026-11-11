param(
    [Parameter(Mandatory=$true)][string]$HookshotRoot,
    [Parameter(Mandatory=$true)][string]$GameFolder,
    [ValidateSet(1,2,4,8,16)][int]$PollInterval = 1,
    [ValidateSet('O2','O3')][string]$HotOptimization = 'O2',
    [ValidateSet('auto','znver3','x86-64-v3')][string]$CpuTarget = 'auto',
    [string]$PgoProfile = ''
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path $HookshotRoot).Path
$game = (Resolve-Path $GameFolder).Path
if (!(Test-Path (Join-Path $root 'nx2\hyrule_pollpass.py'))) {
    throw 'Hyrule compiler pass is not installed. Run scripts\install_optimizer.py first.'
}
Push-Location $root
try {
    $env:A64_POLL_INTERVAL = [string]$PollInterval
    $env:A64_POLL_HOT_ONLY = '1'
    $env:RX_HOT_OPT = $HotOptimization
    if ($CpuTarget -eq 'auto') { Remove-Item Env:RX_MARCH -ErrorAction SilentlyContinue } else { $env:RX_MARCH = $CpuTarget }
    if ($PgoProfile) {
        $pgo = (Resolve-Path $PgoProfile).Path
        $env:RX_PGO = $pgo
    } else {
        Remove-Item Env:RX_PGO -ErrorAction SilentlyContinue
    }
    Write-Host "Building Hookshot with Hyrule settings:" -ForegroundColor Cyan
    Write-Host "  hot-loop poll interval: $PollInterval (profile-hot functions only)"
    Write-Host "  hot function optimization: $HotOptimization"
    Write-Host "  CPU code generation target: $CpuTarget"
    Write-Host "  PGO profile: $(if ($PgoProfile) {$PgoProfile} else {'upstream/default profile'})"
    & python -I nx2/make_game.py --update $game
    if ($LASTEXITCODE -ne 0) { throw "Hookshot build failed with exit code $LASTEXITCODE" }
    $stamp = Join-Path $root 'work\hyrule_build_variant.txt'
    @(
        "poll_interval=$PollInterval"
        "poll_hot_only=1"
        "hot_optimization=$HotOptimization"
        "cpu_target=$CpuTarget"
        "pgo_profile=$PgoProfile"
        "built_at=$(Get-Date -Format o)"
    ) | Set-Content -Encoding UTF8 $stamp
    Write-Host "Build complete. Variant record: $stamp" -ForegroundColor Green
} finally {
    Remove-Item Env:A64_POLL_INTERVAL -ErrorAction SilentlyContinue
    Remove-Item Env:A64_POLL_HOT_ONLY -ErrorAction SilentlyContinue
    Remove-Item Env:RX_HOT_OPT -ErrorAction SilentlyContinue
    Remove-Item Env:RX_MARCH -ErrorAction SilentlyContinue
    Remove-Item Env:RX_PGO -ErrorAction SilentlyContinue
    Pop-Location
}

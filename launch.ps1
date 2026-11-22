param(
    [ValidateSet('all','desktop','tech','lab','web','mobile','server')][string]$Target='all',
    [int]$Port=8765,
    [string]$Address
)
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$base="http://127.0.0.1:$Port"

function Test-Ceramika {
    try { return (Invoke-RestMethod "$base/api/health" -TimeoutSec 1).data.status -eq 'online' }
    catch { return $false }
}

function Get-CeramikaPython {
    $runtime = Get-AppxPackage -Name 'OpenAI.CodexPrimaryRuntime*' | Sort-Object Version -Descending | Select-Object -First 1
    $python = if ($runtime) { Join-Path $runtime.InstallLocation 'dependencies/python/python.exe' }
    $prefix = @()
    if (-not $python -or -not (Test-Path -LiteralPath $python)) {
        $command = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($command) { $python=$command.Source; $prefix=@('-3') }
        else {
            $command = Get-Command python.exe -ErrorAction SilentlyContinue
            if (-not $command -or $command.Source -like '*Microsoft\WindowsApps\python.exe') {
                throw 'Install Python 3.10+ or use the bundled Codex runtime.'
            }
            $python=$command.Source
        }
    }
    return @{ Path=$python; Prefix=$prefix }
}

if ($Target -eq 'mobile') {
    if (-not $PSBoundParameters.ContainsKey('Port')) { $Port=8766 }
    if (-not $Address) {
        $configs = @(Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' })
        $preferred = @($configs | Where-Object { $_.NetAdapter.NdisPhysicalMedium -match '802\.11|Wireless' }) + $configs
        $Address = $preferred.IPv4Address.IPAddress | Where-Object {
            $_ -match '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)'
        } | Select-Object -First 1
    }
    if (-not $Address) { throw 'Connect this PC to the local Wi-Fi network first.' }
    $assigned = Get-NetIPAddress -AddressFamily IPv4 -IPAddress $Address -ErrorAction SilentlyContinue
    if ($Address -ne '127.0.0.1' -and -not $assigned) { throw 'Address must be assigned to this PC.' }
    $runtime = Get-CeramikaPython
    Write-Host ''
    Write-Host "Open on your phone: http://${Address}:$Port/mobile" -ForegroundColor Cyan
    Write-Host 'Connect the phone and PC to the same Wi-Fi. Keep this window open.'
    Write-Host 'If Windows Firewall prompts, allow access on Private networks only.'
    Write-Host 'Press Ctrl+C to stop the mobile server.'
    Push-Location -LiteralPath $root
    try {
        $prefix = $runtime.Prefix
        & $runtime.Path @prefix server.py --port $Port --mobile-lan $Address
        if ($LASTEXITCODE -ne 0) { throw "Mobile server could not start at ${Address}:$Port." }
    } finally { Pop-Location }
    return
}

if (-not (Test-Ceramika)) {
    $runtime = Get-CeramikaPython
    $arguments = $runtime.Prefix + @('server.py','--port',$Port)
    $process = Start-Process -FilePath $runtime.Path -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden -PassThru
    $ready = $false
    for ($attempt=0; $attempt -lt 40; $attempt++) {
        if (Test-Ceramika) { $ready=$true; break }
        if ($process.HasExited) { break }
        Start-Sleep -Milliseconds 200
    }
    if (-not $ready) { throw "Ceramika could not start on port $Port. Check if the port is in use." }
}

$desktopShell = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
foreach ($workspace in @('tech','lab')) {
    if ($Target -in @('all','desktop',$workspace)) {
        Start-Process -FilePath $desktopShell -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-Sta','-WindowStyle','Hidden','-File','desktop.ps1',
            '-Module',$workspace,'-Port',$Port) -WorkingDirectory $root -WindowStyle Hidden
    }
}
if ($Target -in @('all','web')) { Start-Process "$base/" }

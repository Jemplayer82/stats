[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$dotnetExe = Join-Path $env:ProgramFiles 'dotnet\dotnet.exe'

if (-not (Test-Path -LiteralPath $dotnetExe)) {
    throw '.NET 10 SDK is required. Install it with: winget install Microsoft.DotNet.SDK.10'
}

$solution = Join-Path $projectRoot 'StatsUsageWidget.sln'
$packagingProject = Join-Path $projectRoot 'src\StatsUsageWidget.WinUI\StatsUsageWidget.WinUI.csproj'

& $dotnetExe restore $solution
if ($LASTEXITCODE -ne 0) { throw 'NuGet restore failed.' }

& $dotnetExe build $solution -c Release '-p:Platform=x64' --no-restore
if ($LASTEXITCODE -ne 0) { throw 'Widget build failed.' }

& $dotnetExe build $packagingProject -t:Rebuild -c Release '-p:Platform=x64' `
    '-p:GenerateAppxPackageOnBuild=true' '-p:AppxBundle=Never' `
    '-p:AppxPackageSigningEnabled=false' --no-restore
if ($LASTEXITCODE -ne 0) { throw 'MSIX packaging failed.' }

$packageRoot = Join-Path $projectRoot 'src\StatsUsageWidget.WinUI\bin\x64\Release\net10.0-windows10.0.19041\AppPackages'
$msix = Get-ChildItem $packageRoot -Recurse -Filter '*.msix' |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1 -ExpandProperty FullName
if (-not $msix) { throw 'The MSIX package was not created.' }

$certificate = Get-ChildItem Cert:\CurrentUser\My |
    Where-Object { $_.Subject -eq 'CN=StatsUsageWidget' -and $_.NotAfter -gt (Get-Date).AddDays(30) } |
    Sort-Object NotAfter -Descending |
    Select-Object -First 1

if (-not $certificate) {
    $certificate = New-SelfSignedCertificate `
        -Type Custom `
        -Subject 'CN=StatsUsageWidget' `
        -FriendlyName 'Stats Usage Widget local certificate' `
        -CertStoreLocation 'Cert:\CurrentUser\My' `
        -KeySpec Signature `
        -KeyExportPolicy Exportable `
        -HashAlgorithm SHA256 `
        -KeyLength 2048 `
        -KeyUsage DigitalSignature `
        -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3')
}

$artifactDirectory = Join-Path $projectRoot 'artifacts'
New-Item -ItemType Directory -Force -Path $artifactDirectory | Out-Null
$certificateFile = Join-Path $artifactDirectory 'StatsUsageWidget.cer'
$installerFile = Join-Path $artifactDirectory 'StatsUsageWidget.msix'
Export-Certificate -Cert $certificate -FilePath $certificateFile -Force | Out-Null
Copy-Item -LiteralPath $msix -Destination $installerFile -Force

$signTool = Get-ChildItem (Join-Path $env:USERPROFILE '.nuget\packages\microsoft.windows.sdk.buildtools') `
    -Recurse -Filter signtool.exe |
    Where-Object { $_.FullName -match '\\x64\\signtool\.exe$' } |
    Sort-Object FullName -Descending |
    Select-Object -First 1
if (-not $signTool) { throw 'SignTool was not found after restoring the project.' }

& $signTool.FullName sign /sha1 $certificate.Thumbprint /fd SHA256 $installerFile
if ($LASTEXITCODE -ne 0) { throw 'MSIX signing failed.' }

$certificateLiteral = $certificateFile.Replace("'", "''")
$installerLiteral = $installerFile.Replace("'", "''")
$trustedCertificate = Get-ChildItem Cert:\LocalMachine\Root |
    Where-Object { $_.Thumbprint -eq $certificate.Thumbprint } |
    Select-Object -First 1

if ($trustedCertificate) {
    Add-AppxPackage -Path $installerFile -ForceApplicationShutdown -ForceUpdateFromAnyVersion
} else {
    $elevatedCommand = @"
`$ErrorActionPreference = 'Stop'
Import-Certificate -FilePath '$certificateLiteral' -CertStoreLocation 'Cert:\LocalMachine\Root' | Out-Null
Add-AppxPackage -Path '$installerLiteral' -ForceApplicationShutdown -ForceUpdateFromAnyVersion
"@
    $encodedCommand = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($elevatedCommand))
    $process = Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -Wait -PassThru `
        -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $encodedCommand

    if ($process.ExitCode -ne 0) {
        throw "Installation did not finish successfully (exit code $($process.ExitCode))."
    }
}

Write-Host ''
Write-Host 'Stats, Apple Music, and System Monitor widgets installed.' -ForegroundColor Green
Write-Host 'Open Widget Launcher, refresh extensions, then add the widget you want to use.'

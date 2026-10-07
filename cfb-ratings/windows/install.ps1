# One-time setup on Windows: puts the FBS Efficiency Ratings in a folder of your choice, with
# double-click launchers at the top of it, then opens the site. Run it again any time to pull the
# latest version. From any copy of the repository:
#
#   powershell -ExecutionPolicy Bypass -File .\cfb-ratings\windows\install.ps1
#   powershell -ExecutionPolicy Bypass -File .\cfb-ratings\windows\install.ps1 -Dest "D:\Somewhere else"
#
# Needs git and Python 3.10+. Only the cfb-ratings folder of the repository is checked out.
param(
    [string]$Dest = (Join-Path $env:USERPROFILE "Documents\Github - Personal Projects\CFB Rankings"),
    [string]$Repo = "https://github.com/acbennett89/catchall.git",
    [string]$Branch = "claude/cfb-kenpom-ratings"
)
$ErrorActionPreference = "Stop"

# (Not named "Git": PowerShell names ignore case, so it would call itself.)
function Invoke-Git { & git.exe @args; if ($LASTEXITCODE) { throw "git $args failed" } }

if (Test-Path (Join-Path $Dest ".git")) {
    Write-Host "Updating the copy in $Dest"
    Invoke-Git -C $Dest pull --ff-only
} else {
    if ((Test-Path $Dest) -and (Get-ChildItem -Force $Dest | Select-Object -First 1)) {
        throw "$Dest already exists and is not empty. Empty it, or pass -Dest with another folder."
    }
    New-Item -ItemType Directory -Force -Path $Dest | Out-Null
    Write-Host "Downloading into $Dest (only the cfb-ratings folder)"
    Invoke-Git clone --branch $Branch --filter=blob:none --sparse $Repo $Dest
    Invoke-Git -C $Dest sparse-checkout set cfb-ratings
}

# Launchers at the top of the folder; they call the ones inside cfb-ratings.
foreach ($name in "Launch CFB Rankings.bat", "Update CFB Rankings.bat") {
    $body = "@echo off`r`ncall `"%~dp0cfb-ratings\$name`" %*`r`n"
    [IO.File]::WriteAllText((Join-Path $Dest $name), $body, [Text.Encoding]::ASCII)
}
$exclude = Join-Path $Dest ".git\info\exclude"
$have = if (Test-Path $exclude) { Get-Content $exclude } else { @() }
foreach ($name in "/Launch CFB Rankings.bat", "/Update CFB Rankings.bat") {
    if ($have -notcontains $name) { Add-Content -Path $exclude -Value $name }
}

Write-Host "`nDone. In $Dest double-click:"
Write-Host "  Launch CFB Rankings.bat   open the ratings"
Write-Host "  Update CFB Rankings.bat   fetch new games and polls first, then open them"
Start-Process -FilePath (Join-Path $Dest "Launch CFB Rankings.bat") -WorkingDirectory $Dest

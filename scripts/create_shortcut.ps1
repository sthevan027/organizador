<#
.SYNOPSIS
    Cria um atalho "Organizador de Arquivos.lnk" na Área de Trabalho do usuário
    com ícone customizado e apontando para o `run.py` via pythonw (sem console).

.NOTES
    Executado a partir de scripts/criar_atalho.bat.
#>

$ErrorActionPreference = "Stop"

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$RunPy       = Join-Path $ProjectRoot "run.py"
$IconPath    = Join-Path $ProjectRoot "assets\organizer.ico"

if (-not (Test-Path $RunPy)) {
    Write-Host "Arquivo run.py nao encontrado em $RunPy" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $IconPath)) {
    Write-Host "Icone nao encontrado. Gerando com scripts\gen_icon.py..." -ForegroundColor Yellow
    & python (Join-Path $ScriptDir "gen_icon.py") | Out-Null
}

# Localiza pythonw.exe (preferido para GUI sem console)
$PythonW = $null
try {
    $cmd = Get-Command pythonw.exe -ErrorAction Stop
    $PythonW = $cmd.Source
} catch {
    try {
        $cmd = Get-Command python.exe -ErrorAction Stop
        $candidate = Join-Path (Split-Path $cmd.Source -Parent) "pythonw.exe"
        if (Test-Path $candidate) {
            $PythonW = $candidate
        } else {
            $PythonW = $cmd.Source
            Write-Host "Aviso: pythonw.exe nao encontrado, usando python.exe (abre console junto)." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "Python nao encontrado no PATH. Instale em https://python.org" -ForegroundColor Red
        exit 2
    }
}

$DesktopPath  = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopPath "Organizador de Arquivos.lnk"

$WScript = New-Object -ComObject WScript.Shell
$Shortcut = $WScript.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath       = $PythonW
$Shortcut.Arguments        = '"{0}"' -f $RunPy
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.IconLocation     = "$IconPath,0"
$Shortcut.Description      = "Organizador de Arquivos - ordene sua pasta em segundos"
$Shortcut.WindowStyle      = 1
$Shortcut.Save()

Write-Host ""
Write-Host "Atalho criado com sucesso!" -ForegroundColor Green
Write-Host "  Local:   $ShortcutPath"
Write-Host "  Destino: $PythonW $RunPy"
Write-Host "  Icone:   $IconPath"
Write-Host ""
Write-Host "Agora e so dar duplo clique no icone da Area de Trabalho." -ForegroundColor Cyan

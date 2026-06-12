<#
.SYNOPSIS
    Build Cove Narrator into a Windows Setup installer and portable exe.

.EXAMPLE
    .\build.ps1
    .\build.ps1 -Version 2.2.0
#>

[CmdletBinding()]
param(
    [string]$Version = "2.2.0"
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$App          = "cove-narrator"
$ReleaseDir   = "release"

function Step([string]$msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

function Download-File([string]$url, [string]$dest) {
    & curl.exe --silent --show-error --fail --location --output $dest $url
    if ($LASTEXITCODE -ne 0) { throw "Download failed: $url" }
}

Step "Building $App v$Version"

# --- 1. Build environment ---
Step "[1/6] Creating build venv"
if (Test-Path .buildenv) { Remove-Item -Recurse -Force .buildenv }
python -m venv .buildenv
& .\.buildenv\Scripts\python.exe -m pip install --quiet --upgrade pip
& .\.buildenv\Scripts\python.exe -m pip install --quiet `
    -r requirements.txt pyinstaller Pillow

# --- 1b. Bundle the full standard library as hidden imports ---
# torch/transformers/huggingface_hub are installed at RUNTIME, so PyInstaller
# cannot see which stdlib modules they import lazily (e.g. pickletools). Add
# every stdlib module as a hidden import so those runtime deps resolve in the
# frozen app. Skip the tkinter family (also excluded below) and dev/test modules.
Step "Collecting stdlib modules for hidden imports"
$stdlibDeny = @('tkinter','turtle','turtledemo','idlelib','test','lib2to3',
                'antigravity','this','_tkinter','pydoc_data','__hello__','__phello__')
$stdlibList = & .\.buildenv\Scripts\python.exe -c "import sys; print('\n'.join(sorted(sys.stdlib_module_names)))"
$stdlibHidden = @()
foreach ($m in ($stdlibList -split "`r?`n")) {
    $m = $m.Trim()
    if ($m -and ($stdlibDeny -notcontains $m)) {
        $stdlibHidden += '--hidden-import'
        $stdlibHidden += $m
    }
}
Write-Host ("  -> {0} stdlib modules" -f ($stdlibHidden.Count / 2))

# --- 2. Download model files if missing ---
Step "[2/8] Downloading model files"
$modelsDir = "data\models"
if (-not (Test-Path $modelsDir)) { New-Item -ItemType Directory -Path $modelsDir -Force | Out-Null }
if (-not (Test-Path "$modelsDir\kokoro-v1.0.onnx")) {
    Download-File "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx" "$modelsDir\kokoro-v1.0.onnx"
}
if (-not (Test-Path "$modelsDir\voices-v1.0.bin")) {
    Download-File "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin" "$modelsDir\voices-v1.0.bin"
}

# --- 3. Generate .ico ---
Step "[3/8] Generating icon"
& .\.buildenv\Scripts\python.exe -c @"
from PIL import Image
Image.open('build/icon.png').save(
    'build/icon.ico',
    sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)],
)
"@

# --- 3. PyInstaller one-dir (installer input) ---
Step "[4/8] PyInstaller (one-dir for installer)"
if (Test-Path build\tmp) { Remove-Item -Recurse -Force build\tmp }
if (Test-Path dist)      { Remove-Item -Recurse -Force dist }

$commonArgs = @(
    '--noconfirm', '--clean', '--log-level', 'WARN',
    '--windowed',
    '--name', $App,
    '--icon', 'build\icon.ico',
    '--paths', '.',
    '--collect-submodules', 'src',
    '--add-data', ("src\vendor\qwen_tts\core\tokenizer_25hz\vq\assets" + [IO.Path]::PathSeparator + "src\vendor\qwen_tts\core\tokenizer_25hz\vq\assets"),
    '--add-data', ("src\vendor\qwen_tts" + [IO.Path]::PathSeparator + "src\vendor\qwen_tts"),
    '--collect-data', 'kokoro_onnx',
    '--collect-data', 'phonemizer',
    '--collect-data', 'language_tags',
    '--collect-data', 'espeakng_loader',
    '--add-data', ("data\models\kokoro-v1.0.onnx" + [IO.Path]::PathSeparator + "data\models"),
    '--add-data', ("data\models\voices-v1.0.bin" + [IO.Path]::PathSeparator + "data\models"),
    '--add-data', ("data\cmudict.txt" + [IO.Path]::PathSeparator + "data"),
    '--add-data', ("build\icon.png" + [IO.Path]::PathSeparator + "build"),
    '--hidden-import', 'kokoro_onnx',
    '--hidden-import', 'onnxruntime',
    '--hidden-import', 'sounddevice',
    '--hidden-import', 'soundfile',
    '--hidden-import', 'numpy',
    '--hidden-import', 'PySide6',
    '--hidden-import', 'pymupdf',
    '--exclude-module', 'PySide6.QtWebEngineCore',
    '--exclude-module', 'PySide6.QtWebEngineWidgets',
    '--exclude-module', 'PySide6.QtQml',
    '--exclude-module', 'PySide6.QtQuick',
    '--exclude-module', 'PySide6.Qt3DCore',
    '--exclude-module', 'PySide6.QtCharts',
    '--exclude-module', 'PySide6.QtDataVisualization',
    '--exclude-module', 'tkinter',
    'src\main.py'
)

& .\.buildenv\Scripts\pyinstaller.exe @stdlibHidden @commonArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller (onedir) failed" }

$dirAppDir = Join-Path 'dist' $App
Copy-Item build\icon.png $dirAppDir -Force
if (Test-Path README.md) { Copy-Item README.md $dirAppDir -Force }
if (Test-Path LICENSE)   { Copy-Item LICENSE   $dirAppDir -Force }

# --- 4. PyInstaller one-file (portable) ---
Step "[5/8] PyInstaller (one-file portable)"
$portableName = "$App-portable"
& .\.buildenv\Scripts\pyinstaller.exe @stdlibHidden `
    --noconfirm --clean --log-level WARN `
    --onefile --windowed `
    --name $portableName `
    --icon build\icon.ico `
    --paths . `
    --collect-submodules src `
    --add-data ("src\vendor\qwen_tts\core\tokenizer_25hz\vq\assets" + [IO.Path]::PathSeparator + "src\vendor\qwen_tts\core\tokenizer_25hz\vq\assets") `
    --add-data ("src\vendor\qwen_tts" + [IO.Path]::PathSeparator + "src\vendor\qwen_tts") `
    --collect-data kokoro_onnx `
    --collect-data phonemizer `
    --collect-data language_tags `
    --collect-data espeakng_loader `
    --add-data ("data\models\kokoro-v1.0.onnx" + [IO.Path]::PathSeparator + "data\models") `
    --add-data ("data\models\voices-v1.0.bin" + [IO.Path]::PathSeparator + "data\models") `
    --add-data ("data\cmudict.txt" + [IO.Path]::PathSeparator + "data") `
    --add-data ("build\icon.png" + [IO.Path]::PathSeparator + "build") `
    --hidden-import kokoro_onnx `
    --hidden-import onnxruntime `
    --hidden-import sounddevice `
    --hidden-import soundfile `
    --hidden-import numpy `
    --hidden-import PySide6 `
    --hidden-import pymupdf `
    --exclude-module PySide6.QtWebEngineCore `
    --exclude-module PySide6.QtWebEngineWidgets `
    --exclude-module PySide6.QtQml `
    --exclude-module PySide6.QtQuick `
    --exclude-module PySide6.Qt3DCore `
    --exclude-module PySide6.QtCharts `
    --exclude-module PySide6.QtDataVisualization `
    --exclude-module tkinter `
    src\main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller (onefile) failed" }

# --- 5. Build installer + stage portable ---
Step "[6/8] Building Setup installer with Inno Setup"
New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null

$iscc = $null
foreach ($candidate in @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)) {
    if ($candidate -and (Test-Path $candidate)) { $iscc = $candidate; break }
}
if (-not $iscc) {
    $inPath = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($inPath) { $iscc = $inPath.Source }
}
if (-not $iscc) { throw "Inno Setup (iscc.exe) not found. Install Inno Setup 6." }

$absSource  = (Resolve-Path $dirAppDir).Path
$absRelease = (Resolve-Path $ReleaseDir).Path
$absIcon    = (Resolve-Path build\icon.ico).Path

& $iscc `
    "/DAppVersion=$Version" `
    "/DSourceDir=$absSource" `
    "/DOutputDir=$absRelease" `
    "/DIconFile=$absIcon" `
    packaging\installer.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup build failed" }

Step "Staging portable exe"
$portableSrc  = Join-Path 'dist' "$portableName.exe"
$portableDest = Join-Path $ReleaseDir ("{0}-{1}-Portable.exe" -f $App, $Version)
if (Test-Path $portableDest) { Remove-Item -Force $portableDest }
Copy-Item $portableSrc $portableDest -Force

function Write-Sha256Sidecar([string]$file) {
    $hash = (Get-FileHash -Algorithm SHA256 -Path $file).Hash.ToLower()
    $name = [IO.Path]::GetFileName($file)
    "$hash  $name" | Set-Content -Path "$file.sha256" -NoNewline -Encoding ascii
}

Step "[7/8] Writing sha256 sidecars"
Get-ChildItem -Path $ReleaseDir -Filter "*$Version*.exe" | ForEach-Object {
    Write-Sha256Sidecar $_.FullName
    Write-Host ("  -> {0}.sha256" -f $_.Name)
}

# --- 6. Cleanup ---
Step "[8/8] Cleaning up"
Remove-Item -Recurse -Force .buildenv, build\tmp, dist, build\icon.ico -ErrorAction SilentlyContinue
Get-ChildItem -Filter *.spec | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Done:" -ForegroundColor Green
Get-ChildItem $ReleaseDir -Filter "*$Version*" | ForEach-Object {
    Write-Host ("  {0}" -f $_.FullName)
}

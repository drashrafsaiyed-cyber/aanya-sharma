@echo off
echo ============================================
echo  Installing ComfyUI for Aanya Sharma HD Images
echo ============================================

cd /d "C:\Users\admin"

echo [1/4] Checking Git...
git --version >nul 2>&1
if errorlevel 1 (
    echo Git not found. Downloading...
    curl -L -o git_installer.exe https://github.com/git-for-windows/git/releases/download/v2.45.2.windows.1/Git-2.45.2-64-bit.exe
    git_installer.exe /SILENT /COMPONENTS="icons,ext\reg\shellhere,assoc,assoc_sh"
)

echo [2/4] Cloning ComfyUI...
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI

echo [3/4] Installing ComfyUI dependencies...
"C:\Users\admin\Python311\python.exe" -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 -q
"C:\Users\admin\Python311\python.exe" -m pip install -r requirements.txt -q

echo [4/4] Done!
echo.
echo TO START COMFYUI:
echo   cd C:\Users\admin\ComfyUI
echo   C:\Users\admin\Python311\python.exe main.py
echo.
echo Then open: http://127.0.0.1:8188
pause

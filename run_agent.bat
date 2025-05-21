@echo off
setlocal

:: ----- Kiểm tra Python -----
where python >nul 2>nul
if errorlevel 1 (
    echo Python chưa được cài. Đang tải và cài đặt...
    powershell -Command "Start-Process 'https://www.python.org/ftp/python/3.11.2/python-3.11.2-amd64.exe' -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1' -Wait"
    if errorlevel 1 (
        echo ❌ Không thể cài Python. Thoát...
        pause
        exit /b
    )
) else (
    echo ✅ Python đã được cài.
)

:: ----- Đảm bảo pip được cài -----
echo 🔧 Đảm bảo pip có sẵn...
python -m ensurepip --default-pip
python -m pip install --upgrade pip

:: ----- Danh sách thư viện cần -----
set LIBS=pyautogui psutil pygetwindow google-generativeai tkinterdnd2 Pillow pytesseract python-docx PyMuPDF pandas pyperclip tkhtmlview requests selenium

:: ----- Cài từng thư viện nếu chưa có -----
for %%L in (%LIBS%) do (
    python -c "import %%L" 2>nul
    if errorlevel 1 (
        echo 📦 Đang cài đặt %%L ...
        python -m pip install %%L
    ) else (
        echo ✅ %%L đã được cài.
    )
)

:: ----- Chạy chương trình chính -----
echo ▶️ Đang chạy ứng dụng...
python main_gui.py

endlocal
pause

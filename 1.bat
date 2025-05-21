@echo off
setlocal

:: Đường dẫn thư mục dự án
set "PROJECT_DIR=D:\Agent AI\Test"

:: URL repository GitHub của bạn
set "REPO_URL=https://github.com/your-username/your-repo-name.git"

echo === Đang chuyển đến thư mục dự án ===
cd /d "%PROJECT_DIR%"
if errorlevel 1 (
    echo ❌ Không thể chuyển đến thư mục %PROJECT_DIR%
    pause
    exit /b
)

echo === Khởi tạo Git repository ===
git init

echo === Thêm remote nếu chưa có ===
git remote remove origin >nul 2>&1
git remote add origin %REPO_URL%

echo === Đang thêm và commit toàn bộ file ===
git add .
git commit -m "Đẩy nội dung website lên GitHub"

echo === Đẩy lên GitHub ===
git push -u origin master

echo ✅ Hoàn tất!
pause

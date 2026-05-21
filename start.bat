@echo off
chcp 65001 >nul
echo ========================================
echo   视频水印去除工具 - 启动脚本
echo ========================================

:: 切换到项目根目录
cd /d "%~dp0"

:: 启动后端
echo [1/2] 启动后端服务 (http://localhost:8000)...
start "后端服务" cmd /k "cd /d %~dp0 && uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000"

:: 等待后端启动
timeout /t 2 /nobreak >nul

:: 启动前端
echo [2/2] 启动前端服务 (http://localhost:5173)...
start "前端服务" cmd /k "cd /d %~dp0\frontend && npm run dev"

echo.
echo 启动完成！
echo   后端: http://localhost:8000
echo   前端: http://localhost:5173
echo.
echo 请在浏览器打开 http://localhost:5173
pause

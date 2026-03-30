@echo off
setlocal

cd /d "%~dp0\.."

where python >nul 2>nul
if errorlevel 1 (
  echo 未找到 python，请先激活项目环境（推荐 conda activate veto311）。
  exit /b 1
)

python -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] < (3, 13) else 1)"
if errorlevel 1 (
  echo 当前 python 版本不兼容，请先切到 Python 3.10-3.12（推荐 conda activate veto311）。
  python -V
  exit /b 1
)

if "%PORT%"=="" set PORT=8000

echo VETO web 正在启动...
echo 启动后打开: http://127.0.0.1:%PORT%/veto

if "%VETO_RELOAD%"=="1" (
  python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port %PORT%
) else (
  python -m uvicorn backend.main:app --host 0.0.0.0 --port %PORT%
)

endlocal

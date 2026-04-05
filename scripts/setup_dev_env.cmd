@echo off
setlocal

cd /d "%~dp0\.."

set "PYTHON_CMD=python"
%PYTHON_CMD% --version >nul 2>nul
if errorlevel 1 (
  if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
    set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python311\python.exe"
  ) else (
    echo [ERROR] Python was not found in PATH or default install location.
    echo Install Python 3.11+ first.
    exit /b 1
  )
)

if not exist ".venv\Scripts\python.exe" (
  echo [INFO] Creating virtual environment...
  "%PYTHON_CMD%" -m venv .venv
  if errorlevel 1 exit /b 1
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 exit /b 1

python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

pip install -r requirements.txt
if errorlevel 1 exit /b 1

if not exist ".env" (
  copy /Y ".env.example" ".env" >nul
  echo [INFO] Created .env from .env.example
) else (
  echo [INFO] .env already exists, left unchanged.
)

echo [INFO] Starting MySQL user process...
"%PYTHON_CMD%" "scripts\start_mysql_user.py" >nul 2>nul

echo.
echo [DONE] Dev environment is ready.
echo Next steps:
echo 1^) Update .env values ^(openai_api_key/openai_auth_mode etc.^)
echo 2^) Seed data: .venv\Scripts\python -m app.seed.seed_data
echo 3^) Run API: .venv\Scripts\uvicorn app.main:app --reload --port 8000

endlocal

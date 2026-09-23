@echo off
setlocal
cd /d "%~dp0services\api-gateway"

set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY if exist "..\api-gateway.venv\Scripts\python.exe" set "PY=..\api-gateway.venv\Scripts\python.exe"
if not defined PY if exist "..\.venv\Scripts\python.exe" set "PY=..\.venv\Scripts\python.exe"

if not defined PY (
  echo Could not find the python.exe inside a virtualenv.
  echo Looked in: services\api-gateway\.venv and sibling .venv folders.
  pause
  exit /b 1
)

echo Using python: %PY%
echo.
echo Step 1/2 - Running database migrations (best effort)...
"%PY%" -m alembic upgrade head

echo.
echo Step 2/2 - Widening encrypted columns to VARCHAR(255)...
"%PY%" -m scripts.fix_employee_column_widths

echo.
echo Done. Now restart uvicorn and try Add Employee again.
pause

@echo off
cd /d "%~dp0"
set "DATABASE_URL=postgresql+asyncpg://aifya_user:aifya_dev_password@localhost:5432/AIFYA-MAIN"
echo.
echo ============================================================
echo  Aifya - create real schema in database: AIFYA-MAIN
echo  (existing legacy_* tables are left untouched)
echo ============================================================
echo.
".venv\Scripts\python.exe" -m alembic upgrade head
if errorlevel 1 (
  echo.
  echo MIGRATION FAILED - see the error above.
) else (
  echo.
  echo MIGRATION OK - AIFYA-MAIN schema created. No demo data added.
)
echo.
pause
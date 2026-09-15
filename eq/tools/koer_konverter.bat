@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ============================================
echo   Databento  -^>  15s parquet
echo ============================================
echo Mappe: %CD%
echo.

rem --- 1. er Python installeret?
python --version >nul 2>&1
if errorlevel 1 goto ingenpython

rem --- 2. ligger scriptet her?
if not exist "databento_konverter3.py" goto ingenscript

rem --- 3. find zip ELLER udpakket mappe
set "MAAL="
for %%F in ("GLBX-*.zip") do set "MAAL=%%F"
if not defined MAAL for /d %%D in ("GLBX-*") do set "MAAL=%%D"
if not defined MAAL goto ingendata

echo Fandt data: !MAAL!
echo.
echo Det her tager 5-15 minutter. Luk ikke vinduet.
echo.
python "databento_konverter3.py" "!MAAL!"
if errorlevel 1 goto fejl

echo.
echo ============================================
echo   FAERDIG
echo ============================================
echo De .parquet-filer der ligger i denne mappe
echo skal uploades. Her er de:
echo.
dir /b *.parquet 2>nul
goto slut

:ingenpython
echo FEJL: Python blev ikke fundet.
echo Hent det paa python.org og saet flueben i
echo "Add Python to PATH" under installationen.
goto slut

:ingenscript
echo FEJL: databento_konverter3.py ligger ikke i
echo %CD%
echo.
echo Laeg denne .bat samme sted som scriptet.
goto slut

:ingendata
echo FEJL: fandt hverken en GLBX-zip eller en
echo udpakket GLBX-mappe i %CD%
echo.
echo Laeg din Databento-download her.
goto slut

:fejl
echo.
echo Konverteringen fejlede. Mangler du pakker, koer:
echo   pip install databento pandas pyarrow zstandard
goto slut

:slut
echo.
pause

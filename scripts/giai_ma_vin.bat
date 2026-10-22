@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=%USERPROFILE%\anaconda3\python.exe"
echo === AutoWise AI - giai ma VIN qua NHTSA (dong cua so roi chay lai se lam tiep) ===
echo Dung Python: %PY%
"%PY%" 07_vin_decode.py
echo.
echo Xong. Nhan phim bat ky de dong cua so.
pause >nul

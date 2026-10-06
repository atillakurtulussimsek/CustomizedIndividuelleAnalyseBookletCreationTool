@echo off
REM ============================================================
REM  Booklet Engine - Tek tikla calistirma scripti (Windows)
REM  Sistem Python'unu kullanir; eksik bagimliliklari otomatik kurar.
REM ============================================================
setlocal

REM Scriptin bulundugu dizine gec (her yerden calisabilsin)
cd /d "%~dp0"

echo ========================================
echo   Analyse Booklet Engine v1.0.0
echo   %DATE% %TIME%
echo ========================================
echo.

REM --- Python 3.10+ yorumlayicisi bul -------------------------
call :find_python
if not defined PY (
    echo [HATA] Python 3.10 veya ustu bulunamadi.
    echo        Kurulum: https://www.python.org/downloads/
    echo        Kurarken "Add python.exe to PATH" secenegini isaretleyin.
    pause
    exit /b 1
)

for /f "delims=" %%v in ('%PY% --version 2^>^&1') do echo Python: %%v

REM --- Bagimliliklar eksikse kur ------------------------------
%PY% -c "import click, pymupdf, pikepdf, reportlab, pydantic, rich" >nul 2>&1
if errorlevel 1 (
    echo.
    echo Bagimliliklar eksik, kuruluyor ^(ilk calistirmada birkac dakika surebilir^)...
    %PY% -m pip install --user -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [HATA] Bagimliliklar kurulamadi. Internet baglantinizi kontrol edin.
        pause
        exit /b 1
    )
    echo [OK] Bagimliliklar kuruldu.
)

echo.

REM --- Calistir -----------------------------------------------
%PY% -m src.cli run --config config.json
set EXIT_CODE=%ERRORLEVEL%

echo.
if %EXIT_CODE% EQU 0 (
    echo [OK] Islem basariyla tamamlandi.
) else if %EXIT_CODE% EQU 2 (
    echo [UYARI] Islem tamamlandi fakat bazi hatalar olustu. Loglara bakin.
) else (
    echo [HATA] Islem basarisiz oldu ^(cikis kodu: %EXIT_CODE%^).
)

echo.
pause
exit /b %EXIT_CODE%

REM ============================================================
REM  Yardimci altyordamlar
REM ============================================================
:find_python
set "PY="
call :try_python "py -3.13"
call :try_python "py -3.12"
call :try_python "py -3.11"
call :try_python "py -3.10"
call :try_python "py -3"
call :try_python "python"
call :try_python "python3"
exit /b

:try_python
if defined PY exit /b
%~1 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=%~1"
exit /b

@echo off
title AgroIA Peru V6 - Iniciar
cd /d "%~dp0"
echo ============================================
echo      INICIANDO AGROIA PERU V6
echo ============================================
echo.
echo Si es la primera vez, Docker puede tardar porque descargara dependencias.
echo.
echo Cerrando posibles contenedores antiguos...
docker rm -f agroia_peru >nul 2>nul
docker rm -f agroia_peru_v2 >nul 2>nul
docker rm -f agroia_peru_v3 >nul 2>nul
docker rm -f agroia_peru_v5 >nul 2>nul
docker rm -f agroia_peru_v6 >nul 2>nul

echo Levantando AgroIA Peru V6...
docker compose up --build -d
if errorlevel 1 (
    echo.
    echo No se pudo iniciar. Verifica que Docker Desktop este instalado y abierto.
    pause
    exit /b 1
)
echo.
echo AgroIA Peru V6 se esta abriendo en el navegador...
timeout /t 4 >nul
start http://localhost:8000
echo.
echo Listo. Para detener el sistema usa DETENER_AGROIA.bat
echo.
pause
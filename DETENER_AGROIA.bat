@echo off
title AgroIA Peru V6 - Detener
cd /d "%~dp0"
echo ============================================
echo      DETENIENDO AGROIA PERU V6
echo ============================================
echo.
docker compose down
docker rm -f agroia_peru >nul 2>nul
docker rm -f agroia_peru_v2 >nul 2>nul
docker rm -f agroia_peru_v3 >nul 2>nul
docker rm -f agroia_peru_v5 >nul 2>nul
docker rm -f agroia_peru_v6 >nul 2>nul
echo.
echo Sistema detenido.
echo.
pause
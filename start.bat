@echo off
title CallScribe
cd /d "%~dp0"

:: Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no esta instalado o no esta en PATH.
    echo Descargalo desde https://python.org
    pause
    exit /b 1
)

:: Verificar ffmpeg
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo ERROR: ffmpeg no esta instalado o no esta en PATH.
    echo Descargalo desde https://ffmpeg.org/download.html
    pause
    exit /b 1
)

:: Crear entorno virtual si no existe
if not exist "venv" (
    echo Creando entorno virtual...
    python -m venv venv
)

:: Activar entorno virtual
call venv\Scripts\activate.bat

:: Instalar dependencias
pip install -r requirements.txt --quiet

:: Cargar variables de entorno si existe .env
if exist ".env" (
    for /f "tokens=*" %%a in (.env) do set %%a
)

:: Iniciar aplicacion
echo Iniciando CallScribe...
python main.py

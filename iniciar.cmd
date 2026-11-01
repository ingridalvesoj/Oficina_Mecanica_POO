@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Ambiente virtual nao encontrado. Siga a instalacao no README.md.
    pause
    exit /b 1
)
echo Acesse http://127.0.0.1:8501 no navegador.
".venv\Scripts\python.exe" -m streamlit run app.py
if errorlevel 1 pause

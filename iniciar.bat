@echo off
cd /d "%~dp0"
title Radar de Precos
echo Radar de Precos rodando. Feche esta janela para parar.
".venv\Scripts\python.exe" run.py
pause

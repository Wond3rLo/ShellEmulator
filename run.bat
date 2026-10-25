@echo off
cd /d "%~dp0"
python src\main.py --config src\config.toml
pause
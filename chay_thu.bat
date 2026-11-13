@echo off
chcp 65001 >nul
py -3 viet_hoa.py
if errorlevel 1 pause

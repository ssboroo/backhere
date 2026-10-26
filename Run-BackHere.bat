@echo off
cd /d "%~dp0"
py -3 desktop\backhere.py
if errorlevel 1 (
 echo Install Python 3.12 or newer from python.org, including Tcl/Tk and the Python launcher.
 pause
)

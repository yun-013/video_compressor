@echo off
rem Launch GUI without console window
where pythonw >nul 2>nul && (start "" pythonw "%~dp0gui.py") || (start "" python "%~dp0gui.py")

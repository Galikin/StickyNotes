@echo off
setlocal enabledelayedexpansion
echo ==================================================
echo  Sticky Notes Application Build Script
echo ==================================================
echo.

echo Checking for dependencies...
for %%p in (pyinstaller pystray Pillow) do (
    pip show %%p > nul 2>&1
    if !errorlevel! neq 0 (
        echo %%p not found. Installing now...
        pip install %%p
        if !errorlevel! neq 0 (
            echo Failed to install %%p. Please install it manually and run this script again.
            pause
            exit /b
        )
    ) else (
        echo %%p is already installed.
    )
)

echo.
echo Building the executable...
pyinstaller --onefile --windowed --name StickyNotes --add-data "icon.png;." --icon="icon.png" --clean pyqt_sticky_notes.py

echo.
if exist "dist\StickyNotes.exe" (
    echo ==================================================
    echo  Build successful!
    echo ==================================================
    echo The executable can be found in the 'dist' folder:
    echo %cd%\dist\StickyNotes.exe
    echo.
) else (
    echo ==================================================
    echo  Build failed.
    echo ==================================================
    echo Please check the output above for errors.
    echo.
)

pause

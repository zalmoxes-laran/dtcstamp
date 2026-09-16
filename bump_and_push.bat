@echo off
setlocal enabledelayedexpansion

:: bump_and_push.bat - Automated version bump and push for dtcstamp
:: Usage: bump_and_push.bat [patch^|minor^|major]
::
:: Same script as s3Dgraphy's, on purpose. For the --tag-only and --set modes
:: (PEP 440 pre-releases) use bump_and_push.sh; on Windows, Git Bash runs it.

if "%1"=="" (
    echo Error: No bump type specified
    goto :show_help
)

set "BUMP_TYPE=%1"

if not "%BUMP_TYPE%"=="patch" if not "%BUMP_TYPE%"=="minor" if not "%BUMP_TYPE%"=="major" (
    echo Error: Invalid bump type '%BUMP_TYPE%'
    goto :show_help
)

git rev-parse --git-dir >nul 2>&1
if errorlevel 1 (
    echo Error: Not in a git repository
    pause
    exit /b 1
)

git diff --quiet >nul 2>&1
if errorlevel 1 (
    echo Warning: Working directory has uncommitted changes
    set /p "continue=Continue anyway? (y/N): "
    if /i not "!continue!"=="y" (
        echo Aborted.
        pause
        exit /b 1
    )
)

bump2version --version >nul 2>&1
if errorlevel 1 (
    echo Error: bump2version not found
    echo Install with: pip install bump2version
    pause
    exit /b 1
)

echo Getting current version...
for /f "tokens=3" %%v in ('findstr "current_version = " .bumpversion.cfg') do set "CURRENT_VERSION=%%v"
echo Current version: %CURRENT_VERSION%

echo Bumping %BUMP_TYPE% version...
bump2version %BUMP_TYPE%
if errorlevel 1 (
    echo Version bump failed
    pause
    exit /b 1
)
echo Version bump successful

for /f "tokens=3" %%v in ('findstr "current_version = " .bumpversion.cfg') do set "NEW_VERSION=%%v"
echo New version: %NEW_VERSION%

echo Pushing to GitHub...
git push
if errorlevel 1 (
    echo Push failed
    pause
    exit /b 1
)

git push --tags
if errorlevel 1 (
    echo Tag push failed
    pause
    exit /b 1
)

echo Push successful

echo.
echo SUCCESS!
echo Version bumped: %CURRENT_VERSION% -^> %NEW_VERSION%
echo Tag created and pushed: v%NEW_VERSION%
echo.
echo Next step:
echo   GitHub -^> Actions -^> "Publish to PyPI" -^> Run workflow
echo   target: testpypi (first), then pypi
echo   version_tag: v%NEW_VERSION%
echo.
pause
goto :end

:show_help
echo Usage: %0 [patch^|minor^|major]
echo.
echo Automated version bump and push for dtcstamp
echo.
echo Commands:
echo   patch    Increment patch version (0.1.0 -^> 0.1.1)
echo   minor    Increment minor version (0.1.1 -^> 0.2.0)
echo   major    Increment major version (0.2.0 -^> 1.0.0)
echo.
echo NOTE: this bumps the PACKAGE version. STAMP_VERSION and HINTS_VERSION
echo       in dtcstamp.py are the ON-DISK FORMAT versions and are not touched.
echo.
echo Examples:
echo   %0 patch
echo   %0 minor
echo.
pause

:end
endlocal

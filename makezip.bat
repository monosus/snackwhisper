@REM CHANGELOG.md と dist\snackwhisper.exe を一つの zip にまとめる
@REM 使い方: dev ディレクトリで実行
@REM    $ makezip.bat
@REM 依存: PowerShell

cd /d "%~dp0"
powershell Compress-Archive -Path CHANGELOG.md,dist\snackwhisper.exe -DestinationPath dist\snackwhisper.zip -Force

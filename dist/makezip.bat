@REM CHANGELOG.md (dev配下) と snackwhisper.exe を一つのアーカイブファイルにまとめる
@REM 使い方: cmd.exeから、
@REM    $ makezip.bat
@REM 依存: PowerShell

powershell Compress-Archive -Path ..\CHANGELOG.md,snackwhisper.exe -DestinationPath snackwhisper.zip -Force

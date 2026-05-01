@REM # CHANGELOG.mdとsnackwhisper.exe を一つのアーカイブファイルにまとめる
@REM # 使い方: cmd.exeから、 
@REM    $ powershell -File makezip.ps1
@REM # 依存: 7zip, PowerShell

powershell Compress-Archive -Path CHANGELOG.md,snackwhisper.exe -DestinationPath snackwhisper.zip

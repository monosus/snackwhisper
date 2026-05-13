"..\venv\Scripts\python.exe" make_buildinfo.py

pyinstaller main.py ^
  --name snackwhisper.exe ^
  --onefile ^
  --noconsole ^
  --icon=icon.ico ^
  --add-data "icon.ico;./" ^
  --collect-data sv_ttk ^
  --collect-all google.genai ^
  --collect-all elevenlabs ^
  --additional-hooks-dir=.

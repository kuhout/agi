rmdir /Q /S dist
python setup.py bdist_esky
cd dist
"c:\Program Files\GnuWin32\bin\unzip.exe" -q agi-0.9.win32.zip
cd ..
cmd /C dist\agility.exe

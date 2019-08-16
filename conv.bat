python .\conv\ncmdump\ncmdump.py
del *.ncm
.\conv\qaac\qaac64.exe -A --copy-artwork *.flac
del *.flac
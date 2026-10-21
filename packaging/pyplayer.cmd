@echo off
rem Commande « pyplayer » du terminal : lance PyPlayer et attend sa fin, pour que la sortie s'affiche dans la console
rem (l'application est une application fenetree : sans « start /wait », l'invite reviendrait avant la fin).
start "" /wait "%~dp0..\PyPlayer.exe" %*
exit /b %ERRORLEVEL%

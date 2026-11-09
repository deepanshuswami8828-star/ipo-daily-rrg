@echo off
rem Starts the IPO RRG app (if needed) and gives a public link anyone can open.
rem The link works only while this window stays open and this PC is on.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\share_link.ps1"

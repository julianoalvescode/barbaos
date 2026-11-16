#!/bin/bash
#
# BarbaDrop - by Barba777
# Launcher for the ArkOS Options/Tools menu
#
APPDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )/BarbaDrop"
LOG="$APPDIR/log.txt"

# sudo (same as PortMaster)
if sudo -n true 2>/dev/null; then ESUDO="sudo -E"; else ESUDO=""; fi

# clear the text console
$ESUDO chmod 666 /dev/tty0 2>/dev/null
printf "\033c" > /dev/tty0 2>/dev/null
echo "Starting BarbaDrop..." > /dev/tty0 2>/dev/null

# R36S button mapping (ships with PortMaster)
for db in /opt/system/Tools/PortMaster/gamecontrollerdb.txt /roms/tools/PortMaster/gamecontrollerdb.txt \
          /roms2/tools/PortMaster/gamecontrollerdb.txt "$APPDIR/../PortMaster/gamecontrollerdb.txt"; do
  if [ -f "$db" ]; then export SDL_GAMECONTROLLERCONFIG_FILE="$db"; break; fi
done
export PYSDL2_DLL_PATH="/usr/lib"
[ -d /roms2/gba ] && grep -q roms2 /etc/fstab 2>/dev/null && export BARBADROP_ROMS="/roms2"

# free the buttons in case a gptokeyb process was left running
$ESUDO pkill -f gptokeyb 2>/dev/null

cd "$APPDIR"
$ESUDO rm -f /tmp/barbadrop_restart_es
$ESUDO python3 "$APPDIR/BarbaDrop.py" > "$LOG" 2>&1

printf "\033c" > /dev/tty0 2>/dev/null

# if games were installed, restart EmulationStation so they show up
if [ -f /tmp/barbadrop_restart_es ]; then
  $ESUDO rm -f /tmp/barbadrop_restart_es
  $ESUDO systemctl restart emulationstation
fi

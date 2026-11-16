#!/bin/bash
#
# BarbaOS Branding - by Barba777
# 1) Sets the network name (hostname) to BarbaOS
# 2) Writes a report of where dArkOS/ArkOS still shows up in the system
# Every changed file is backed up to /roms/backup_barbaos/<date>/
#
if sudo -n true 2>/dev/null; then S="sudo"; else S=""; fi
TTY=/dev/tty1
$S chmod 666 $TTY /dev/tty0 2>/dev/null
printf "\033c" > $TTY
say() { echo "$*" > $TTY; echo "$*" >> "$REL"; }

STAMP=$(date +%Y%m%d_%H%M%S)
ROMS=/roms; [ -d /roms2/tools ] && grep -q roms2 /etc/fstab 2>/dev/null && ROMS=/roms2
BK="$ROMS/backup_barbaos/$STAMP"
REL="$ROMS/tools/BarbaOS_report.txt"
mkdir -p "$BK"
: > "$REL"

backup() { [ -f "$1" ] && mkdir -p "$BK$(dirname "$1")" && $S cp -a "$1" "$BK$1"; }

say "=== BarbaOS Branding ($STAMP) ==="
say ""

# ---- 1) hostname ----
OLD=$(hostname)
if [ "$OLD" != "BarbaOS" ]; then
  backup /etc/hostname; backup /etc/hosts
  echo "BarbaOS" | $S tee /etc/hostname > /dev/null
  if [ -n "$OLD" ] && [ "$OLD" != "localhost" ]; then $S sed -i "s/\b$OLD\b/BarbaOS/g" /etc/hosts; fi
  grep -q "BarbaOS" /etc/hosts || echo "127.0.1.1	BarbaOS" | $S tee -a /etc/hosts > /dev/null
  $S hostname BarbaOS 2>/dev/null
  say "[OK] Network name: $OLD -> BarbaOS (applies after reboot)"
else
  say "[OK] Network name is already BarbaOS"
fi
say ""

# ---- 2) report ----
say "--- Text files mentioning darkos/arkos ---"
for d in /etc /usr/share/plymouth /opt /usr/local/bin /usr/bin/emulationstation /home/ark/.emulationstation /home/ark/.config/retroarch/retroarch.cfg /boot; do
  [ -e "$d" ] || continue
  $S grep -rIil -E "d?arkos" "$d" 2>/dev/null | grep -v -E "^$ROMS/" | while read -r f; do
    echo "## $f" >> "$REL"
    $S grep -n -i -E "d?arkos" "$f" 2>/dev/null | head -8 | cut -c1-200 >> "$REL"
  done
done
say ""
say "--- Files with the name in the file name ---"
$S find / -xdev \( -iname "*darkos*" -o -iname "*arkos*" \) 2>/dev/null | grep -v -E "^$ROMS/|^/proc|^/sys" | head -200 >> "$REL"
say ""
say "--- Plymouth (text boot screen) ---"
cat /usr/share/plymouth/themes/text.plymouth >> "$REL" 2>/dev/null
say ""
say "--- os-release ---"
cat /etc/os-release >> "$REL" 2>/dev/null
say ""
say "--- EmulationStation ---"
ES=$(command -v emulationstation 2>/dev/null; ls /usr/bin/emulationstation/emulationstation 2>/dev/null)
say "binary: $ES"
for b in $ES; do [ -f "$b" ] && strings "$b" 2>/dev/null | grep -i -E "d?arkos" | sort -u | head -30 >> "$REL"; done

$S sync
say ""
say "Report saved to: tools/BarbaOS_report.txt"
say "Backup in: backup_barbaos/$STAMP"
say ""
say "Power off the console and put the SD card"
say "in your PC to read the report."
sleep 8
printf "\033c" > $TTY

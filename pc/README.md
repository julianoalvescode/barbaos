# PC tools

## BarbaDrop server

Shares a folder of your games over Wi-Fi so **BarbaDrop** on the console can download them.

1. Install [Python 3](https://www.python.org) (tick *Add python.exe to PATH*).
2. Create a `games` folder next to `barbadrop_server.py`, with one subfolder per system,
   named like the folders on the EASYROMS partition:

   ```
   games/
     gba/    My Game (USA).gba
     snes/   Other Game (USA).zip
   ```

3. Windows: double-click `start_barbadrop_server.bat`.
   macOS/Linux: `python3 barbadrop_server.py`.
   Another folder or port: `python barbadrop_server.py D:\MyGames 8080`.
4. Allow access when the firewall asks. The server prints the address to type in BarbaDrop.

## Boxart scripts

Download boxart and screenshots from [libretro-thumbnails](https://github.com/libretro-thumbnails) for the games
**you already have** on the SD card and write the EmulationStation `gamelist.xml`.

1. Save the thumbnail listings to a work folder as `box.html` and `snap.html`:
   - `https://thumbnails.libretro.com/Nintendo%20-%20Game%20Boy%20Advance/Named_Boxarts/`
   - `https://thumbnails.libretro.com/Nintendo%20-%20Game%20Boy%20Advance/Named_Snaps/`
2. Match ROM names to boxart: `python boxart_match.py <work_folder> E:/gba`
3. Download the images to `E:/gba/images`: `python boxart_download.py <work_folder> E:/gba`

`boxart_match.py` has an alias list (`ALIAS`) for names that don't follow the No-Intro naming.
The scripts are set up for GBA; for another system, change the system name in the URLs.

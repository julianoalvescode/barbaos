# Credits and third-party licenses

## SD card image

The `BarbaOS-1.0-R36S.img.xz` image is derived, with no changes to the Linux system, from
**dArkOS4Clone 20261008** (<https://github.com/lcdyk0517/arkos4clone/releases/tag/20261008>).
BarbaOS only adds files to the BOOT (logo) and EASYROMS (loading screen, apps and theme) partitions.

Source code for the GPL components (kernel, system, EmulationStation, emulators):

- dArkOS: <https://github.com/christianhaitian/dArkOS>
- ArkOS4Clone (kernel, DTBs and scripts for clones): <https://github.com/lcdyk0517/arkos4clone>
- ArkOS: <https://github.com/christianhaitian/arkos>

## Components

| Component | Where | License |
|---|---|---|
| ArkOS | base system | GPL — <https://github.com/christianhaitian/arkos> |
| dArkOS / ArkOS4Clone | base system, boot scripts, DTB profiles | see the original projects |
| PortMaster | used at runtime (not included in this repo) | MIT — <https://github.com/PortsMaster/PortMaster-GUI> |
| PySDL2 | `easyroms/tools/BarbaDrop/lib/sdl2/` | Public domain / zlib — <https://github.com/py-sdl/py-sdl2> |
| DejaVu Sans | `easyroms/tools/BarbaDrop/lib/DejaVuSans.ttf` | Bitstream Vera / DejaVu (free redistribution) — <https://dejavu-fonts.github.io/License.html> |
| es-theme-EpicAeolus | included in the image, downloaded by the installer | see <https://github.com/AeolusUX/es-theme-EpicAeolus> |
| EpicNoir | base of EpicAeolus | Chicuelo and Nick L (c64-dev) |
| libretro-thumbnails | boxart downloaded at runtime (not included) | <https://github.com/libretro-thumbnails> |
| "Game Boy" ASCII art | `easyroms/launchimages/loading.ascii` | Haley Jane Wakenshaw (hjw '97) |

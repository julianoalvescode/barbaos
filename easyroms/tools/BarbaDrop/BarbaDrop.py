#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# BarbaDrop - game downloader for R36S / ArkOS
# by Barba777
#
# Downloads games from sources set in config.json (by default, a server on
# your PC running pc/barbadrop_server.py), installs them in the system folder
# under /roms, extracts .zip/.7z and adds boxart (libretro-thumbnails) to
# gamelist.xml.
#
# Compatible with Python 3.7 (ArkOS).

import ctypes
import html
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

APP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(APP, 'lib'))

import sdl2  # noqa: E402
import sdl2.sdlttf as ttf  # noqa: E402

VERSION = '1.0'
W, H = 640, 480
ON_DEVICE = os.path.isdir('/roms') and sys.platform.startswith('linux')
ROMS = os.environ.get('BARBADROP_ROMS') or ('/roms' if ON_DEVICE else os.path.join(APP, 'roms_teste'))
CFG_PATH = os.path.join(APP, 'config.json')
CACHE = os.path.join(APP, 'cache')
FONT = os.path.join(APP, 'lib', 'DejaVuSans.ttf')
RESTART_FLAG = '/tmp/barbadrop_restart_es'
UA = {'User-Agent': 'BarbaDrop/' + VERSION}

LIBRETRO = {
    'gba': 'Nintendo - Game Boy Advance', 'gb': 'Nintendo - Game Boy', 'gbc': 'Nintendo - Game Boy Color',
    'nes': 'Nintendo - Nintendo Entertainment System', 'fds': 'Nintendo - Family Computer Disk System',
    'snes': 'Nintendo - Super Nintendo Entertainment System', 'sfc': 'Nintendo - Super Nintendo Entertainment System',
    'n64': 'Nintendo - Nintendo 64', 'nds': 'Nintendo - Nintendo DS', 'virtualboy': 'Nintendo - Virtual Boy',
    'genesis': 'Sega - Mega Drive - Genesis', 'megadrive': 'Sega - Mega Drive - Genesis',
    'mastersystem': 'Sega - Master System - Mark III', 'gamegear': 'Sega - Game Gear',
    'segacd': 'Sega - Mega-CD - Sega CD', 'sega32x': 'Sega - 32X', 'sg-1000': 'Sega - SG-1000',
    'psx': 'Sony - PlayStation', 'psp': 'Sony - PlayStation Portable',
    'pcengine': 'NEC - PC Engine - TurboGrafx 16', 'pcenginecd': 'NEC - PC Engine CD - TurboGrafx-CD',
    'atari2600': 'Atari - 2600', 'atari7800': 'Atari - 7800', 'lynx': 'Atari - Lynx',
    'ngp': 'SNK - Neo Geo Pocket', 'ngpc': 'SNK - Neo Geo Pocket Color', 'wonderswan': 'Bandai - WonderSwan',
    'wonderswancolor': 'Bandai - WonderSwan Color', 'msx': 'Microsoft - MSX', 'colecovision': 'Coleco - ColecoVision',
    'fbneo': 'FBNeo - Arcade Games', 'mame2003': 'MAME', 'arcade': 'MAME', 'neogeo': 'SNK - Neo Geo',
}
KEEP_ZIP = {'arcade', 'fbneo', 'fba', 'mame', 'mame2000', 'mame2003', 'mame2003-plus', 'mame2010', 'hbmame',
            'neogeo', 'cps1', 'cps2', 'cps3', 'atomiswave', 'naomi', 'daphne', 'dos', 'pico-8'}
SKIP_EXT = ('.html', '.htm', '.xml', '.txt', '.png', '.jpg', '.jpeg', '.md', '.json', '.ini', '.db', '.nfo', '.part')

DEFAULT_CFG = {
    'pc_host': '192.168.0.10',
    'pc_port': 8000,
    'swap_ab': False,
    'boxart': True,
    'sources': [
        {'name': 'My PC', 'type': 'dir', 'url': 'http://{PC}/', 'system': '*'},
    ],
}

# ------------------------------------------------------------------ helpers


def log(*a):
    print('[BarbaDrop]', *a)
    sys.stdout.flush()


def load_cfg():
    cfg = json.loads(json.dumps(DEFAULT_CFG))
    try:
        with open(CFG_PATH, encoding='utf-8') as f:
            cfg.update(json.load(f))
    except FileNotFoundError:
        save_cfg(cfg)
    except Exception as e:
        log('invalid config.json:', e)
    return cfg


def save_cfg(cfg):
    with open(CFG_PATH, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def expand(url, cfg):
    return url.replace('{PC}', '%s:%s' % (cfg['pc_host'], cfg['pc_port']))


def http_open(url, timeout=20, method='GET'):
    req = urllib.request.Request(url, headers=UA, method=method)
    return urllib.request.urlopen(req, timeout=timeout)


def fetch_text(url, timeout=20):
    if not re.match(r'https?://', url):
        path = url if os.path.isabs(url) else os.path.join(APP, url)
        with open(path, encoding='utf-8') as f:
            return f.read()
    with http_open(url, timeout) as r:
        return r.read().decode('utf-8', 'replace')


def list_dir(url):
    """Parse an HTTP directory listing (python http.server, nginx, apache)."""
    page = fetch_text(url)
    out, seen = [], set()
    for h in re.findall(r'href\s*=\s*"([^"]+)"', page, re.I):
        h = html.unescape(h)
        if h.startswith(('?', '#', '/', '..', 'mailto:')) or '://' in h:
            continue
        name = urllib.parse.unquote(h.rstrip('/'))
        if not name or name in seen:
            continue
        seen.add(name)
        out.append({'name': name, 'url': urllib.parse.urljoin(url, h), 'dir': h.endswith('/')})
    return out


def title_of(fname):
    return os.path.splitext(fname)[0]


def human(n):
    if not n:
        return ''
    for u in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or u == 'GB':
            return ('%.0f %s' if u in ('B', 'KB') else '%.1f %s') % (n, u)
        n /= 1024.0


def norm(s):
    s = re.sub(r'\s*(\(.*?\)|\[.*?\])', '', s).lower().replace('&', 'and').replace(' _ ', ' and ')
    s = re.sub(r"^(the )|, the\b", '', s.strip())
    s = re.sub(r'\b(and|the|of)\b', '', s)
    return re.sub(r'[^a-z0-9]', '', s)


def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def installed_stems(system):
    d = os.path.join(ROMS, system)
    try:
        return {os.path.splitext(f)[0].lower() for f in os.listdir(d)}
    except OSError:
        return set()


# ------------------------------------------------------------------ boxart


_box_index = {}


def boxart_index(system):
    if system in _box_index:
        return _box_index[system]
    lib = LIBRETRO.get(system)
    if not lib:
        return None
    os.makedirs(CACHE, exist_ok=True)
    cpath = os.path.join(CACHE, system + '.json')
    names = None
    if os.path.exists(cpath) and time.time() - os.path.getmtime(cpath) < 30 * 86400:
        try:
            names = json.load(open(cpath, encoding='utf-8'))
        except Exception:
            names = None
    if names is None:
        url = 'https://thumbnails.libretro.com/%s/Named_Boxarts/' % urllib.parse.quote(lib)
        names = [e['name'][:-4] for e in list_dir(url) if e['name'].lower().endswith('.png')]
        json.dump(names, open(cpath, 'w', encoding='utf-8'))
    idx = {}
    for n in names:
        idx.setdefault(norm(n), []).append(n)
    _box_index[system] = idx
    return idx


def pick_region(cands):
    def score(n):
        r = 0
        for t, w in (('USA', 4), ('Brazil', 3), ('Europe', 2), ('World', 2)):
            if t in n:
                r += w
        if re.search(r'Beta|Proto|Demo|Sample|Kiosk|Hack|Pirate', n):
            r -= 10
        return r
    return max(cands, key=score)


def fetch_boxart(system, rom_file):
    idx = boxart_index(system)
    if not idx:
        return None
    stem = os.path.splitext(rom_file)[0]
    cands = idx.get(norm(stem))
    if not cands:
        return None
    name = pick_region(cands)
    url = 'https://thumbnails.libretro.com/%s/Named_Boxarts/%s.png' % (
        urllib.parse.quote(LIBRETRO[system]), urllib.parse.quote(re.sub(r'[&*/:`<>?\\|"]', '_', name)))
    imgdir = os.path.join(ROMS, system, 'images')
    os.makedirs(imgdir, exist_ok=True)
    dest = os.path.join(imgdir, stem + '-image.png')
    with http_open(url, 30) as r, open(dest, 'wb') as f:
        shutil.copyfileobj(r, f)
    return './images/' + stem + '-image.png'


def gamelist_add(system, rom_file, image):
    path = os.path.join(ROMS, system, 'gamelist.xml')
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception:
        root = ET.Element('gameList')
        tree = ET.ElementTree(root)
    rel = './' + rom_file
    game = None
    for g in root.findall('game'):
        if (g.findtext('path') or '') == rel:
            game = g
            break
    if game is None:
        game = ET.SubElement(root, 'game')
        ET.SubElement(game, 'path').text = rel
    if game.find('name') is None:
        ET.SubElement(game, 'name').text = re.sub(r'\s*(\(.*?\)|\[.*?\])', '', title_of(rom_file)).strip()
    if image:
        el = game.find('image')
        if el is None:
            el = ET.SubElement(game, 'image')
        el.text = image
    tmp = path + '.tmp'
    tree.write(tmp, encoding='utf-8', xml_declaration=True)
    os.replace(tmp, path)


# -------------------------------------------------------------- downloads


class Job(object):
    def __init__(self, entry, system):
        self.entry, self.system = entry, system
        self.state = 'queued'          # queued, downloading, extracting, boxart, ok, error, cancelled
        self.done = 0
        self.total = entry.get('size') or 0
        self.speed = 0.0
        self.msg = ''
        self.cancel = False

    @property
    def active(self):
        return self.state in ('queued', 'downloading', 'extracting', 'boxart')


class Downloader(object):
    def __init__(self, cfg):
        self.cfg = cfg
        self.jobs = []
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.installed_any = False
        threading.Thread(target=self.run, daemon=True).start()

    def add(self, entry, system):
        with self.lock:
            for j in self.jobs:
                if j.entry['url'] == entry['url'] and j.active:
                    return None
            j = Job(entry, system)
            self.jobs.append(j)
        self.wake.set()
        return j

    def retry(self, j):
        if not j.active:
            j.state, j.done, j.msg, j.cancel = 'queued', 0, '', False
            self.wake.set()

    def busy(self):
        return any(j.active for j in self.jobs)

    def current(self):
        for j in self.jobs:
            if j.state in ('downloading', 'extracting', 'boxart'):
                return j
        return None

    def run(self):
        while True:
            job = None
            with self.lock:
                for j in self.jobs:
                    if j.state == 'queued':
                        job = j
                        break
            if not job:
                self.wake.wait(1.0)
                self.wake.clear()
                continue
            try:
                self.process(job)
            except Exception as e:
                if job.cancel:
                    job.state, job.msg = 'cancelled', ''
                else:
                    job.state, job.msg = 'error', str(e)[:80]
                    log('error on', job.entry['name'], repr(e))

    def process(self, job):
        sysdir = os.path.join(ROMS, job.system)
        os.makedirs(sysdir, exist_ok=True)
        fname = os.path.basename(job.entry['name'])
        dest = os.path.join(sysdir, fname)
        part = dest + '.part'
        job.state = 'downloading'
        with http_open(job.entry['url'], 30) as r:
            job.total = int(r.headers.get('Content-Length') or 0) or job.total
            if job.total and shutil.disk_usage(sysdir).free < job.total * 2.2 + 50 * 2 ** 20:
                raise Exception('Not enough space on the SD card')
            last, lastd = time.time(), 0
            with open(part, 'wb') as f:
                while True:
                    if job.cancel:
                        break
                    buf = r.read(65536)
                    if not buf:
                        break
                    f.write(buf)
                    job.done += len(buf)
                    now = time.time()
                    if now - last >= 0.5:
                        job.speed = (job.done - lastd) / (now - last)
                        last, lastd = now, job.done
        if job.cancel:
            os.remove(part)
            job.state = 'cancelled'
            return
        if job.total and job.done < job.total:
            os.remove(part)
            raise Exception('Incomplete download')
        os.replace(part, dest)

        main_file = fname
        ext = os.path.splitext(fname)[1].lower()
        if job.system not in KEEP_ZIP and ext in ('.zip', '.7z'):
            job.state = 'extracting'
            main_file = self.extract(dest, sysdir) or fname

        if self.cfg.get('boxart', True) and job.system in LIBRETRO:
            job.state = 'boxart'
            img = None
            try:
                img = fetch_boxart(job.system, main_file)
            except Exception as e:
                log('boxart failed:', e)
            try:
                gamelist_add(job.system, main_file, img)
            except Exception as e:
                log('gamelist falhou:', e)
            job.msg = 'with boxart' if img else 'no boxart'
        job.state = 'ok'
        self.installed_any = True

    def extract(self, archive, sysdir):
        before = set(os.listdir(sysdir))
        if archive.lower().endswith('.zip'):
            root = os.path.realpath(sysdir)
            with zipfile.ZipFile(archive) as z:
                for m in z.infolist():
                    if m.is_dir():
                        continue
                    target = os.path.realpath(os.path.join(sysdir, m.filename))
                    if not target.startswith(root + os.sep):
                        continue  # guard against zip slip
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with z.open(m) as src, open(target, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
        else:
            sevenz = None
            for p in ('/opt/system/Tools/PortMaster/7zzs.aarch64', '/roms/tools/PortMaster/7zzs.aarch64',
                      os.path.join(APP, '..', 'PortMaster', '7zzs.aarch64')):
                if os.path.exists(p):
                    sevenz = p
                    break
            if not sevenz:
                return None  # keep the .7z as is
            subprocess.check_call([sevenz, 'x', '-y', '-o' + sysdir, archive], stdout=subprocess.DEVNULL)
        os.remove(archive)
        new = [f for f in set(os.listdir(sysdir)) - before if os.path.isfile(os.path.join(sysdir, f))]
        if not new:
            return None
        for pref in ('.m3u', '.cue', '.gdi', '.chd'):
            for f in new:
                if f.lower().endswith(pref):
                    return f
        return max(new, key=lambda f: os.path.getsize(os.path.join(sysdir, f)))


# --------------------------------------------------------------------- UI

C_BG = (18, 18, 22)
C_PANEL = (30, 30, 36)
C_RED = (196, 30, 36)
C_RED_D = (120, 18, 22)
C_TXT = (235, 235, 235)
C_DIM = (150, 150, 160)
C_OK = (90, 200, 110)
C_WARN = (240, 180, 60)
C_ERR = (240, 90, 90)

KEYS = ['1234567890', 'QWERTYUIOP', 'ASDFGHJKL.', 'ZXCVBNM-_:']


class Gfx(object):
    def __init__(self):
        sdl2.SDL_SetHint(sdl2.SDL_HINT_RENDER_SCALE_QUALITY, b'1')
        if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO | sdl2.SDL_INIT_GAMECONTROLLER | sdl2.SDL_INIT_JOYSTICK) != 0:
            raise RuntimeError(sdl2.SDL_GetError())
        ttf.TTF_Init()
        flags = sdl2.SDL_WINDOW_FULLSCREEN_DESKTOP if ON_DEVICE else 0
        self.win = sdl2.SDL_CreateWindow(b'BarbaDrop', sdl2.SDL_WINDOWPOS_CENTERED, sdl2.SDL_WINDOWPOS_CENTERED,
                                         W, H, flags | sdl2.SDL_WINDOW_SHOWN)
        self.ren = sdl2.SDL_CreateRenderer(self.win, -1, sdl2.SDL_RENDERER_ACCELERATED)
        if not self.ren:
            self.ren = sdl2.SDL_CreateRenderer(self.win, -1, sdl2.SDL_RENDERER_SOFTWARE)
        sdl2.SDL_RenderSetLogicalSize(self.ren, W, H)
        sdl2.SDL_SetRenderDrawBlendMode(self.ren, sdl2.SDL_BLENDMODE_BLEND)
        self.fonts = {}
        self.cache = {}

    def font(self, size):
        if size not in self.fonts:
            self.fonts[size] = ttf.TTF_OpenFont(FONT.encode('utf-8'), size)
        return self.fonts[size]

    def measure(self, txt, size):
        w, h = ctypes.c_int(), ctypes.c_int()
        ttf.TTF_SizeUTF8(self.font(size), txt.encode('utf-8'), ctypes.byref(w), ctypes.byref(h))
        return w.value

    def fit(self, txt, size, maxw):
        if maxw is None or self.measure(txt, size) <= maxw:
            return txt
        lo, hi = 0, len(txt)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.measure(txt[:mid] + '…', size) <= maxw:
                lo = mid
            else:
                hi = mid - 1
        return txt[:lo] + '…'

    def text(self, txt, x, y, size=18, color=C_TXT, align='l', maxw=None):
        if not txt:
            return 0
        txt = self.fit(txt, size, maxw)
        key = (txt, size, color)
        if key not in self.cache:
            if len(self.cache) > 600:
                for t, _, _ in self.cache.values():
                    sdl2.SDL_DestroyTexture(t)
                self.cache.clear()
            surf = ttf.TTF_RenderUTF8_Blended(self.font(size), txt.encode('utf-8'), sdl2.SDL_Color(*color))
            if not surf:
                return 0
            tex = sdl2.SDL_CreateTextureFromSurface(self.ren, surf)
            self.cache[key] = (tex, surf.contents.w, surf.contents.h)
            sdl2.SDL_FreeSurface(surf)
        tex, w, h = self.cache[key]
        if align == 'r':
            x -= w
        elif align == 'c':
            x -= w // 2
        sdl2.SDL_RenderCopy(self.ren, tex, None, sdl2.SDL_Rect(int(x), int(y), w, h))
        return w

    def rect(self, x, y, w, h, color, alpha=255):
        sdl2.SDL_SetRenderDrawColor(self.ren, color[0], color[1], color[2], alpha)
        sdl2.SDL_RenderFillRect(self.ren, sdl2.SDL_Rect(int(x), int(y), int(w), int(h)))

    def clear(self):
        self.rect(0, 0, W, H, C_BG)

    def present(self):
        sdl2.SDL_RenderPresent(self.ren)


class Input(object):
    """Gamepad (SDL GameController), raw joystick and keyboard -> actions."""
    CB = {
        sdl2.SDL_CONTROLLER_BUTTON_A: 'a', sdl2.SDL_CONTROLLER_BUTTON_B: 'b',
        sdl2.SDL_CONTROLLER_BUTTON_X: 'x', sdl2.SDL_CONTROLLER_BUTTON_Y: 'y',
        sdl2.SDL_CONTROLLER_BUTTON_LEFTSHOULDER: 'l', sdl2.SDL_CONTROLLER_BUTTON_RIGHTSHOULDER: 'r',
        sdl2.SDL_CONTROLLER_BUTTON_START: 'start', sdl2.SDL_CONTROLLER_BUTTON_BACK: 'select',
        sdl2.SDL_CONTROLLER_BUTTON_DPAD_UP: 'up', sdl2.SDL_CONTROLLER_BUTTON_DPAD_DOWN: 'down',
        sdl2.SDL_CONTROLLER_BUTTON_DPAD_LEFT: 'left', sdl2.SDL_CONTROLLER_BUTTON_DPAD_RIGHT: 'right',
    }
    KB = {
        sdl2.SDLK_UP: 'up', sdl2.SDLK_DOWN: 'down', sdl2.SDLK_LEFT: 'left', sdl2.SDLK_RIGHT: 'right',
        sdl2.SDLK_RETURN: 'a', sdl2.SDLK_z: 'a', sdl2.SDLK_ESCAPE: 'b', sdl2.SDLK_x: 'b', sdl2.SDLK_BACKSPACE: 'b',
        sdl2.SDLK_s: 'x', sdl2.SDLK_a: 'y', sdl2.SDLK_q: 'l', sdl2.SDLK_w: 'r',
        sdl2.SDLK_SPACE: 'start', sdl2.SDLK_TAB: 'select',
    }
    DIRS = ('up', 'down', 'left', 'right')

    def __init__(self, cfg):
        self.swap = cfg.get('swap_ab', False)
        self.joymap = {int(v): k for k, v in cfg.get('joy_buttons', {}).items()}
        self.pads, self.gc_ids, self.joys = {}, set(), {}
        db = os.environ.get('SDL_GAMECONTROLLERCONFIG_FILE')
        if db and os.path.exists(db):
            sdl2.SDL_GameControllerAddMappingsFromFile(db.encode('utf-8'))
        for i in range(sdl2.SDL_NumJoysticks()):
            self.open(i)
        self.held, self.next_rep = None, 0
        self.axis_dir = {}

    def open(self, i):
        if sdl2.SDL_IsGameController(i):
            gc = sdl2.SDL_GameControllerOpen(i)
            if gc:
                jid = sdl2.SDL_JoystickInstanceID(sdl2.SDL_GameControllerGetJoystick(gc))
                self.pads[jid] = gc
                self.gc_ids.add(jid)
                log('controle:', sdl2.SDL_GameControllerName(gc))
                return
        j = sdl2.SDL_JoystickOpen(i)
        if j:
            self.joys[sdl2.SDL_JoystickInstanceID(j)] = j
            log('unmapped joystick:', sdl2.SDL_JoystickName(j), '- set "joy_buttons" in config.json')

    def _press(self, act, out):
        if self.swap and act in ('a', 'b'):
            act = 'b' if act == 'a' else 'a'
        out.append(act)
        if act in self.DIRS:
            self.held, self.next_rep = act, time.time() + 0.35

    def _release(self, act):
        if act == self.held:
            self.held = None

    def poll(self):
        out = []
        ev = sdl2.SDL_Event()
        while sdl2.SDL_PollEvent(ctypes.byref(ev)):
            t = ev.type
            if t == sdl2.SDL_QUIT:
                out.append('quit')
            elif t == sdl2.SDL_CONTROLLERDEVICEADDED:
                if not sdl2.SDL_GameControllerFromInstanceID(sdl2.SDL_JoystickGetDeviceInstanceID(ev.cdevice.which)):
                    self.open(ev.cdevice.which)
            elif t == sdl2.SDL_CONTROLLERBUTTONDOWN:
                a = self.CB.get(ev.cbutton.button)
                if a:
                    self._press(a, out)
            elif t == sdl2.SDL_CONTROLLERBUTTONUP:
                a = self.CB.get(ev.cbutton.button)
                if a:
                    self._release(a)
            elif t == sdl2.SDL_CONTROLLERAXISMOTION and ev.caxis.axis in (0, 1):
                v = ev.caxis.value
                neg, pos = ('left', 'right') if ev.caxis.axis == 0 else ('up', 'down')
                d = neg if v < -20000 else pos if v > 20000 else None
                if d != self.axis_dir.get(ev.caxis.axis):
                    if self.axis_dir.get(ev.caxis.axis):
                        self._release(self.axis_dir[ev.caxis.axis])
                    if d:
                        self._press(d, out)
                    self.axis_dir[ev.caxis.axis] = d
            elif t == sdl2.SDL_JOYBUTTONDOWN and ev.jbutton.which not in self.gc_ids:
                a = self.joymap.get(ev.jbutton.button)
                log('joy botao', ev.jbutton.button, '->', a)
                if a:
                    self._press(a, out)
            elif t == sdl2.SDL_JOYBUTTONUP and ev.jbutton.which not in self.gc_ids:
                a = self.joymap.get(ev.jbutton.button)
                if a:
                    self._release(a)
            elif t == sdl2.SDL_JOYHATMOTION and ev.jhat.which not in self.gc_ids:
                v = ev.jhat.value
                d = 'up' if v & 1 else 'right' if v & 2 else 'down' if v & 4 else 'left' if v & 8 else None
                if d:
                    self._press(d, out)
                else:
                    self.held = None
            elif t == sdl2.SDL_KEYDOWN and not ev.key.repeat:
                a = self.KB.get(ev.key.keysym.sym)
                if a:
                    self._press(a, out)
            elif t == sdl2.SDL_KEYUP:
                a = self.KB.get(ev.key.keysym.sym)
                if a:
                    self._release(a)
        if self.held and time.time() >= self.next_rep:
            out.append(self.held)
            self.next_rep = time.time() + 0.07
        return out


class Async(object):
    def __init__(self, fn, *args):
        self.result, self.error, self.done = None, None, False
        threading.Thread(target=self._run, args=(fn,) + args, daemon=True).start()

    def _run(self, fn, *args):
        try:
            self.result = fn(*args)
        except Exception as e:
            self.error = e
            log('error:', repr(e))
        self.done = True


class Screen(object):
    title = ''
    hints = ''

    def __init__(self, app):
        self.app, self.sel, self.top = app, 0, 0

    def items(self):
        return []

    def move(self, act, n):
        if n == 0:
            return
        step = {'up': -1, 'down': 1, 'left': -10, 'right': 10}[act]
        new = self.sel + step
        if act in ('up', 'down'):
            new %= n
        self.sel = max(0, min(n - 1, new))


class ListScreen(Screen):
    ROW = 30
    Y0 = 64

    def visible(self):
        return (H - self.Y0 - 70) // self.ROW

    def draw_list(self, g, rows, empty='(empty)'):
        vis = self.visible()
        if self.sel < self.top:
            self.top = self.sel
        if self.sel >= self.top + vis:
            self.top = self.sel - vis + 1
        if not rows:
            g.text(empty, W // 2, self.Y0 + 60, 18, C_DIM, 'c', W - 40)
            return
        for i in range(self.top, min(len(rows), self.top + vis)):
            y = self.Y0 + (i - self.top) * self.ROW
            left, right, rcol = rows[i]
            if i == self.sel:
                g.rect(8, y, W - 16, self.ROW - 2, C_RED_D)
                g.rect(8, y, 4, self.ROW - 2, C_RED)
            rw = g.measure(right, 15) + 16 if right else 0
            g.text(left, 20, y + 4, 18, C_TXT, 'l', W - 44 - rw)
            if right:
                g.text(right, W - 18, y + 6, 15, rcol or C_DIM, 'r')
        if len(rows) > vis:
            th = max(20, int((H - self.Y0 - 70) * vis / len(rows)))
            ty = self.Y0 + int((H - self.Y0 - 70 - th) * self.top / max(1, len(rows) - vis))
            g.rect(W - 6, ty, 3, th, C_DIM)


class Home(ListScreen):
    title = 'BarbaDrop'
    hints = 'A open    B/START quit    SELECT downloads'

    def entries(self):
        e = [(s['name'], 'source', s) for s in self.app.cfg['sources']]
        e.append(('Downloads (%d)' % len(self.app.dl.jobs), 'queue', None))
        e.append(('Set PC IP address  [%s:%s]' % (self.app.cfg['pc_host'], self.app.cfg['pc_port']), 'ip', None))
        e.append(('Quit', 'quit', None))
        return e

    def handle(self, act):
        e = self.entries()
        if act in self.DIRS:
            self.move(act, len(e))
        elif act == 'a':
            _, kind, src = e[self.sel]
            if kind == 'source':
                if src.get('system') == '*':
                    self.app.push(Systems(self.app, src))
                else:
                    self.app.push(Games(self.app, src, src['system'], expand(src['url'], self.app.cfg)))
            elif kind == 'queue':
                self.app.push(Queue(self.app))
            elif kind == 'ip':
                cur = '%s:%s' % (self.app.cfg['pc_host'], self.app.cfg['pc_port'])
                self.app.push(Keyboard(self.app, 'PC IP address (e.g. 192.168.0.10:8000)', cur, self.set_ip))
            elif kind == 'quit':
                self.app.quit()
        elif act in ('b', 'start'):
            self.app.quit()
        elif act == 'select':
            self.app.push(Queue(self.app))

    DIRS = Input.DIRS

    def set_ip(self, txt):
        txt = txt.strip()
        host, _, port = txt.partition(':')
        if not re.match(r'^[A-Za-z0-9.\-]+$', host or ''):
            self.app.toast('Invalid IP address', C_ERR)
            return
        self.app.cfg['pc_host'] = host
        self.app.cfg['pc_port'] = int(port) if port.isdigit() else 8000
        save_cfg(self.app.cfg)
        self.app.toast('IP saved: %s:%s' % (host, self.app.cfg['pc_port']), C_OK)

    def draw(self, g):
        rows = []
        for name, kind, src in self.entries():
            right = ''
            if kind == 'source':
                right = 'all systems' if src.get('system') == '*' else src.get('system', '')
            rows.append((name, right, None))
        self.draw_list(g, rows)


class Systems(ListScreen):
    hints = 'A open    B back    Y reload'
    DIRS = Input.DIRS

    def __init__(self, app, src):
        ListScreen.__init__(self, app)
        self.src = src
        self.title = src['name']
        self.reload()

    def reload(self):
        self.task = Async(list_dir, expand(self.src['url'], self.app.cfg))

    def handle(self, act):
        data = [e for e in (self.task.result or []) if e['dir']]
        if act in self.DIRS:
            self.move(act, len(data))
        elif act == 'a' and data:
            e = data[self.sel]
            self.app.push(Games(self.app, self.src, e['name'], e['url']))
        elif act == 'b':
            self.app.pop()
        elif act == 'y':
            self.reload()

    def draw(self, g):
        if not self.task.done:
            g.text('Connecting to %s …' % expand(self.src['url'], self.app.cfg), W // 2, 200, 18, C_DIM, 'c', W - 40)
            return
        if self.task.error:
            g.text('Could not connect.', W // 2, 170, 20, C_ERR, 'c')
            g.text(str(self.task.error), W // 2, 205, 15, C_DIM, 'c', W - 40)
            g.text('Check Wi-Fi and the PC IP address on the home screen.', W // 2, 240, 16, C_DIM, 'c')
            return
        data = [e for e in self.task.result if e['dir']]
        rows = []
        for e in data:
            ok = os.path.isdir(os.path.join(ROMS, e['name']))
            rows.append((e['name'], LIBRETRO.get(e['name'], '') if ok else 'folder missing on console',
                         C_DIM if ok else C_WARN))
        self.draw_list(g, rows, 'No system folders on the server (e.g. gba, snes, nes).')


class Games(ListScreen):
    hints = 'A download   X search   L/R letter   Y reload   SELECT queue   B back'
    DIRS = Input.DIRS

    def __init__(self, app, src, system, url):
        ListScreen.__init__(self, app)
        self.src, self.system, self.url = src, system, url
        self.title = '%s / %s' % (src['name'], system)
        self.query = ''
        self.reload()

    def reload(self):
        if self.src.get('type') == 'json':
            self.task = Async(self.load_json)
        else:
            self.task = Async(list_dir, self.url)
        self.stems = installed_stems(self.system)

    def load_json(self):
        data = json.loads(fetch_text(self.url))
        out = []
        for g in data.get('games', data if isinstance(data, list) else []):
            if g.get('system', self.system) == self.system:
                out.append({'name': g.get('file') or os.path.basename(urllib.parse.urlparse(g['url']).path),
                            'url': g['url'], 'size': g.get('size'), 'dir': False, 'title': g.get('name')})
        return out

    def games(self):
        data = [e for e in (self.task.result or [])
                if not e['dir'] and not e['name'].lower().endswith(SKIP_EXT)]
        if self.query:
            words = self.query.lower().split()
            data = [e for e in data if all(w in e['name'].lower() for w in words)]
        return data

    def handle(self, act):
        data = self.games()
        if act in self.DIRS:
            self.move(act, len(data))
        elif act in ('l', 'r') and data:
            cur = data[self.sel]['name'][:1].upper()
            rng = range(self.sel - 1, -1, -1) if act == 'l' else range(self.sel + 1, len(data))
            for i in rng:
                c = data[i]['name'][:1].upper()
                if c != cur:
                    if act == 'l':
                        while i > 0 and data[i - 1]['name'][:1].upper() == c:
                            i -= 1
                    self.sel = i
                    break
        elif act == 'a' and data:
            e = data[self.sel]
            if self.app.dl.add(e, self.system):
                self.app.toast('Queued: ' + title_of(e['name']), C_OK)
            else:
                self.app.toast('Already in queue', C_WARN)
        elif act == 'x':
            self.app.push(Keyboard(self.app, 'Search game', self.query, self.set_query))
        elif act == 'y':
            self.reload()
        elif act == 'select':
            self.app.push(Queue(self.app))
        elif act == 'b':
            if self.query:
                self.query, self.sel = '', 0
            else:
                self.app.pop()

    def set_query(self, q):
        self.query, self.sel, self.top = q.strip(), 0, 0

    def status(self, e):
        for j in reversed(self.app.dl.jobs):
            if j.entry['url'] == e['url']:
                if j.state == 'downloading':
                    pct = int(j.done * 100 / j.total) if j.total else 0
                    return '%d%%' % pct, C_WARN
                if j.state in ('queued', 'extracting', 'boxart'):
                    return j.state, C_WARN
                if j.state == 'ok':
                    return '✓ installed', C_OK
                if j.state == 'error':
                    return '✗ error', C_ERR
        if os.path.splitext(e['name'])[0].lower() in self.stems:
            return '✓ installed', C_OK
        return human(e.get('size')), C_DIM

    def draw(self, g):
        if not self.task.done:
            g.text('Loading list…', W // 2, 200, 18, C_DIM, 'c')
            return
        if self.task.error:
            g.text('Could not load the list.', W // 2, 180, 20, C_ERR, 'c')
            g.text(str(self.task.error), W // 2, 215, 15, C_DIM, 'c', W - 40)
            return
        data = self.games()
        if any(j.state == 'ok' for j in self.app.dl.jobs):
            self.stems = installed_stems(self.system)
        rows = []
        for e in data:
            right, col = self.status(e)
            rows.append((e.get('title') or title_of(e['name']), right, col))
        info = '%d games' % len(data) + ('  ·  search: "%s"' % self.query if self.query else '')
        g.text(info, W - 14, 40, 14, C_DIM, 'r')
        self.draw_list(g, rows, 'No games found.')


class Queue(ListScreen):
    title = 'Downloads'
    hints = 'A retry   X cancel   B back'
    DIRS = Input.DIRS

    def handle(self, act):
        jobs = self.app.dl.jobs
        if act in self.DIRS:
            self.move(act, len(jobs))
        elif act == 'a' and jobs and jobs[self.sel].state in ('error', 'cancelled'):
            self.app.dl.retry(jobs[self.sel])
        elif act == 'x' and jobs and jobs[self.sel].active:
            jobs[self.sel].cancel = True
            if jobs[self.sel].state == 'queued':
                jobs[self.sel].state = 'cancelled'
        elif act in ('b', 'select'):
            self.app.pop()

    def draw(self, g):
        rows = []
        for j in self.app.dl.jobs:
            if j.state == 'downloading':
                pct = int(j.done * 100 / j.total) if j.total else 0
                r, c = '%d%%  %s/s' % (pct, human(j.speed)), C_WARN
            elif j.state == 'ok':
                r, c = '✓ ' + (j.msg or 'ok'), C_OK
            elif j.state == 'error':
                r, c = '✗ ' + j.msg, C_ERR
            else:
                r, c = j.state, C_WARN if j.active else C_DIM
            rows.append(('[%s] %s' % (j.system, title_of(j.entry['name'])), r, c))
        self.draw_list(g, rows, 'No downloads yet.')


class Keyboard(Screen):
    hints = 'A key   X delete   Y space   START ok   B cancel'

    def __init__(self, app, title, initial, cb):
        Screen.__init__(self, app)
        self.title, self.buf, self.cb = title, initial, cb
        self.r, self.c = 0, 0

    def rows(self):
        return [list(k) for k in KEYS] + [['SPACE', 'DELETE', 'OK']]

    def handle(self, act):
        rows = self.rows()
        if act == 'up':
            self.r = (self.r - 1) % len(rows)
        elif act == 'down':
            self.r = (self.r + 1) % len(rows)
        elif act == 'left':
            self.c -= 1
        elif act == 'right':
            self.c += 1
        self.c %= len(rows[self.r])
        if act == 'a':
            k = rows[self.r][self.c]
            if k == 'SPACE':
                self.buf += ' '
            elif k == 'DELETE':
                self.buf = self.buf[:-1]
            elif k == 'OK':
                self.finish()
            elif len(self.buf) < 40:
                self.buf += k.lower() if self.title.startswith('Search') else k
        elif act == 'x':
            self.buf = self.buf[:-1]
        elif act == 'y':
            self.buf += ' '
        elif act == 'start':
            self.finish()
        elif act == 'b':
            self.app.pop()

    def finish(self):
        self.app.pop()
        self.cb(self.buf)

    def draw(self, g):
        g.rect(30, 70, W - 60, 44, C_PANEL)
        g.text(self.buf + ('_' if int(time.time() * 2) % 2 else ' '), 44, 80, 22, C_TXT, 'l', W - 90)
        rows = self.rows()
        y = 140
        for ri, row in enumerate(rows):
            kw = 52 if ri < len(KEYS) else 160
            total = len(row) * (kw + 6) - 6
            x = (W - total) // 2
            for ci, k in enumerate(row):
                on = (ri == self.r and ci == self.c)
                g.rect(x, y, kw, 46, C_RED if on else C_PANEL)
                g.text(k, x + kw // 2, y + 11, 20 if len(k) == 1 else 16, C_TXT, 'c')
                x += kw + 6
            y += 54


class App(object):
    def __init__(self):
        self.cfg = load_cfg()
        self.g = Gfx()
        self.inp = Input(self.cfg)
        self.dl = Downloader(self.cfg)
        self.stack = [Home(self)]
        self.running = True
        self.toast_msg, self.toast_col, self.toast_t = '', C_TXT, 0
        self.quit_armed = 0
        self.ip = local_ip()
        self.ip_t = time.time()

    def push(self, s):
        self.stack.append(s)

    def pop(self):
        if len(self.stack) > 1:
            self.stack.pop()

    def toast(self, msg, col=C_TXT):
        self.toast_msg, self.toast_col, self.toast_t = msg, col, time.time()

    def quit(self):
        if self.dl.busy() and time.time() - self.quit_armed > 3:
            self.quit_armed = time.time()
            self.toast('Downloads in progress. Press again to quit.', C_WARN)
            return
        self.running = False

    def draw_chrome(self, s):
        g = self.g
        g.rect(0, 0, W, 34, C_RED)
        g.text('BarbaDrop', 12, 4, 20, (255, 255, 255))
        if s.title and s.title != 'BarbaDrop':
            g.text('›  ' + s.title, 128, 7, 17, (255, 230, 230), 'l', 360)
        if time.time() - self.ip_t > 5:
            self.ip, self.ip_t = local_ip(), time.time()
        g.text(('Wi-Fi ' + self.ip) if self.ip else 'No network', W - 10, 9, 14,
               (255, 235, 235) if self.ip else (255, 220, 120), 'r')
        cur = self.dl.current()
        if cur:
            g.rect(0, H - 62, W, 30, C_PANEL)
            frac = (cur.done / float(cur.total)) if cur.total else 0
            g.rect(0, H - 62, int(W * frac), 30, C_RED_D)
            label = '%s %s' % (cur.state.capitalize(), title_of(cur.entry['name']))
            g.text(label, 10, H - 57, 15, C_TXT, 'l', W - 200)
            info = '%s / %s  %s/s' % (human(cur.done), human(cur.total) or '?', human(cur.speed)) \
                if cur.state == 'downloading' else ''
            pend = sum(1 for j in self.dl.jobs if j.state == 'queued')
            g.text(info + ('  +%d' % pend if pend else ''), W - 10, H - 57, 14, C_DIM, 'r')
        g.rect(0, H - 30, W, 30, C_PANEL)
        g.text(s.hints, W // 2, H - 25, 14, C_DIM, 'c', W - 20)
        g.text('by Barba777', W - 8, H - 46 if not cur else H - 80, 11, (90, 90, 100), 'r')
        if self.toast_msg and time.time() - self.toast_t < 2.5:
            tw = min(W - 40, g.measure(self.toast_msg, 17) + 30)
            g.rect((W - tw) // 2, H - 110, tw, 34, (0, 0, 0), 220)
            g.text(self.toast_msg, W // 2, H - 103, 17, self.toast_col, 'c', W - 60)

    def run(self):
        while self.running:
            for act in self.inp.poll():
                if act == 'quit':
                    self.running = False
                elif act == 'start' and not isinstance(self.stack[-1], Keyboard):
                    self.quit()
                else:
                    self.stack[-1].handle(act)
            s = self.stack[-1]
            self.g.clear()
            s.draw(self.g)
            self.draw_chrome(s)
            self.g.present()
            if os.environ.get('BARBADROP_SHOT'):
                return
            sdl2.SDL_Delay(16)
        if self.dl.installed_any and ON_DEVICE:
            open(RESTART_FLAG, 'w').close()


def screenshot(app, path):
    """PC testing only: save the current screen as BMP."""
    g = app.g
    surf = sdl2.SDL_CreateRGBSurfaceWithFormat(0, W, H, 32, sdl2.SDL_PIXELFORMAT_ARGB8888)
    sdl2.SDL_RenderReadPixels(g.ren, None, sdl2.SDL_PIXELFORMAT_ARGB8888, surf.contents.pixels, surf.contents.pitch)
    sdl2.SDL_SaveBMP(surf, path.encode('utf-8'))
    sdl2.SDL_FreeSurface(surf)


if __name__ == '__main__':
    log('versao', VERSION, 'roms em', ROMS)
    App().run()
    sdl2.SDL_Quit()

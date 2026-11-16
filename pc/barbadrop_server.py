#!/usr/bin/env python3
"""
BarbaDrop server - by Barba777

Shares a folder of your games over Wi-Fi so BarbaDrop on the R36S can
download them. The folder must contain one subfolder per system, named like
the folders on the EASYROMS partition:

    games/
      gba/   Some Game (USA).gba
      snes/  Other Game (USA).zip
      nes/   ...

Usage:
    python barbadrop_server.py                 # shares ./games next to this script
    python barbadrop_server.py D:\\MyGames      # shares another folder
    python barbadrop_server.py D:\\MyGames 8080 # custom port (default 8000)

Then on the console: BarbaDrop -> "Set PC IP address" -> type the address shown below.
"""
import functools
import http.server
import os
import socket
import sys


def lan_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith('127.'))


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stdout.write('[%s] %s\n' % (self.address_string(), fmt % args))


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    folder = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(here, 'games')
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    if not os.path.isdir(folder):
        os.makedirs(folder)
        print('Created %s - put your system folders (gba, snes, ...) inside it.' % folder)
    systems = sorted(d for d in os.listdir(folder) if os.path.isdir(os.path.join(folder, d)))

    print('=' * 60)
    print(' BarbaDrop server')
    print(' Sharing : %s' % folder)
    print(' Systems : %s' % (', '.join(systems) or '(none yet)'))
    print(' On the console, set the PC IP address to:')
    for ip in lan_ips() or ['<this PC IP>']:
        print('    %s:%d' % (ip, port))
    print(' Press Ctrl+C to stop.')
    print('=' * 60)

    handler = functools.partial(Handler, directory=folder)
    with http.server.ThreadingHTTPServer(('0.0.0.0', port), handler) as srv:
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print('\nServer stopped.')


if __name__ == '__main__':
    main()

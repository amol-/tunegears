import logging
logging.basicConfig()
log = logging.getLogger()

from threading import Thread
from Queue import Queue, Empty
import subprocess
import time
import os

from gmusicapi import Webclient
gm = Webclient()

class PlayMusicThread(Thread):
    songs_queue = Queue()

    def __init__(self, *args, **kw):
        super(PlayMusicThread, self).__init__(*args, **kw)
        self.daemon = True

    def run(self):
        self.proc = None
        self._detect_mpg123()

        while True:
            if self.proc is None:
                song_id = self.songs_queue.get()
		
                try:
                    song_url = gm.get_stream_url(song_id)
                except Exception as a:
                    log.exception('Failed to retrieve song url')
                    continue
 
                print "Playing " + song_url
                self.proc = subprocess.Popen([self.mpg123, song_url])
            else:
                if not self.proc.poll() is None:
                    self.proc = None
            time.sleep(0.5)

    def skip_song(self):
        if self.proc is not None:
            os.kill(self.proc.pid, SIGTERM)

    def stop_player(self):
        try:
            while self.songes_queue.get(False, 0):
                pass
        except Empty:
            self.skip_song()

    def _detect_mpg123(self):
        self.mpg123 = None

        fin, fout = os.popen4(["which", "mpg123"])
        self.mpg123 = fout.read().replace("\n", "")
        if not len(self.mpg123):
            log.error("mpg123 is not installed")
            self.mpg123 = None
        else:
            log.info('MPG123 detected at %s', self.mpg123)

from tg import AppConfig, TGController, app_globals
from tg import expose


class RootController(TGController):
    @expose()
    def index(self, **kw):
        library = app_globals.library

        html = '<!DOCTYPE html>\n<html><head><script src="/jquery.js"></script></head><body><table>%s</table></body></html>'
        tracks = ('''<tr><td><a href="#" onclick="jQuery.get('/play/%s'); return false;">%s - %s</a></td></tr>''' % (track['id'], track['artist'], track['title']) for track in library)
        return html % ''.join(tracks)

    @expose('json:')
    def play(self, song_id, **kw):
        PlayMusicThread.songs_queue.put(song_id)
        return dict(success=True)


config = AppConfig(minimal=True, root_controller=RootController())
config.renderers = ['jinja', 'json']
config.default_renderer = 'json'
config.serve_static = True
config.paths['static_files'] = '.'
config.tg.app_globals.gm = gm
config.tg.app_globals.player = PlayMusicThread()
config.tg.app_globals.player.start()
from wsgiref.simple_server import make_server
import json

config_options = {}
with open('config.json') as config_file:
    config_options.update(json.load(config_file))

config.tg.app_globals.gm.login(config_options['gm.username'], config_options['gm.password'])
config.tg.app_globals.library = config.tg.app_globals.gm.get_all_songs()

print "Serving on port 8080..."
httpd = make_server('', 8080, config.make_wsgi_app(**config_options))
httpd.serve_forever()

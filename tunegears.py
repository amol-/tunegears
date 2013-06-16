import logging
from signal import SIGTERM

logging.basicConfig()
log = logging.getLogger()

from threading import Thread
from Queue import Queue, Empty
import subprocess
import time
import os

from gmusicapi import Webclient

class PlayMusicThread(Thread):
    songs_queue = Queue()

    def __init__(self, *args, **kw):
        _gm = kw.pop('gm', None)
        _songsmap = kw.pop('songsmap', None)

        super(PlayMusicThread, self).__init__(*args, **kw)

        self.daemon = True
        self._play_info = {}
        self._gm = _gm
        self._songsmap = _songsmap

    def run(self):
        self.proc = None
        self._detect_mpg123()

        while True:
            if self.proc is None:
                song_id = self.songs_queue.get()
		
                try:
                    song_url = self._gm.get_stream_url(song_id)
                except Exception as a:
                    log.exception('Failed to retrieve song url')
                    continue

                # Switch play info in oneshot so we don't have to lock it
                # on CPython
                _play_info = self._songsmap[song_id].copy()
                _play_info['queue_len'] = self.songs_queue.qsize()
                self._play_info = _play_info

                self.proc = subprocess.Popen([self.mpg123, song_url])
            else:
                if not self.proc.poll() is None:
                    self.proc = None
            time.sleep(0.5)

    def skip_song(self):
        if self.proc is not None:
            os.kill(self.proc.pid, SIGTERM)
            self._play_info = {}

    def stop_player(self):
        try:
            while self.songs_queue.get(False, 0):
                pass
        except Empty:
            self.skip_song()

    def queue(self, song_id):
        self.songs_queue.put(song_id)

        _play_info = self._play_info.copy()
        _play_info['queue_len'] = self.songs_queue.qsize()
        self._play_info = _play_info

    def get_playinfo(self):
        # Play Info changes and reads must be oneshot as it's shared between threads
        # we take for granted that we are running on CPython
        pinfo = self._play_info.copy()
        if not pinfo:
            return {'artist': 'None',
                    'title': 'Nothing...',
                    'queue_len': '?'}
        return pinfo

    def _detect_mpg123(self):
        self.mpg123 = None

        fin, fout = os.popen4(["which", "mpg123"])
        self.mpg123 = fout.read().replace("\n", "")
        if not len(self.mpg123):
            log.error("mpg123 is not installed")
            self.mpg123 = None
        else:
            log.info('MPG123 detected at %s', self.mpg123)

import tg
from tg import AppConfig, TGController, app_globals
from tg import expose

BASIC_HTML = '''<!DOCTYPE html>
<html>
  <head>
    <style>
      .btn { width: 24px; height: 24px; background-size: 24px 24px; display: inline-block; }
      #player { margin-bottom: 20px; font-size: 20px; line-height: 24px; }
      .play_btn { background-image: url("play.png"); }
      .stop_btn { background-image: url("stop.png"); }
      .next_btn { background-image: url("next.png"); }
    </style>
    <script src="/jquery.js"></script>
  </head>
  <body>
    <div id="player">
      <div><strong>Now Playing:</strong> <span id="now-playing"></span></div>
      <div>
        <a class="btn stop_btn" href="#" onclick="return playerDo('stop')">&nbsp;</a>
        <a class="btn next_btn" href="#" onclick="return playerDo('next')">&nbsp;</a>
        <strong>In Queue:</strong> <span id="queue-len"></span>
      </div>
    </div>
    </div>
    <table>%(songs)s</table>
    <script>
        function playerDo(action) {
            jQuery.get('/cmd/' + action, updateNowPlaying);
            return false;
        }

        function updateNowPlaying() {
            jQuery.get('/nowplaying.json', function(data) {
                var playingText = data['artist'] + ' - ' + data['title'];
                jQuery('#now-playing').text(playingText);
                jQuery('#queue-len').text(data['queue_len']);
            });
        }

        setInterval(updateNowPlaying, 5000);
    </script>
  </body>
</html>
'''

SONG_ROW = '''<tr>
  <td><a class="btn play_btn" href="#" onclick="return playerDo('play/%(id)s')">&nbsp;</a></td>
  <td>%(artist)s</td>
  <td>%(album)s</td>
  <td>%(title)s</td>
</tr>
'''

class RootController(TGController):
    @expose()
    def index(self, **kw):
        library = app_globals.library

        tracks = (SONG_ROW % track for track in library)
        return BASIC_HTML % dict(songs=''.join(tracks))

    @expose('json:')
    def nowplaying(self):
        # SSE is better suited for this, but as we serve
        # on wsgiref it would block the player.
        playing = app_globals.player.get_playinfo()
        return playing

    @expose('json:')
    def cmd(self, cmd, arg=None):
        if cmd == 'play':
            app_globals.player.queue(arg)
        elif cmd == 'next':
            app_globals.player.skip_song()
        elif cmd == 'stop':
            app_globals.player.stop_player()
        return dict(success=True)

def _setup_music_player():
    log.info('Starting Music Player')
    config = tg.config
    app_globals = config.tg.app_globals

    app_globals.player = PlayMusicThread(gm=app_globals.gm,
                                         songsmap=dict(((song['id'], song) for song in app_globals.library)))
    app_globals.player.start()

def _setup_google_music():
    log.info('Connecting to Google Music')
    config = tg.config
    app_globals = config.tg.app_globals

    app_globals.gm = Webclient()
    app_globals.gm.login(config.gm.username, config.gm.password)

    song_sorting = lambda song: '%(artist)s-%(album)s-%(track)s' % song
    app_globals.library = sorted(app_globals.gm.get_all_songs(), key=song_sorting)

config = AppConfig(minimal=True, root_controller=RootController())
config.renderers = ['json']
config.default_renderer = 'json'
config.serve_static = True
config.paths['static_files'] = '.'
config.register_hook('startup', _setup_google_music)
config.register_hook('startup', _setup_music_player)

from wsgiref.simple_server import make_server
import json

config_options = {}
with open('config.json') as config_file:
    config_options.update(json.load(config_file))

print "Serving on port 8080..."
httpd = make_server('', 8080, config.make_wsgi_app(**config_options))
httpd.serve_forever()

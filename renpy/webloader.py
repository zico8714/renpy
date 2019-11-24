# Copyright 2004-2019 Tom Rothamel <pytom@bishoujo.us>
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from __future__ import print_function
import renpy
import os
import renpy.display

# A list of downloads, in-progress or waiting to be processed
queue = [ ]

if renpy.emscripten:
    import emscripten, json

    # Space-efficient, copy-less download share
    # Note: could be reimplement with pyodide's jsproxy, but let's keep things small
    emscripten.run_script(r"""RenPyWeb = {
    xhr_id: 0,
    xhrs: {},

    dl_new: function(path) {
        var xhr = new XMLHttpRequest();
        xhr.responseType = 'arraybuffer';
        xhr.onerror = function() {
            console.log("Network error", xhr);
        }
        xhr.onload = function() {
            if (xhr.status == 200 || xhr.status == 304 || xhr.status == 206 || (xhr.status == 0 && xhr.response)) {
                // Create file reusing XHR's buffer (no-copy)
                try { FS.unlink(path); } catch {}
                FS.writeFile(path, new Uint8Array(xhr.response), {canOwn:true});
            } else {
                console.log("Download error", xhr);
            }
        }
        xhr.open('GET', path);
        xhr.send();
        RenPyWeb.xhrs[RenPyWeb.xhr_id] = xhr;
        var ret = RenPyWeb.xhr_id;
        RenPyWeb.xhr_id++;
        return ret;
    },

    dl_get: function(xhr_id) {
        return RenPyWeb.xhrs[xhr_id];
    },

    dl_free: function(xhr_id) {
        delete RenPyWeb.xhrs[xhr_id];
        // Note: xhr.response kept alive until file is deleted
    },
}
""")

    class XMLHttpRequest(object):
        def __init__(self, filename):
            url = 'game/' + filename
            self.id = emscripten.run_script_int(
                r'''RenPyWeb.dl_new({})'''.format(json.dumps(url)))
    
        def __del__(self):
            emscripten.run_script(r'''RenPyWeb.dl_free({})'''.format(self.id))
    
        @property
        def readyState(self):
            return emscripten.run_script_int(r'''RenPyWeb.dl_get({}).readyState'''.format(self.id))
    
        @property
        def status(self):
            return emscripten.run_script_int(r'''RenPyWeb.dl_get({}).status'''.format(self.id))

        @property
        def statusText(self):
            return emscripten.run_script_string(r'''RenPyWeb.dl_get({}).statusText'''.format(self.id))

elif os.environ.get('RENPY_SIMULATE_DOWNLOAD', False):
    # simulate
    # Ex: rm -f the_question/game/images/* the_question/game/gui/*_menu.png && unzip -d the_question the_question-7.0-dists/the_question-7.0-web/game.zip game/renpyweb_remote_files.txt && RENPY_SIMULATE_DOWNLOAD=1 ./renpy.sh the_question; git checkout the_question/game/images/ the_question/game/gui/*_menu.png

    import urllib2, urllib, httplib, os, threading

    class XMLHttpRequest(object):
        def __init__(self, filename):
            self.done = False
            self.error = None
            url = 'http://127.0.0.1:8042/game/' + urllib.quote(filename)
            req = urllib2.Request(url)
            def thread_main():
                try:
                    r = urllib2.urlopen(req)
                    fullpath = os.path.join(renpy.config.gamedir, filename)
                    with open(fullpath, 'wb') as f:
                        f.write(r.read())
                    #print("downloaded:", url, '>', fullpath)
                except urllib2.URLError, e:
                    self.error = str(e.reason)
                except httplib.HTTPException, e:
                    self.error = 'HTTPException'
                except Exception, e:
                    self.error = 'Error: ' + str(e)
                self.done = True
            threading.Thread(target=thread_main, name="XMLHttpRequest").start()
    
        @property
        def readyState(self):
            if self.done:
                return 4
            else:
                return 0
    
        @property
        def status(self):
            if self.error:
                return 0
            return 200

        @property
        def statusText(self):
            return self.error or 'OK'


class DownloadNeeded(Exception):
    def __init__(self, relpath):
        self.relpath = relpath


class ReloadRequest:
    def __init__(self, relpath, obj):
        self.relpath = relpath
        self.obj = obj
        #print("download_start:", self.filename)
        self.xhr = XMLHttpRequest(self.relpath)

    def download_completed(self):
        return self.xhr.readyState == 4


def enqueue(relpath, obj_to_reload):
    global queue
    queue.append(ReloadRequest(relpath, obj_to_reload))
    # Note: image: referencing 'obj' directly because:
    # - no relpath->image mapping in the Cache (esp. with multiple search paths)
    # - need to update this instance in particular has it will be referenced by the game
    #   (recreating a new Image with the same path won't work)

def process_downloaded_resources():
    global queue

    postponed = []
    reloaded = False

    for rr in queue:

        if not rr.download_completed():
            postponed.append(rr)
            continue
 
        if isinstance(rr.obj, renpy.display.im.Image):
            fullpath = os.path.join(renpy.config.gamedir,rr.relpath)
            if not os.path.exists(fullpath):
                # don't rethrow exception while in Ren'Py's error handler
                queue.remove(rr)
                # trigger Ren'Py's error handler
                raise IOError("Download error: {} ('{}' > '{}')".format(
                    (rr.xhr.statusText or "network error"), rr.relpath, fullpath))
            #print("reloading", rr.image.filename)
            ce = renpy.display.im.cache.cache.get(rr.obj)
            renpy.display.im.cache.kill(ce)
            renpy.display.im.cache.get(rr.obj, render=True)
            #print("unlink", fullpath)
            os.unlink(fullpath)
            reloaded = True

        # TODO: sounds

    queue = postponed

    if reloaded:
        #renpy.exports.force_full_redraw()  # no effect on already show-n images
        #renpy.game.interface.set_mode()  # heavy, don't respect aspect ratio
        renpy.display.render.free_memory()  # TODO: be more precise
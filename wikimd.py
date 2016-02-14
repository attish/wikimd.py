#!/usr/bin/env python

import web as webpy
import os
import sys
import threading
import time
import datetime
import time
import random
import markdown
import codecs

count = 0

urls = (
    '/wiki/(.*)', 'Frame',
    '/longpoll/([0-9]+)/(.*)', 'LongPoll',
    '/stop', 'Stop',
    '/jquery.js', 'jQuery'
    )

def file_mtime(fname):
    return datetime.datetime.fromtimestamp(os.path.getmtime(fname))

def file_data(fname):
    with codecs.open(fname, encoding="utf-8") as f:
        data = f.read()
    return markdown.markdown(data, tab_length=2)

class LongPoll:
    def GET(self, session_id, page_name):
        global last_refresh
        webpy.header('Content-type', 'text/html')
        last_seen = file_mtime(page_name)
        while last_seen == file_mtime(page_name):
            time.sleep(1)
        return file_data(page_name)

class Stop:
    def GET(self):
        os._exit(0)

class jQuery:
    def GET(self):
        raise webpy.seeother('https://ajax.googleapis.com/ajax/libs/jquery/1.6.2/jquery.min.js')

class Frame:
    def GET(self, page_name):
        randnum = random.randint(0, 2000000000)
        data = file_data(page_name)
        page = """
        <html>
            <head>
                <title>Markdown viewer</title>
                <meta charset="UTF-8">
                <script type="text/javascript" src="/jquery.js"></script>
<style>
%s
</style>
            </head>
            <body>
                <input name="stop" type="button" value="Stop" onclick="stop()"></input>
                <div id="closed" style="width: 30em; background-color: aliceblue; border: 1px solid lightblue; margin: 3em auto; padding: 1em; color: blue; text-align: center; display: none">The server is stopped. You may close the window.</div>
                <div class="container">
                <div id="content">%s</div>
                </div>
            <script type="text/javascript">
                function stop() {
                    $.ajax({url: '/stop'});
                    $('#stop').hide();
                    $('#closed').show(400);
                    $('#content').css('color', 'lightgrey');
                }


                function getContent() {
                    $.ajax({
                        url: '/longpoll/%d/%s',
                        dataType: 'text',
                        type: 'get',
                        success: function(doc){
                            $('#content').fadeTo(1, 0);
                            $('#content').html(doc);
                            $('#content').fadeTo(500, 1);
                            setTimeout('getContent()', 100);
                            }
                    });
                }
                getContent();
            </script>
            </body>
        </html>
        """
#        return page % (data, randnum)
        style = open("/home/attis/watchmd.py/bootstrap-readable.css").read()
        return page % (style, data, randnum, page_name)
        #return page % (randnum, data)
        #return "<head><script>alert('a');</script></head>"

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print "Usage: wikimd.py <port_num>"
        sys.exit(1)
    webapp = webpy.application(urls, globals())
    webapp.run()


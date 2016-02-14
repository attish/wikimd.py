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
    '/', 'Index',
    '/longpoll/([0-9]+)/(.*)', 'LongPoll',
    '/longpoll-index/([0-9]+)', 'LongPollIndex',
    '/stop', 'Stop',
    '/jquery.js', 'jQuery'
    )

def file_mtime(fname):
    return datetime.datetime.fromtimestamp(os.path.getmtime(fname))

def file_data(fname):
    with codecs.open(fname, encoding="utf-8") as f:
        data = f.read()
    return markdown.markdown(data, tab_length=2)

def title_line(file_name):
    with open(file_name, 'r') as f:
        return f.readline()

def index_data():
    link_boiler = "<tr><td><a href='wiki/%s'>%s</a></td></tr>"
    html_boiler = "<h1>Index</h1><table class=\"table\">%s</table>"
    pwd = os.getcwd()
    files = [(f, title_line(f)) for f in os.listdir(pwd) if f.endswith(".md")]
    links = [link_boiler % (f[0], f[1]) for f in files]
    return html_boiler % '\n'.join(links)

def get_dir():
# From http://timgolden.me.uk/python/win32_how_do_i/watch_directory_for_changes.html
    return dict([(f, None) for f in os.listdir(os.getcwd())])


class LongPoll:
    def GET(self, session_id, page_name):
        global last_refresh
        webpy.header('Content-type', 'text/html')
        last_seen = file_mtime(page_name)
        while last_seen == file_mtime(page_name):
            time.sleep(1)
        return file_data(page_name)

class LongPollIndex:
    def GET(self, session_id):
        global last_refresh
        path = os.getcwd()
        webpy.header('Content-type', 'text/html')
        last_dir = get_dir()
        while last_dir == get_dir():
            time.sleep(1)
        return index_data()

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


class Index:
    def GET(self):
        randnum = random.randint(0, 2000000000)
        data = index_data()
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
                        url: '/longpoll-index/%d',
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
        return page % (style, data, randnum)
        #return page % (randnum, data)
        #return "<head><script>alert('a');</script></head>"

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print "Usage: wikimd.py <port_num>"
        sys.exit(1)
    webapp = webpy.application(urls, globals())
    webapp.run()


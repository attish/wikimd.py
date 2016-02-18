#!/usr/bin/env python

import web as webpy
import os
import subprocess
import sys
import threading
import time
import datetime
import time
import random
import markdown
import codecs

count = 0
dir = os.path.dirname(os.path.realpath(__file__))
style = open(dir + "/bootstrap-readable.css").read()

urls = (
    '/wiki/(.*)', 'Frame',
    '/', 'Index',
    '/longpoll/([0-9]+)/(.*)', 'LongPoll',
    '/longpoll-index/([0-9]+)', 'LongPollIndex',
    '/git', 'Git',
    '/commit/([0-9a-f]+)', 'CommitIndex',
    '/longpoll-git/([0-9]+)', 'LongPollGit',
    '/stop', 'Stop',
    '/jquery.js', 'jQuery'
    )

# Outer static HTML boilerplate
# Params:
#   %s style
#   %s content
html_boiler = """
<html>
    <head>
        <title>WikiMD</title>
        <meta charset="UTF-8">
        <script type="text/javascript" src="/jquery.js"></script>
<style>
%s
</style>
    </head>
    <body>
        <input name="stop" type="button" value="Stop" onclick="stop()"></input>
        <a href="/">Index</a>&nbsp;|&nbsp;
        <a href="/git">Git</a>
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
    </script>
    </body>
</html>
"""

# Outer live HTML boilerplate (with longpoll)
# Params:
#   %s style
#   %s content
#   %s longpoll_url
html_live_boiler = """
<html>
    <head>
        <title>WikiMD</title>
        <meta charset="UTF-8">
        <script type="text/javascript" src="/jquery.js"></script>
<style>
%s
</style>
    </head>
    <body>
        <input name="stop" type="button" value="Stop" onclick="stop()"></input>
        <a href="/">Index</a>&nbsp;|&nbsp;
        <a href="/git">Git</a>
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
                url: '%s',
                dataType: 'text',
                type: 'get',
                success: function(doc){
                    if (doc != "") {
                        $('#content').fadeTo(1, 0);
                        $('#content').html(doc);
                        $('#content').fadeTo(500, 1);
                    }
                    setTimeout('getContent()', 100);
                }
            });
        }
        getContent();
    </script>
    </body>
</html>
"""


def run_command(command):
# By Max Persson. http://stackoverflow.com/a/13135985
    p = subprocess.Popen(command,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    return iter(p.stdout.readline, b'')

def file_mtime(fname):
    return datetime.datetime.fromtimestamp(os.path.getmtime(fname))

def file_data(fname):
    with codecs.open(fname, encoding="utf-8") as f:
        data = f.read()
    return markdown.markdown(data, tab_length=2)

def title_line(file_name):
    with open(file_name, 'r') as f:
        return f.readline()

def git_title_line(commit, file_name):
    git_command = ("git show " + commit + ":" + file_name).split()
    file_lines = run_command(git_command)
    return file_lines.next()

def index_data():
    link_boiler = "<tr><td><a href='wiki/%s'>%s</a></td></tr>"
    index_boiler = "<h1>Index</h1><table class=\"table\">%s</table>"
    pwd = os.getcwd()
    files = [(f, title_line(f)) for f in os.listdir(pwd) if f.endswith(".md")]
    links = [link_boiler % (f[0], f[1]) for f in files]
    return index_boiler % '\n'.join(links)

def commit_index_data(commit):
    link_boiler = "<tr><td><a href='/git-wiki/%s/%s'>%s</a></td></tr>"
    index_boiler = "<h1>Index at %s</h1><table class=\"table\">%s</table>"
    pwd = os.getcwd()
    git_command = ("git ls-tree --name-only -r " + commit).split()
    commit_files = run_command(git_command)
    files = [(f, git_title_line(commit, f))
                for f in commit_files
                if f.strip().endswith(".md")]
    links = [link_boiler % (commit, f[0], f[1]) for f in files]
    return index_boiler % (commit, '\n'.join(links))

def git_data():
    is_git = not os.system('git rev-parse')

    cmd_iter = run_command("git log --oneline".split())
    commit_table = '<table class="table">'
    for commit_line in cmd_iter:
        commit_hash = commit_line[0:6]
        commit_title = commit_line[7:]
        commit_table += '<tr><td class="col-sm-2">'
        commit_table += '<a href="/commit/' + commit_hash + '">'
        commit_table += commit_hash
        commit_table += '</a>'
        commit_table += '</td><td>'
        commit_table += '<a href="/commit/' + commit_hash + '">'
        commit_table += commit_title
        commit_table += '</a>'
        commit_table += '</td></tr>'
    commit_table += '</table>'

#        commits.append((commit_line [0:5], commit_line[7:]))

    #commit_list = '<br>'.join(run_command("git log --oneline".split()))
    git_content = no_git if (not is_git) else commit_table
    return "<h1>Git</h1>" + git_content

def get_dir():
# From http://timgolden.me.uk/python/win32_how_do_i/watch_directory_for_changes.html
    return dict([(f, None) for f in os.listdir(os.getcwd())])


class LongPoll:
    def GET(self, session_id, page_name):
        global last_refresh
        webpy.header('Content-type', 'text/html')
        last_seen = file_mtime(page_name)
        counter = 0
        while last_seen == file_mtime(page_name):
            counter += 1
            if counter >= 10:
                print "stop %s long poll." % page_name
                return ""
            print "%s poll" % page_name
            time.sleep(1)
        return file_data(page_name)

class LongPollIndex:
    def GET(self, session_id):
        global last_refresh
        path = os.getcwd()
        webpy.header('Content-type', 'text/html')
        last_dir = get_dir()
        counter = 0
        while last_dir == get_dir():
            counter += 1
            if counter >= 10:
                print "stop index long poll."
                return ""
            print "index poll"
            time.sleep(1)
        return index_data()

class LongPollGit:
    def GET(self, session_id):
        def get_head():
            return "".join(run_command("git show-ref -s".split())).strip()

        counter = 0
        webpy.header('Content-type', 'text/html')
        last_git = get_head()
        print last_git
        while last_git == get_head():
            # Stop long poll after a while,
            # The window may have been closed meanwhile
            counter += 1
            if counter >= 10:
                print "stop git long poll."
                return ""
            print "git head poll... " + get_head()
            time.sleep(1)
        print "************** new commit: " + get_head()
        return git_data()

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
        #style = open("/home/attis/watchmd.py/bootstrap-readable.css").read()
        longpoll_url = '/longpoll/%d/%s' % (randnum, page_name)
        page = html_live_boiler % (style, data, longpoll_url)
        return page

class Index:
    def GET(self):
        randnum = random.randint(0, 2000000000)
        data = index_data()
        #style = open("/wikimd.py/bootstrap-readable.css").read()
        longpoll_url = '/longpoll-index/%d' % randnum 
        page = html_live_boiler % (style, data, longpoll_url)
        return page

class CommitIndex:
    def GET(self, commit):
        randnum = random.randint(0, 2000000000)
        data = commit_index_data(commit)
        #style = open("/home/attis/watchmd.py/bootstrap-readable.css").read()
        page = html_boiler % (style, data)
        return page

class Git:
    def GET(self):
        no_git = """
<div class="alert alert-danger" role="alert">
  <span class="glyphicon glyphicon-exclamation-sign" aria-hidden="true"></span>
  <span class="sr-only">Error:</span>
  Directory is not a  git repository!
</div>"""
        randnum = random.randint(0, 2000000000)
        #style = open("/home/attis/watchmd.py/bootstrap-readable.css").read()
        longpoll_url = '/longpoll-git/%d' % randnum 
        page = html_live_boiler % (style, git_data(), longpoll_url)
        return page

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print "Usage: wikimd.py <port_num>"
        sys.exit(1)
    webapp = webpy.application(urls, globals())
    webapp.run()


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
from markdown.extensions.wikilinks import WikiLinkExtension
import codecs

count = 0
long_polls = {}
dir = os.path.dirname(os.path.realpath(__file__))
style = open(dir + "/bootstrap-readable.css").read()

urls = (
    '/', 'Index',
    '/wiki/(.*)', 'Frame',
    '/edit/(.*)', 'Edit',
    '/new', 'New',
    '/save/(.*)', 'Save',
    '/save-new', 'SaveNew',
    '/delete/(.*)', 'Delete',
    '/add/(.*)', 'Add',
    '/longpoll/([0-9]+)/(.*)', 'LongPoll',
    '/longpoll-index/([0-9]+)', 'LongPollIndex',
    '/git', 'Git',
    '/git/([0-9a-f]+)', 'CommitIndex',
    '/git/([0-9a-f]+)/(.+)', 'GitFrame',
    '/git-commit', 'GitCommit',
    '/longpoll-git/([0-9]+)', 'LongPollGit',
    '/longpoll-count', 'CountLongPoll',
    '/stop', 'Stop',
    '/jquery.js', 'jQuery'
    )

html_boiler_common = """
<html>
    <head>
        <title>WikiMD</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <script type="text/javascript" src="/jquery.js"></script>
<style>
%(style)s
</style>
    </head>
    <body>
        <input name="stop" type="button" value="Stop" onclick="stop()"></input>
        <a href="/">Index</a>&nbsp;|&nbsp;<a href="/git">Git</a>&nbsp;|&nbsp;<a href="/new">New</a>
        %(toplinks)s
        <div id="closed" style="width: 30em; background-color: aliceblue; border: 1px solid lightblue; margin: 3em auto; padding: 1em; color: blue; text-align: center; display: none">The server is stopped. You may close the window.</div>
        <div class="container">
            <div id="content">
                %(content)s
            </div>
        </div>
    <script type="text/javascript">
        function stop() {
            $.ajax({url: '/stop'});
            $('#stop').hide();
            $('#closed').show(400);
            $('#content').css('color', 'lightgrey');
        }

        %(scripts)s
    </script>
    </body>
</html>
"""

live_script = """
        function getContent() {
            $.ajax({
                url: '%(longpoll_url)s',
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
"""

html_static_boiler = html_boiler_common % {
            "style": "%(style)s", 
            "toplinks": "", 
            "content": "%(content)s", 
            "scripts": "",
        }

html_live_boiler = html_boiler_common % {
            "style": "%(style)s", 
            "toplinks": "", 
            "content": "%(content)s", 
            "scripts": live_script, 
        }

html_editable_live_boiler = html_boiler_common % {
            "style": "%(style)s", 
            "toplinks": '|&nbsp;<a href="/edit/%(page_name)s">Edit</a>&nbsp;|&nbsp;<a href="/delete/%(page_name)s">Delete</a>', 
            "content": "%(content)s", 
            "scripts": live_script, 
        }

html_commitable_live_boiler = html_boiler_common % {
            "style": "%(style)s", 
            "toplinks": '|&nbsp;<a href="/git-commit">Commit</a>', 
            "content": "%(content)s", 
            "scripts": live_script, 
        }

edit_boiler = """
    <h1>Edit %(page_name)s</h1>
    <form action="/save/%(page_name)s" method="post">
        <p><textarea name="edit_text" rows="15" id="edit_text" style="width: 100%%; overflow: hidden; word-wrap: break-word; resize: horizontal;">%(text)s</textarea></p>
        <input type="submit" value="Save"></form>
"""

new_boiler = """
    <h1>New page</h1>
    <form action="/save-new" method="post">
        <p>
            <input name="file_name" type="text" class="form-control" placeholder="Filename"></input>
            <textarea name="edit_text" class="form-control" rows="30" id="edit_text" style="width: 100%%; overflow: hidden; word-wrap: break-word; resize: horizontal;"></textarea>
        </p>
        <input type="submit" value="Save"></form>
"""

delete_boiler = """
    <h1>Delete page</h1>
    <form action="/delete/%s" method="post">
        <div class="checkbox">
            <label><input type="checkbox" name="confirm">Confirm delete</label></div>
        <input type="submit" value="Delete"></form>
"""

error_boiler = """
<div class="alert alert-danger" role="alert">
  <span class="glyphicon glyphicon-exclamation-sign" aria-hidden="true">
  </span>
  <span class="sr-only">Error:</span>
  %s
</div>
"""

commit_boiler = """
    <h1>Commit changes</h1>
    <form action="/git-commit" method="post">
        <p>
            <input name="message" type="text" class="form-control" placeholder="Commit message"></input>
            <textarea name="optional" class="form-control" rows="15" id="edit_text" style="width: 100%%; overflow: hidden; word-wrap: break-word; resize: horizontal;" placeholder="Notes (optional)"></textarea>
        </p>
        <input type="submit" value="Commit"></form>
"""


def register_long_poll(session_id):
    # This cleans up long_poll entries that have not been removed when the
    # long poll finished for some reason (ie. crashed), then adds new.
    now = datetime.datetime.now()
    sessions = long_polls.keys()
    for session in sessions:
        if (now - long_polls[session]).total_seconds() > 60:
            del long_polls[session]
    long_polls[session_id] = datetime.datetime.now()

def unregister_long_poll(session_id):
    del long_polls[session_id]

def is_git():
    return not os.system('git rev-parse')

def run_command(command):
# By Max Persson. http://stackoverflow.com/a/13135985
    p = subprocess.Popen(command,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    return iter(p.stdout.readline, b'')

def run_command_blocking(command):
    try:
        p = subprocess.check_output(command,
                                    stderr=subprocess.STDOUT)
        return p, 0
    except subprocess.CalledProcessError as err:
        return err.output, err.returncode

def file_mtime(file_name):
    try:
        return datetime.datetime.fromtimestamp(os.path.getmtime(file_name))
    except:
        return None

def raw_file_data(file_name):
    with codecs.open(file_name, encoding="utf-8") as f:
        return f.read()

def file_data(file_name):
    try:
        return markdown.markdown(raw_file_data(file_name),
            tab_length=2,
            extensions=[WikiLinkExtension(base_url='/tagline/',
                                          end_url='')])
    except:
        return error_boiler % "File is no longer available."

def git_file_data(commit, file_name):
    git_command = ("git show " + commit + ":" + file_name).split()
    output, git_error = run_command_blocking(git_command)
    return ("<h1>Git error</h1>" + error_boiler % output
               if git_error
               else markdown.markdown(output.decode("utf-8"), tab_length=2))

def title_line(file_name):
    try:
        with open(file_name, 'r') as f:
            title_line = f.readline().strip()
            return title_line if title_line else file_name
    except:
        return file_name

def git_title_line(commit, file_name):
    git_command = ("git show " + commit + ":" + file_name).split()
    file_lines = run_command(git_command)
    return file_lines.next().decode("utf-8")

def index_data():
    def status_icon(fn):
        span = "<span class='%s'></span>"
        span_add = "<a href='/add/%s'><span class='%s'></span></a>"
        if git_status.get(fn) == "d": return span_add % \
            (fn, "glyphicon glyphicon-exclamation-sign")
        if git_status.get(fn) == "s": return span % "glyphicon glyphicon-time" 
        if git_status.get(fn) == "n": return span_add % \
            (fn, "glyphicon glyphicon-question-sign")
        if git_status.get(fn) == "r": return span % "glyphicon glyphicon-trash" 
        if git_status.get(fn) == "c": return span % "glyphicon glyphicon-ok-sign" 
        return ""

    def make_link(fn, deleted):
        link = "<tr><td>%s</td><td>" % status_icon(fn)
        if not deleted:
            link += "<a href='wiki/%s'>%s</a></td></tr>" % (fn, title_line(fn))
        else:
            link += '<span style="color:lightgrey">%s</span>' % fn
        return link

    link_boiler = "<tr><td><span class='%s'></span></td><td><a href='wiki/%s'>%s</a></td></tr>"
    index_boiler = "<h1>Index</h1><table class=\"table\">%s</table>"
    pwd = os.getcwd()
    git = is_git()
    git_status = {}
    links = []
    if git:
        git_cmd_all = "git ls-files".split()
        git_cmd_dirty = "git diff --name-only".split()
        git_cmd_staged = "git diff --name-only --staged".split()
        git_cmd_notrack = "git ls-files -o --exclude-standard".split()
        git_cmd_removed = "git ls-files -d".split()
        try:
            git_all = subprocess.check_output(git_cmd_all).splitlines()
            dirty = subprocess.check_output(git_cmd_dirty).splitlines()
            staged = subprocess.check_output(git_cmd_staged).splitlines()
            clean = [f for f in git_all if f not in (dirty + staged)]
            notrack = subprocess.check_output(git_cmd_notrack).splitlines()
            removed = subprocess.check_output(git_cmd_removed).splitlines()
            for f in clean: git_status[f] = "c"
            for f in staged: git_status[f] = "s"
            for f in dirty: git_status[f] = "d"
            for f in notrack: git_status[f] = "n"
            for f in removed: git_status[f] = "r"
            filelist = git_status.keys()
            links = [make_link(f, f in removed) for f in filelist if f.endswith(".md")]
        except Exception as e: print e
    else:
        filelist = os.listdir(pwd)
        links = [make_link(f, False) for f in filelist if f.endswith(".md")]
    return index_boiler % '\n'.join(links)

def commit_index_data(commit):
    link_boiler = "<tr><td><a href='/git/%s/%s'>%s</a></td></tr>"
    index_boiler = "<h1>Index at %s</h1><table class=\"table\">%s</table>"
    pwd = os.getcwd()
    git_command = ("git ls-tree --name-only -r " + commit).split()
    output, git_error = run_command_blocking(git_command)
    if git_error:
        return "<h1>Git error</h1>" + error_boiler % output
    commit_files = iter(output.splitlines())
    files = [(f, git_title_line(commit, f))
                for f in commit_files
                if f.strip().endswith(".md")]
    print files
    links = [link_boiler % (commit, f[0], f[1]) for f in files]
    return index_boiler % (commit, '\n'.join(links))

def git_data():
    cmd_iter = run_command("git log --oneline".split())
    commit_table = '<table class="table">'
    for commit_line in cmd_iter:
        commit_hash = commit_line[0:6]
        commit_title = commit_line[7:]
        commit_table += '<tr><td class="col-sm-2">'
        commit_table += '<a href="/git/' + commit_hash + '">'
        commit_table += commit_hash
        commit_table += '</a>'
        commit_table += '</td><td>'
        commit_table += '<a href="/git/' + commit_hash + '">'
        commit_table += commit_title
        commit_table += '</a>'
        commit_table += '</td></tr>'
    commit_table += '</table>'

    no_git = error_boiler % "Directory is not a git repository!"
    git_content = no_git if (not is_git()) else commit_table
    return "<h1>Git</h1>" + git_content

def get_dir():
    # From http://timgolden.me.uk/python/win32_how_do_i/watch_directory_for_changes.html
    #return dict([(f, None) for f in os.listdir(os.getcwd())])
    r = subprocess.check_output("ls -la --time-style=+%s", shell=True)
    return r

class LongPoll:
    def GET(self, session_id, page_name):
        global last_refresh
        register_long_poll(session_id)
        webpy.header('Content-type', 'text/html')
        last_seen = file_mtime(page_name)
        counter = 0
        while last_seen == file_mtime(page_name):
            counter += 1
            if counter >= 10:
                print "stop %s long poll." % page_name
                unregister_long_poll(session_id)
                return ""
            print "%s poll" % page_name
            time.sleep(1)
        unregister_long_poll(session_id)
        return file_data(page_name)

class LongPollIndex:
    def GET(self, session_id):
        global last_refresh
        register_long_poll(session_id)
        path = os.getcwd()
        webpy.header('Content-type', 'text/html')
        last_dir = get_dir()
        counter = 0
        while last_dir == get_dir():
            counter += 1
            if counter >= 10:
                print "stop index long poll."
                unregister_long_poll(session_id)
                return ""
            print "index poll"
            time.sleep(1)
        unregister_long_poll(session_id)
        return index_data()

class LongPollGit:
    def GET(self, session_id):
        def get_head():
            return "".join(run_command("git show-ref -s".split())).strip()

        register_long_poll(session_id)
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
                unregister_long_poll(session_id)
                return ""
            print "git head poll... " + get_head()
            time.sleep(1)
        print "************** new commit: " + get_head()
        unregister_long_poll(session_id)
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
        print page_name
        data = file_data(page_name)
        longpoll_url = '/longpoll/%d/%s' % (randnum, page_name)
        page = html_editable_live_boiler % {
                "style": style,
                "content": data,
                "longpoll_url": longpoll_url,
                "page_name": page_name,
            }
        return page

class GitFrame:
    def GET(self, commit, page_name):
        data = git_file_data(commit, page_name)
        page = html_static_boiler % {"style": style, "content": data}
        return page

class Index:
    def GET(self):
        randnum = random.randint(0, 2000000000)
        longpoll_url = '/longpoll-index/%d' % randnum 
        page = html_commitable_live_boiler % {
                "style": style,
                "content": index_data(),
                "longpoll_url": longpoll_url,
            }
        return page

class CommitIndex:
    def GET(self, commit):
        data = commit_index_data(commit)
        page = html_static_boiler % {"style": style, "content": data}
        return page

class Git:
    def GET(self):
        randnum = random.randint(0, 2000000000)
        longpoll_url = '/longpoll-git/%d' % randnum 
        page = html_live_boiler % {
                "style": style,
                "content": git_data(),
                "longpoll_url": longpoll_url,
            }
        return page

class Edit:
    def GET(self, page_name):
        content = edit_boiler % {
                "page_name": page_name,
                "text": raw_file_data(page_name),
            }
        page = html_static_boiler % {"style": style, "content": content}
        return page

class New:
    def GET(self):
        content = new_boiler
        page = html_static_boiler % {"style": style, "content": content}
        return page

class Save:
    def POST(self, page_name):
        post_data = webpy.input()
        with open(page_name, "w") as page_file:
            page_file.write(post_data.edit_text.encode('utf-8'))
        raise webpy.seeother('/wiki/%s' % page_name)

class SaveNew:
    def POST(self):
        post_data = webpy.input()
        page_name = post_data.file_name.strip() + ".md"
        print "creating new file %s" % page_name
        with open(page_name, "w") as page_file:
            page_file.write(post_data.edit_text.encode('utf-8'))
        raise webpy.seeother('/wiki/%s' % page_name)

class Delete:
    def GET(self, page_name):
        content = delete_boiler % page_name
        page = html_static_boiler % {"style": style, "content": content}
        return page

    def POST(self, page_name):
        if webpy.input().get("confirm", "") == "on":
            if page_name.endswith(".md"):
                os.remove(page_name)
            if is_git:
                git_command = ("git rm " + page_name).split()
                output, git_error = run_command_blocking(git_command)
            print "DELETED %s" % page_name
            raise webpy.seeother('/')
        raise webpy.seeother('/wiki/%s' % page_name)

class Add:
    def GET(self, page_name):
        git_command = ("git add " + page_name).split()
        output, git_error = run_command_blocking(git_command)
        if git_error: return "error"
        raise webpy.seeother('/')

class GitCommit:
    def GET(self):
        page = html_static_boiler % {"style": style, "content": commit_boiler}
        return page

    def POST(self):
        msg = webpy.input().get("message", "")
        opt = webpy.input().get("optional", "")
        git_command = "git commit -m".split()
        git_command.append(msg + "\n\n" + opt)
        output, git_error = run_command_blocking(git_command)
        if git_error:
            content = error_boiler % output.replace("\n", "<br>") + commit_boiler
            page = html_static_boiler % {"style": style, "content": content}
            return page
        raise webpy.seeother('/git')

class CountLongPoll:
    def GET(self):
        return len(long_polls)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print "Usage: wikimd.py <port_num>"
        sys.exit(1)
    webapp = webpy.application(urls, globals())
    webapp.run()


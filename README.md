wikimd.py -- instant Markdown wiki server
=========================================

Purpose
-------

Tracks and displays a live rendering of a set of Markdown text files
in a web browser. It can be used as a kind of wiki-like service backed by
filesystem. Usable `git` integration is also planned.

Serves files in the current working directory.

Usage
-----

    $ python wikimd.py <port>

Notes
-----

Required Python packages:

* web.py
* markdown

Uses the long poll variant of HTTP Push to implement live refresh of
content when the source file changes.

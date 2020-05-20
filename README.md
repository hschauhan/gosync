                                      GOSYNC

GoSync is an open source Google Drive client for Linux written in python language.
It's not perfect yet but it does the job. GoSync is released under GNU GPL version 2.0.

What it does?
=============
It syncs everything from the Google Drive. By default, the sync is turned on. You can pause
it by clicking "Pause/Resume Sync" menu item. GoSync also monitors for the file changes
in the local mirror directory. When a new file is created in local mirror, it is
immediately uploaded to the Google Drive.

GoSync does the sync every 10 minutes. It is not configurable right now. This is called
as "regular sync".

There are some limitations as of now:
1. You cannot choose which directories to sync. It just syncs everything.
2. While its calculating the drive usage, the progress is not shown. If the usage of drive is high, it takes time to calculate the total categorical usage.

This will be fixed in future versions.

Installation
============
Starting from version 0.3, GoSync is available for installation via pip (including all dependencies). Simply run:

pip install GoSync

If you want to: 

1. install the latest source from GitHub
1. enable Google Drive API

please use the following procedure :

https://github.com/arentoine/gosync/wiki

Requests
========
Please help in improving this project. You can send me patches at hschauhan at nulltrace dot org. If you
can't write the code and you find something more or something non-functional, please create a bug on github
page. I will see if I can fix that as soon as possible. Since I work on this project in my free time, I
can't tell when exactly I will be able to honor your request. But rest assured I will.

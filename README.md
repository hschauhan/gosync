                                      GOSYNC

GoSync is an open source Google Drive client for Linux written in python language.
It's not perfect yet but it does the job. GoSync is released under GNU GPL version 2.0.

What it does?
-------------
It can sync everything from the root folder. By default, the sync is not turned on.
You have to enable it by clicking "Start background sync" menu item. Currently,
it only syncs everything from server. GoSync monitors for the file changes in the
local sync directory. When a new file is created, it is immediately uploaded to the
Google Drive.

What it doesn't do?
-------------------
While eventually GoSYnc will do everything that other clients do on the other operating
systems, there are some limitations to it right now:

    1. During the sync, it only downloads the files from the server. Any preexisting files
       in the sync directory are not uploaded.
    2. File modification, delete or move are not supported yet.

This will be fixed in future versions.

What you need to make it work?
------------------------------
Until finally there is an egg for GoSync, the dependencies are to installed manually. GoSync
doesn't really depend on many libraries. You need to install the following libraries before
using GoSync:

    1. python (version >= 2.7. Version 3 not tested yet)
    2. wxPythong (version >= 2.8) 
    3. python-googleapi 
    4. pip 
    5. watchdog (to be installed from pip)

GoSync also depends on PyDrive but right now its keeping its own version in the source code.
I have an specific change about getting details of drive like user currently logged in and
total drive usage and quota. I haven't submitted these changes to original PyDrive yet. Once
they are there, I will remove this pydrive code from GoSync source.

You can read more about pydrive at http://pythonhosted.org/PyDrive/

For libraries you need only that many. But there is one more essential thing. The "client_secrets.json"
file. I am not distributing my "client_secrets.json" because I am not distributing GoSync commercially.
A very good get started page can be found at https://developers.google.com/drive/web/quickstart/python.
When you are done creating the .json file, download it and keep it inside GoSync directory as
".client_secrets.json". Please note the "." before the name.

After all this you should get it working. In case you have some problem you can send me mail at
hschauhan at nulltrace dot org or hs dot chauhan at gmail dot com.

Where to get the code?
----------------------
The code is being maintained as a github project. You can either clone the project from github or you
can download the zip file. The following is the github page for GoSync:

https://github.com/hschauhan/gosync

A Request
---------
Please help in improving this project. You can send me patches at hschauhan at nulltrace dot org. If you can't write the code and you find something more or something non-functional, please create a bug on github page. I will see if I can fix that as soon as possible.
Since I work on this project in my free time, I can't tell when exactly I will be able to honor your request. But rest assured I will.

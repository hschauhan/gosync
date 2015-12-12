#!/usr/bin/python
# gosync is an open source google drive sync application for Linux
#
# Copyright (C) 2015 Himanshu Chauhan
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import sys, os, wx, GoSyncController, GoSyncModel
from os.path import expanduser, dirname, relpath
from GoSyncController import GoSyncController
from defines import *

# Add the current path to gosync path.
sys.path.insert(0, APP_PATH)

def main():
    os.chdir(APP_PATH)
    app = wx.PySimpleApp()
    controller = GoSyncController()
    controller.Center()
    controller.Show()
    app.MainLoop()

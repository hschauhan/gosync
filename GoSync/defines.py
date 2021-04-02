# gosync is an open source Google Drive(TM) sync application for Linux
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

import os,sys

APP_LICENSE = """GoSync is an open source Google Drive(TM) client written in python

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""
APP_DEVELOPER = 'Himanshu Chauhan, Alain Robillard'
ART_DEVELOPER = 'Himanshu Chauhan'
APP_DEVELOPER_EMAIL = 'hschauhan@nulltrace.org, arentoine@gmail.com'
APP_WEBSITE = 'http://www.nulltrace.org/p/gosync.html'
APP_COPYRIGHT = '(c) 2015 - 2022 Himanshu Chauhan, Alain Robillard'
APP_DESCRIPTION = 'GoSync is an open source Google Drive client written in python.'
APP_CONFIG_FILE_NAME = 'gosyncrc'
CLIENT_SECRET_HELP_SITE='https://github.com/arentoine/gosync/wiki'
APP_PATH = os.path.abspath(os.path.dirname(os.path.join(sys.argv[0])))
HERE=os.path.abspath(os.path.dirname(__file__))
INI_FILE = os.path.join(APP_PATH, "gosync.ini")

TRAY_TOOLTIP = 'GoSync - A Google Drive Client for Linux'
TRAY_ICON = HERE + '/resources/GoSyncIcon.png'
APP_ICON = HERE + '/resources/GoSyncIcon-64.png'
ABOUT_ICON = HERE + '/resources/GoSyncIcon-64.png'
APP_NAME = 'GoSync'
APP_VERSION = '0.53'

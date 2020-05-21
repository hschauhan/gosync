# gosync is an open source Google Drive(TM) sync application for Linux
# modify it under the terms of the GNU General Public License
#
# Copyright (C) 2015 Himanshu Chauhan
# This program is free software; you can redistribute it and/or
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
#

import threading

class AtomicVariable(object):
    def __init__(self, initial):
        self._value = initial
        self._lock = threading.Lock()

    def get_value(self):
        with self._lock:
            return self._value

    def set_value(self, new):
        with self._lock:
            self._value = new

    value = property(get_value, set_value)

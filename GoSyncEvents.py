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

import os, wx

GOSYNC_EVENT_CALCULATE_USAGE_STARTED = '_gosync_calculate_usage_started'
GOSYNC_EVENT_CALCULATE_USAGE_UPDATE = '_gosync_calculate_usage_update'
GOSYNC_EVENT_CALCULATE_USAGE_DONE = '_gosync_calculate_usage_done'
GOSYNC_EVENT_SYNC_STARTED = '_gosync_sync_started'
GOSYNC_EVENT_SYNC_UPDATE = '_gosync_sync_update'
GOSYNC_EVENT_SYNC_DONE = '_gosync_sync_done'
GOSYNC_EVENT_SYNC_TIMER = '_gosync_sync_timer'

GOSYNC_EVENT_ID_SYNC_STARTED = wx.NewId()
GOSYNC_EVENT_ID_SYNC_UPDATE = wx.NewId()
GOSYNC_EVENT_ID_SYNC_DONE = wx.NewId()
GOSYNC_EVENT_ID_CALCULATE_USAGE_STARTED = wx.NewId()
GOSYNC_EVENT_ID_CALCULATE_USAGE_UPDATE = wx.NewId()
GOSYNC_EVENT_ID_CALCULATE_USAGE_DONE = wx.NewId()
GOSYNC_EVENT_ID_SYNC_TIMER = wx.NewId()

class GoSyncEvent(wx.PyEvent):
    def __init__(self, event, data):
        wx.PyEvent.__init__(self)

        self.SetEventType(event)
        self.data = data

# A singleton class for event passing between
# different modules of GoSync
class GoSyncEventController(object):
    _event_controller_instance = None
    _sync_events = {GOSYNC_EVENT_SYNC_STARTED: GOSYNC_EVENT_ID_SYNC_STARTED,
                    GOSYNC_EVENT_SYNC_UPDATE: GOSYNC_EVENT_ID_SYNC_UPDATE,
                    GOSYNC_EVENT_SYNC_DONE: GOSYNC_EVENT_ID_SYNC_DONE,
                    GOSYNC_EVENT_CALCULATE_USAGE_STARTED: GOSYNC_EVENT_ID_CALCULATE_USAGE_STARTED,
                    GOSYNC_EVENT_CALCULATE_USAGE_UPDATE: GOSYNC_EVENT_ID_CALCULATE_USAGE_UPDATE,
                    GOSYNC_EVENT_CALCULATE_USAGE_DONE: GOSYNC_EVENT_ID_CALCULATE_USAGE_DONE,
                    GOSYNC_EVENT_SYNC_TIMER: GOSYNC_EVENT_ID_SYNC_TIMER}
    _sync_listeners = {GOSYNC_EVENT_SYNC_STARTED:[],
                       GOSYNC_EVENT_SYNC_UPDATE: [],
                       GOSYNC_EVENT_SYNC_DONE: [],
                       GOSYNC_EVENT_CALCULATE_USAGE_STARTED: [],
                       GOSYNC_EVENT_CALCULATE_USAGE_UPDATE: [],
                       GOSYNC_EVENT_CALCULATE_USAGE_DONE: [],
                       GOSYNC_EVENT_SYNC_TIMER: []}

    def __new__(cls, *args, **kwargs):
        if not cls._event_controller_instance:
            cls._event_controller_instance = \
                super(GoSyncEventController, cls).__new__(cls, *args, **kwargs)

        return cls._event_controller_instance

    def PostEvent(self, event, data):
        if self._sync_listeners[event] and \
                self._sync_listeners[event]:
            for listener in self._sync_listeners[event]:
                wx.PostEvent(listener, GoSyncEvent(self._sync_events[event], data))

    def BindEvent(self, notify_object, event, func):
        if not notify_object:
            raise ValueError("Invalid notify object")
    
        if not self._sync_events[event]:
            raise ValueError("Invalid event")

        notify_object.Connect(-1, -1, self._sync_events[event], func)
        self._sync_listeners[event].append(notify_object)

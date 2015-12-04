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

import sys, os, wx, ntpath, defines, threading, math
from GoSyncModel import GoSyncModel
#from defines import TRAY_ICON, TRAY_TOOLTIP, APP_NAME, APP_VERSION, APP_DESCRIPTION
from defines import *
from threading import Timer
from GoSyncPreferences import GoSyncPreferenceDialog

class GoSyncController(wx.TaskBarIcon):
    def __init__(self):
        super(GoSyncController, self).__init__()
        self.SetIcon(wx.IconFromBitmap(wx.Bitmap(TRAY_ICON)), TRAY_TOOLTIP)
        self.Bind(wx.EVT_TASKBAR_LEFT_DOWN, self.OnLeftDown)
        try:
            self.sync_model = GoSyncModel()
        except:
            dial = wx.MessageDialog(None, 'GoSync failed to initialize\n',
                                    'Error', wx.ID_OK | wx.ICON_EXCLAMATION)
            res = dial.ShowModal()
            sys.exit(1)

    def CreateMenuItem(self, menu, label, func, icon=None):
        item = wx.MenuItem(menu, -1, label)
        if icon:
            item.SetBitmap(wx.Bitmap(icon))
        menu.Bind(wx.EVT_MENU, func, id=item.GetId())
        menu.AppendItem(item)
        return item

    def CreatePopupMenu(self):
        menu = wx.Menu()
        aboutdrive = self.sync_model.DriveInfo()
        driveTotalSpace = float(aboutdrive['quotaBytesTotal'])
        driveUsedSpace = float(aboutdrive['quotaBytesUsed'])
        usage_string = "%s/%s" % (self.FileSizeHumanize(driveUsedSpace), self.FileSizeHumanize(driveTotalSpace))
        self.CreateMenuItem(menu, aboutdrive['name'], self.OnLeftDown, 'resources/user.png')
        self.CreateMenuItem(menu, usage_string, self.OnLeftDown, 'resources/usage.png')

        if self.sync_model.IsSyncEnabled():
            self.CreateMenuItem(menu, '&Stop Background Sync', self.OnStopSync, 'resources/sync-menu.png')
        else:
            self.CreateMenuItem(menu, '&Start Background Sync', self.OnSyncNow, 'resources/sync-menu.png')
        menu.AppendSeparator()
        self.CreateMenuItem(menu, 'S&ettings', self.OnPreferences, 'resources/settings.png')
        self.CreateMenuItem(menu, 'A&bout', self.OnAbout, 'resources/info.png')
        self.CreateMenuItem(menu, 'E&xit', self.OnExit, 'resources/exit.png')
        return menu

    def FileSizeHumanize(self, size):
        size = abs(size)
        if (size==0):
            return "0B"
        units = ['B','KiB','MiB','GiB','TiB','PiB','EiB','ZiB','YiB']
        p = math.floor(math.log(size, 2)/10)
        return "%.3f%s" % (size/math.pow(1024,p),units[int(p)])

    def OnPreferences(self, event):
        prefPane = GoSyncPreferenceDialog()
        prefPane.ShowModal()
        prefPane.Destroy()

    def OnLeftDown(self, event):
        return

    def OnExit(self, event):
        dial = wx.MessageDialog(None, 'GoSync will stop syncing files until restarted.\nAre you sure to quit?\n',
                                'Question', wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        res = dial.ShowModal()
        if res == wx.ID_YES:
            wx.CallAfter(self.Destroy)

    def OnSyncNow(self, evt):
        self.sync_model.StartSync()

    def OnStopSync(self, evt):
        """Stop syncing with google drive"""
        self.sync_model.StopSync()

    def OnAbout(self, evt):
        """About GoSync"""
        about = wx.AboutDialogInfo()
        about.SetIcon(wx.Icon(TRAY_ICON, wx.BITMAP_TYPE_PNG))
        about.SetName(APP_NAME)
        about.SetVersion(APP_VERSION)
        about.SetDescription(APP_DESCRIPTION)
        about.SetCopyright(APP_COPYRIGHT)
        about.SetWebSite(APP_WEBSITE)
        about.SetLicense(APP_LICENSE)
        about.AddDeveloper(APP_DEVELOPER)
        wx.AboutBox(about)

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

import wx, os
import sys, os, wx, ntpath, defines, threading, math
from GoSyncModel import GoSyncModel
from defines import *
from threading import Timer
from DriveUsageBox import DriveUsageBox

mainWindowStyle = wx.DEFAULT_FRAME_STYLE & (~wx.CLOSE_BOX) & (~wx.MAXIMIZE_BOX)

class PageAccountSettings(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)

        font = wx.Font(11, wx.SWISS, wx.NORMAL, wx.NORMAL)
        headerFont = wx.Font(11.5, wx.SWISS, wx.NORMAL, wx.BOLD)

        accountText = wx.StaticText(self, wx.ID_ANY, "Account", pos=(0,0))
        accountText.SetFont(headerFont)

        container_panel = wx.Panel(self, -1, style=wx.SUNKEN_BORDER, pos=(5,1), size=(685, 150))

        self.driveUsageBar = DriveUsageBox(container_panel, 16106127360, -1, bar_position=(50,90))
        self.driveUsageBar.SetMoviesUsage(25)
        self.driveUsageBar.SetDocumentUsage(25)
        self.driveUsageBar.SetOthersUsage(25)
        self.driveUsageBar.SetAudioUsage(0)
        self.driveUsageBar.RePaint()

        settings_panel = wx.Panel(self, -1, style=wx.SUNKEN_BORDER, pos=(5, 100), size=(600, 500))
        syncOptionsText = wx.StaticText(self, wx.ID_ANY, "Sync Options", pos=(0, 100))
        syncOptionsText.SetFont(headerFont)
        localSyncDirLabel = wx.StaticText(settings_panel, wx.ID_ANY, "Local Folder:")
        self.userHome = "%s/gosync" % os.getenv("HOME")
        self.localSyncDirText = wx.TextCtrl(settings_panel, wx.ID_ANY, self.userHome)
        localSyncDirLabel.SetFont(font)
        self.localSyncDirBrowseBtn = wx.Button(settings_panel, wx.ID_ANY, 'Browse')
        self.localSyncDirBrowseBtn.Bind(wx.EVT_BUTTON, self.onLocalBrowse)

        serverSyncDirLabel = wx.StaticText(settings_panel, wx.ID_ANY, "Server Folder(s):")
        self.serverSyncDirText = wx.TextCtrl(settings_panel, wx.ID_ANY, 'root')
        serverSyncDirLabel.SetFont(font)
        self.serverSyncDirBrowseBtn = wx.Button(settings_panel, wx.ID_ANY, 'Browse')
        #self.serverSyncDirBrowseBtn.Bind(wx.EVT_BUTTON, self.onServerBrowse)

        mainsizer = wx.BoxSizer(wx.VERTICAL)

        prefSizer = wx.FlexGridSizer(cols=3, hgap=5, vgap=10)
        prefSizer.AddGrowableCol(1)

        prefSizer.Add(localSyncDirLabel, 0, wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
        prefSizer.Add(self.localSyncDirText, 0, wx.EXPAND)
        prefSizer.Add(self.localSyncDirBrowseBtn, 0)

        prefSizer.Add(serverSyncDirLabel, 0, wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
        prefSizer.Add(self.serverSyncDirText, 0, wx.EXPAND)
        prefSizer.Add(self.serverSyncDirBrowseBtn, 0)

        mainsizer.Add(accountText, 0, wx.ALL|wx.EXPAND, 5)
        mainsizer.Add(container_panel, 0, wx.ALL|wx.EXPAND, 5)
        mainsizer.Add(syncOptionsText, 0, wx.ALL|wx.EXPAND, 5)
        settings_panel.SetSizerAndFit(prefSizer)
        mainsizer.Add(settings_panel, 0, wx.ALL|wx.EXPAND, 5)
        self.SetSizerAndFit(mainsizer)

    def onLocalBrowse(self, event):
        browseDialog = wx.DirDialog(None, "Choose a directory:",
                                    style = wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        if browseDialog.ShowModal() == wx.ID_OK:
            self.localSyncDirText.SetValue(browseDialog.GetPath())
        browseDialog.Destroy()

class GoSyncController(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, None, title="GoSync", size=(700,700), style=mainWindowStyle)

        try:
            self.sync_model = GoSyncModel()
        except:
            dial = wx.MessageDialog(None, 'GoSync failed to initialize\n',
                                    'Error', wx.ID_OK | wx.ICON_EXCLAMATION)
            res = dial.ShowModal()
            sys.exit(1)

        self.aboutdrive = self.sync_model.DriveInfo()

        title_string = "GoSync -- Logged In as %s" % self.aboutdrive['name']
        self.SetTitle(title_string)
        appIcon = wx.Icon(APP_ICON, wx.BITMAP_TYPE_PNG)
        self.SetIcon(appIcon)
        menuBar = wx.MenuBar()
        menu = wx.Menu()

        if self.sync_model.IsSyncEnabled():
            self.CreateMenuItem(menu, '&Stop Background Sync', self.OnStopSync, 'resources/sync-menu.png')
        else:
            self.CreateMenuItem(menu, '&Start Background Sync', self.OnSyncNow, 'resources/sync-menu.png')
        menu.AppendSeparator()
        self.CreateMenuItem(menu, 'A&bout', self.OnAbout, 'resources/info.png')
        self.CreateMenuItem(menu, 'E&xit', self.OnExit, 'resources/exit.png')

        menuBar.Append(menu, '&File')

        self.SetMenuBar(menuBar)

        # Here we create a panel and a notebook on the panel
        p = wx.Panel(self)
        nb = wx.Notebook(p)

        # create the page windows as children of the notebook
        accountSettingsPage = PageAccountSettings(nb)

        # add the pages to the notebook with the label to show on the tab
        nb.AddPage(accountSettingsPage, "Account && Options")

        # finally, put the notebook in a sizer for the panel to manage
        # the layout
        sizer = wx.BoxSizer()
        sizer.Add(nb, 1, wx.EXPAND)
        p.SetSizer(sizer)

    def CreateMenuItem(self, menu, label, func, icon=None):
        item = wx.MenuItem(menu, -1, label)
        if icon:
            item.SetBitmap(wx.Bitmap(icon))
        self.Bind(wx.EVT_MENU, func, id=item.GetId())
        menu.AppendItem(item)
        return item

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
        print "about dialog box"
        about = wx.AboutDialogInfo()
        about.SetIcon(wx.Icon(ABOUT_ICON, wx.BITMAP_TYPE_PNG))
        about.SetName(APP_NAME)
        about.SetVersion(APP_VERSION)
        about.SetDescription(APP_DESCRIPTION)
        about.SetCopyright(APP_COPYRIGHT)
        about.SetWebSite(APP_WEBSITE)
        about.SetLicense(APP_LICENSE)
        about.AddDeveloper(APP_DEVELOPER)
        about.AddArtist(APP_DEVELOPER)
        wx.AboutBox(about)

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

import wx, os, time
import sys, os, wx, ntpath, defines, threading, math, webbrowser
from GoSyncModel import GoSyncModel, ClientSecretsNotFound
from defines import *
from threading import Timer
from DriveUsageBox import DriveUsageBox
from GoSyncEvents import *

ID_SYNC_TOGGLE = wx.NewId()

mainWindowStyle = wx.DEFAULT_FRAME_STYLE & (~wx.CLOSE_BOX) & (~wx.MAXIMIZE_BOX)
HERE=os.path.abspath(os.path.dirname(__file__))

class PageAccountSettings(wx.Panel):
    def __init__(self, parent, sync_model):
        wx.Panel.__init__(self, parent)

        self.sync_model = sync_model

        aboutdrive = sync_model.DriveInfo()

        font = wx.Font(11, wx.SWISS, wx.NORMAL, wx.NORMAL)
        headerFont = wx.Font(11.5, wx.SWISS, wx.NORMAL, wx.BOLD)

        #accountText = wx.StaticText(self, wx.ID_ANY, "Account", pos=(0,0))
        #accountText.SetFont(headerFont)

        container_panel = wx.Panel(self, -1, style=wx.SUNKEN_BORDER, pos=(5,1), size=(685, 155))

        self.driveUsageBar = DriveUsageBox(container_panel, long(aboutdrive['quotaBytesTotal']),
                                           -1, bar_position=(50,90))
        self.driveUsageBar.SetStatusMessage("Calculating your categorical Google Drive usage. Please wait.")
        self.driveUsageBar.SetMoviesUsage(0)
        self.driveUsageBar.SetDocumentUsage(0)
        self.driveUsageBar.SetOthersUsage(0)
        self.driveUsageBar.SetAudioUsage(0)
        self.driveUsageBar.SetPhotoUsage(0)
        self.driveUsageBar.RePaint()


        mainsizer = wx.BoxSizer(wx.VERTICAL)

        #mainsizer.Add(accountText, 0, wx.ALL|wx.EXPAND, 5)
        mainsizer.Add(container_panel, 0, wx.ALL|wx.EXPAND, 5)
        self.SetSizerAndFit(mainsizer)

        #self.updateTimer = wx.Timer(self)
        #self.Bind(wx.EVT_TIMER, self.UpdateUsageBar, self.updateTimer)

        GoSyncEventController().BindEvent(self, GOSYNC_EVENT_CALCULATE_USAGE_STARTED,
                                          self.OnUsageCalculationStarted)
        #GoSyncEventController().BindEvent(self, GOSYNC_EVENT_CALCULATE_USAGE_UPDATE,
        #                                  self.UpdateUsageBar)
        GoSyncEventController().BindEvent(self, GOSYNC_EVENT_CALCULATE_USAGE_DONE,
                                          self.OnUsageCalculationDone)

        #self.updateTimer.Start(10000, False)

    def OnUsageCalculationDone(self, event):
        if not event.data:
            self.driveUsageBar.SetStatusMessage("Your Google Drive usage is shown below:")
            self.driveUsageBar.SetMoviesUsage(self.sync_model.GetMovieUsage())
            self.driveUsageBar.SetDocumentUsage(self.sync_model.GetDocumentUsage())
            self.driveUsageBar.SetOthersUsage(self.sync_model.GetOthersUsage())
            self.driveUsageBar.SetAudioUsage(self.sync_model.GetAudioUsage())
            self.driveUsageBar.SetPhotoUsage(self.sync_model.GetPhotoUsage())
            self.driveUsageBar.RePaint()
        else:
            self.driveUsageBar.SetStatusMessage("Sorry, could not calculate your Google Drive usage.")

    def OnUsageCalculationStarted(self, event):
        self.driveUsageBar.SetStatusMessage("Calculating your categorical Google Drive usage. Please wait")

class GoSyncController(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, None, title="GoSync", size=(520,300), style=mainWindowStyle)

        try:
            self.sync_model = GoSyncModel()
        except ClientSecretsNotFound:
            dial = wx.MessageDialog(None, 'Client secret file was not found!\n\nDo you want to know how to create one?\n',
                                    'Error', wx.YES_NO | wx.ICON_EXCLAMATION)
            res = dial.ShowModal()

            if res == wx.ID_YES:
                webbrowser.open(CLIENT_SECRET_HELP_SITE, new=1, autoraise=True)

            sys.exit(1)
        except:
            dial = wx.MessageDialog(None, 'GoSync failed to initialize\n',
                                    'Error', wx.ID_OK | wx.ICON_EXCLAMATION)
            res = dial.ShowModal()
            sys.exit(1)

        self.aboutdrive = self.sync_model.DriveInfo()

        title_string = "GoSync --%s (%s used of %s)" % (self.aboutdrive['name'],
                                                        self.FileSizeHumanize(long(self.aboutdrive['quotaBytesUsed'])),
                                                        self.FileSizeHumanize(long(self.aboutdrive['quotaBytesTotal'])))
        self.SetTitle(title_string)
        appIcon = wx.Icon(APP_ICON, wx.BITMAP_TYPE_PNG)
        self.SetIcon(appIcon)
        menuBar = wx.MenuBar()
        menu = wx.Menu()

        if self.sync_model.IsSyncEnabled():
            menu_txt = 'Pause Sync'
        else:
            menu_txt = 'Resume Sync'
        self.CreateMenuItem(menu, menu_txt, self.OnToggleSync, icon=os.path.join(HERE, 'resources/sync-menu.png'), id=ID_SYNC_TOGGLE)
        self.Bind(wx.EVT_UPDATE_UI, self.OnSyncUIUpdate, id=ID_SYNC_TOGGLE)

        menu.AppendSeparator()
        self.CreateMenuItem(menu, 'A&bout', self.OnAbout, os.path.join(HERE, 'resources/info.png'))
        self.CreateMenuItem(menu, 'E&xit', self.OnExit, os.path.join(HERE, 'resources/exit.png'))

        menuBar.Append(menu, '&File')

        self.SetMenuBar(menuBar)

        # Here we create a panel and a notebook on the panel
        p = wx.Panel(self)
        nb = wx.Notebook(p)

        # create the page windows as children of the notebook
        accountSettingsPage = PageAccountSettings(nb, self.sync_model)

        # add the pages to the notebook with the label to show on the tab
        nb.AddPage(accountSettingsPage, "Account")

        # finally, put the notebook in a sizer for the panel to manage
        # the layout
        sizer = wx.BoxSizer()
        sizer.Add(nb, 1, wx.EXPAND)
        p.SetSizer(sizer)

        self.sb = self.CreateStatusBar()

        GoSyncEventController().BindEvent(self, GOSYNC_EVENT_SYNC_STARTED,
                                          self.OnSyncStarted)
        GoSyncEventController().BindEvent(self, GOSYNC_EVENT_SYNC_UPDATE,
                                          self.OnSyncUpdate)
        GoSyncEventController().BindEvent(self, GOSYNC_EVENT_SYNC_DONE,
                                          self.OnSyncDone)
        GoSyncEventController().BindEvent(self, GOSYNC_EVENT_SYNC_TIMER,
                                          self.OnSyncTimer)

        self.sync_model.SetTheBallRolling()

    def OnSyncTimer(self, event):
        unicode_string = event.data.pop()
        self.sb.SetStatusText(unicode_string.encode('ascii', 'ignore'))

    def OnSyncStarted(self, event):
        self.sb.SetStatusText("Sync started...")

    def OnSyncUpdate(self, event):
        unicode_string = event.data.pop()
        self.sb.SetStatusText(unicode_string.encode('ascii', 'ignore'))

    def OnSyncDone(self, event):
        if not event.data:
            self.sb.SetStatusText("Sync completed.")
        else:
            self.sb.SetStatusText("Sync failed. Please check the logs.")

    def CreateMenuItem(self, menu, label, func, icon=None, id=None):
        if id:
            item = wx.MenuItem(menu, id, label)
        else:
            item = wx.MenuItem(menu, -1, label)

        if icon:
            item.SetBitmap(wx.Bitmap(icon))

        if id:
            self.Bind(wx.EVT_MENU, func, id=id)
        else:
            self.Bind(wx.EVT_MENU, func, id=item.GetId())

        menu.AppendItem(item)
        return item

    def OnSyncUIUpdate(self, event):
        if self.sync_model.IsSyncEnabled():
            event.SetText('Pause Sync')
        else:
            event.SetText('Resume Sync')

    def FileSizeHumanize(self, size):
        size = abs(size)
        if (size==0):
            return "0B"
        units = ['B','KB','MB','GB','TB','PB','EB','ZB','YB']
        p = math.floor(math.log(size, 2)/10)
        return "%.3f%s" % (size/math.pow(1024,p),units[int(p)])

    def OnExit(self, event):
        dial = wx.MessageDialog(None, 'GoSync will stop syncing files until restarted.\nAre you sure to quit?\n',
                                'Question', wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        res = dial.ShowModal()
        if res == wx.ID_YES:
            wx.CallAfter(self.Destroy)

    def OnToggleSync(self, evt):
        if self.sync_model.IsSyncEnabled():
            self.sync_model.StopSync()
        else:
            self.sync_model.StartSync()

    def OnAbout(self, evt):
        """About GoSync"""
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

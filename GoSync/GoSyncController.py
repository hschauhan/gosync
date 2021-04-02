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
import sys
if sys.version_info > (3,):
    long = int
try :
	import wx.adv
	wxgtk4 = True
except (ImportError, ValueError):
	wxgtk4 = False
import sys, os, wx, ntpath, threading, math, webbrowser
from threading import Timer
try :
	from .GoSyncModel import GoSyncModel, ClientSecretsNotFound, InternetNotReachable
	from .defines import *
	from .DriveUsageBox import DriveUsageBox
	from .GoSyncEvents import *
	from .GoSyncSelectionPage import SelectionPage
	from .GoSyncSettingPage import SettingsPage
except (ImportError, ValueError):
	from GoSyncModel import GoSyncModel, ClientSecretsNotFound, InternetNotReachable
	from defines import *
	from DriveUsageBox import DriveUsageBox
	from GoSyncEvents import *
	from GoSyncSelectionPage import SelectionPage
	from GoSyncSettingPage import SettingsPage

ID_SYNC_TOGGLE = wx.NewId()
ID_SYNC_NOW = wx.NewId()
ID_RECALC_USAGE = wx.NewId()
ID_DO_FULL_SYNC = wx.NewId()

mainWindowStyle = wx.DEFAULT_FRAME_STYLE & (~wx.MAXIMIZE_BOX) ^ (wx.RESIZE_BORDER)
HERE=os.path.abspath(os.path.dirname(__file__))

class PageAccount(wx.Panel):
    def __init__(self, parent, sync_model):
        wx.Panel.__init__(self, parent, size=parent.GetSize(), style=wx.RAISED_BORDER)

        self.sync_model = sync_model
        self.totalFiles = 0
        self.time_left=0

        aboutdrive = sync_model.DriveInfo()
        self.driveUsageBar = DriveUsageBox(self, long(aboutdrive['storageQuota']['limit']), -1)
        self.driveUsageBar.SetStatusMessage("Calculating your categorical Google Drive usage. Please wait.")
        self.driveUsageBar.SetMoviesUsage(0)
        self.driveUsageBar.SetDocumentUsage(0)
        self.driveUsageBar.SetOthersUsage(0)
        self.driveUsageBar.SetAudioUsage(0)
        self.driveUsageBar.SetPhotoUsage(0)
        self.driveUsageBar.RePaint()


        mainsizer = wx.BoxSizer(wx.VERTICAL)
        mainsizer.AddSpacer(10)
        self.SetSizerAndFit(mainsizer)

        GoSyncEventController().BindEvent(self, GOSYNC_EVENT_CALCULATE_USAGE_STARTED,
                                          self.OnUsageCalculationStarted)
        GoSyncEventController().BindEvent(self, GOSYNC_EVENT_CALCULATE_USAGE_DONE,
                                          self.OnUsageCalculationDone)
        GoSyncEventController().BindEvent(self, GOSYNC_EVENT_CALCULATE_USAGE_UPDATE,
                                          self.OnUsageCalculationUpdate)

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

    def OnUsageCalculationUpdate(self, event):
        self.totalFiles = event.data
        self.driveUsageBar.SetStatusMessage("Calculating usage. Files Scanned: %d\n" % self.totalFiles)
        self.driveUsageBar.SetMoviesUsage(self.sync_model.GetMovieUsage())
        self.driveUsageBar.SetDocumentUsage(self.sync_model.GetDocumentUsage())
        self.driveUsageBar.SetOthersUsage(self.sync_model.GetOthersUsage())
        self.driveUsageBar.SetAudioUsage(self.sync_model.GetAudioUsage())
        self.driveUsageBar.SetPhotoUsage(self.sync_model.GetPhotoUsage())
        self.driveUsageBar.RePaint()

    def OnUsageCalculationStarted(self, event):
        self.totalFiles = event.data
        self.driveUsageBar.SetStatusMessage("Calculating your categorical Google Drive usage. Please wait.")

class GoSyncController(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, None, title="GoSync", size=(490,500), style=mainWindowStyle)

        try:
            self.sync_model = GoSyncModel()
        except ClientSecretsNotFound:
            dial = wx.MessageDialog(None, 'Credentials file was not found!\n\nDo you want to know how to create one?\n',
                                    'Error', wx.YES_NO | wx.ICON_EXCLAMATION)
            res = dial.ShowModal()

            if res == wx.ID_YES:
                webbrowser.open(CLIENT_SECRET_HELP_SITE, new=1, autoraise=True)

            sys.exit(1)
        except InternetNotReachable:
            dial = wx.MessageDialog(None, 'GoSync cannot connect to the Internet.\nPlease check your internet connection.',
                                    'Error', wx.OK | wx.ICON_EXCLAMATION)
            res = dial.ShowModal()
            sys.exit(1)

        except:
            dial = wx.MessageDialog(None, 'GoSync failed to initialize\n',
                                    'Error', wx.OK | wx.ICON_EXCLAMATION)
            res = dial.ShowModal()
            sys.exit(1)

        self.aboutdrive = self.sync_model.DriveInfo()
        self.Bind(wx.EVT_CLOSE, self.OnExit)
        self.IsBusy = False
        self.DisplayTitleBar()
        appIcon = wx.Icon(APP_ICON, wx.BITMAP_TYPE_PNG)
        self.SetIcon(appIcon)
        menuBar = wx.MenuBar()
        menu = wx.Menu()

        menu_txt = 'Pause/Resume Sync'

        self.pr_item = self.CreateMenuItem(menu, menu_txt, self.OnToggleSync,
                                           icon=os.path.join(HERE, 'resources/sync-menu.png'), id=ID_SYNC_TOGGLE)
        self.sync_now_mitem = self.CreateMenuItem(menu, 'Sync Now!', self.OnSyncNow,
                                                  icon=os.path.join(HERE, 'resources/sync-menu.png'), id=ID_SYNC_NOW)
        self.rcu = self.CreateMenuItem(menu, 'Recalculate Drive Usage', self.OnRecalculateDriveUsage,
                                       icon=os.path.join(HERE, 'resources/sync-menu.png'), id=ID_RECALC_USAGE)
        menu.AppendSeparator()
        self.rcu = self.CreateMenuItem(menu, 'Do Full Sync', self.OnDoFullSync,
                                       icon=os.path.join(HERE, 'resources/sync-menu.png'), id=ID_DO_FULL_SYNC)

        menu.AppendSeparator()
        self.CreateMenuItem(menu, 'A&bout', self.OnAbout, os.path.join(HERE, 'resources/info.png'))
        self.CreateMenuItem(menu, 'E&xit', self.OnExit, os.path.join(HERE, 'resources/exit.png'))

        menuBar.Append(menu, '&File')

        self.SetMenuBar(menuBar)

        # Here we create a panel and a notebook on the panel
        p = wx.Panel(self, size=self.GetSize())
        nb = wx.Notebook(p)

        # create the page windows as children of the notebook
        accountPage = PageAccount(nb, self.sync_model)
        selectionPage = SelectionPage(nb, self.sync_model)
        settingPage = SettingsPage(nb, self.sync_model)

        # add the pages to the notebook with the label to show on the tab
        nb.AddPage(accountPage, "Account")
        nb.AddPage(selectionPage, "What to sync?")
        nb.AddPage(settingPage, "Settings")

        # finally, put the notebook in a sizer for the panel to manage
        # the layout
        sizer = wx.BoxSizer()
        sizer.Add(nb, 1, wx.EXPAND)
        p.SetSizer(sizer)

        self.sb = self.CreateStatusBar(2)
        self.sb.SetStatusWidths([-6, -1])

        if self.sync_model.IsSyncEnabled():
            self.sb.SetStatusText("Running", 1)
            self.pr_item.SetItemLabel("Pause Sync")
        else:
            self.sb.SetStatusText("")
            self.sb.SetStatusText("Paused", 1)
            self.pr_item.SetItemLabel("Resume Sync")

        GoSyncEventController().BindEvent(self, GOSYNC_EVENT_SYNC_STARTED,
                                          self.OnSyncStarted)
        GoSyncEventController().BindEvent(self, GOSYNC_EVENT_BUSY_STARTED,
                                          self.OnBusyStart)
        GoSyncEventController().BindEvent(self, GOSYNC_EVENT_BUSY_DONE,
                                          self.OnBusyDone)
        GoSyncEventController().BindEvent(self, GOSYNC_EVENT_SYNC_UPDATE,
                                          self.OnSyncUpdate)
        GoSyncEventController().BindEvent(self, GOSYNC_EVENT_SYNC_DONE,
                                          self.OnSyncDone)
        GoSyncEventController().BindEvent(self, GOSYNC_EVENT_SYNC_TIMER,
                                          self.OnSyncTimer)
        GoSyncEventController().BindEvent(self, GOSYNC_EVENT_INTERNET_UNREACHABLE,
                                          self.OnInternetDown)
        GoSyncEventController().BindEvent(self, GOSYNC_EVENT_SYNC_INV_FOLDER,
                                          self.OnSyncInvalidFolder)
        GoSyncEventController().BindEvent(self, GOSYNC_EVENT_SCAN_UPDATE,
                                          self.OnScanUpdate)
        GoSyncEventController().BindEvent(self, GOSYNC_EVENT_CALCULATE_USAGE_DONE,
                                          self.OnUsageCalculationDone)
        GoSyncEventController().BindEvent(self, GOSYNC_EVENT_CALCULATE_USAGE_STARTED,
                                          self.OnUsageCalculationStarted)

        self.sync_model.SetTheBallRolling()

    def DisplayTitleBar(self):
        title_string = "GoSync - %s (%s used of %s)" % (self.aboutdrive['user']['displayName'],
                self.FileSizeHumanize(long(self.aboutdrive['storageQuota']['usageInDrive'])), 
                self.FileSizeHumanize(long(self.aboutdrive['storageQuota']['limit'])))
        self.SetTitle(title_string)


    def OnUsageCalculationStarted(self, event):
        self.pr_item.Enable(False)
        self.sync_now_mitem.Enable(False)
        self.rcu.Enable(False)

    def OnUsageCalculationDone(self, event):
        self.pr_item.Enable(True)
        if self.sync_model.IsSyncEnabled():
            self.sync_now_mitem.Enable(True)
        else:
            self.sync_now_mitem.Enable(False)
        self.rcu.Enable(True)
        self.DisplayTitleBar()
        self.sb.SetStatusText("Usage calculation completed.")

    def OnInternetDown(self, event):
        if event.data == 1:
            self.sb.SetStatusText("Network is down")
            if self.sync_model.GetUseSystemNotifSetting():
                if wxgtk4:
                    nmsg = wx.adv.NotificationMessage(title="GoSync", message="Network has gone down!")
                    nmsg.SetFlags(wx.ICON_WARNING)
                    nmsg.Show(timeout=wx.adv.NotificationMessage.Timeout_Auto)
                else:
                    nmsg = wx.NotificationMessage("GoSync", "Network has gone down!")
                    nmsg.SetFlags(wx.ICON_WARNING)
                    nmsg.Show(timeout=wx.NotificationMessage.Timeout_Auto)
        else:
            self.sb.SetStatusText("Network is up!")
            if self.sync_model.GetUseSystemNotifSetting():
                if wxgtk4:
                    nmsg = wx.adv.NotificationMessage(title="GoSync", message="Network is up!")
                    nmsg.SetFlags(wx.ICON_INFORMATION)
                    nmsg.Show(timeout=wx.adv.NotificationMessage.Timeout_Auto)
                else:
                    nmsg = wx.NotificationMessage("GoSync", "Network is up!")
                    nmsg.SetFlags(wx.ICON_INFORMATION)
                    nmsg.Show(timeout=wx.NotificationMessage.Timeout_Auto)

    def OnSyncInvalidFolder(self, event):
        if self.sync_model.GetUseSystemNotifSetting():
            if wxgtk4:
                nmsg = wx.adv.NotificationMessage(title="GoSync",
                                                  message="Invalid sync settings detected.\nPlease check the logs.")
                nmsg.SetFlags(wx.ICON_ERROR)
                nmsg.Show(timeout=wx.adv.NotificationMessage.Timeout_Auto)
            else:
                nmsg = wx.NotificationMessage("GoSync", "Invalid sync settings detected.\nPlease check the logs.")
                nmsg.SetFlags(wx.ICON_ERROR)
                nmsg.Show(timeout=wx.NotificationMessage.Timeout_Auto)

    def OnRecalculateDriveUsage(self, event):
        if self.sync_model.IsCalculatingDriveUsage() == True:
            dial = wx.MessageDialog(None, 'GoSync is already scaningfiles on drive.',
                                    'In Progress', wx.OK | wx.ICON_WARNING)
            res = dial.ShowModal()
            dial.Destroy()
            return
        elif self.sync_model.IsSyncRunning() == True:
            dial = wx.MessageDialog(None, 'GoSync is currently syncing files from the Drive.\nThe usage will be refreshed later.',
                                    'In Progress', wx.OK | wx.ICON_WARNING)
            res = dial.ShowModal()
            dial.Destroy()

        self.sync_model.ForceDriveUsageCalculation()


    def OnDoFullSync(self, event):
        self.sync_model.SetForceFullSync(True)

    def OnSyncTimer(self, event):
        unicode_string = event.data.pop()
        self.sb.SetStatusText(unicode_string.encode('ascii', 'ignore'))

    def OnSyncStarted(self, event):
        if self.sync_model.GetUseSystemNotifSetting():
            if wxgtk4 :
                nmsg = wx.adv.NotificationMessage(title="GoSync", message="Sync Started")
                nmsg.SetFlags(wx.ICON_INFORMATION)
                nmsg.Show(timeout=wx.adv.NotificationMessage.Timeout_Auto)
            else:
                nmsg = wx.NotificationMessage("GoSync", "Sync Started")
                nmsg.SetFlags(wx.ICON_INFORMATION)
                nmsg.Show(timeout=wx.NotificationMessage.Timeout_Auto)

        self.sb.SetStatusText("Sync started...")
        self.sb.SetStatusText("Running", 1)
        self.sync_now_mitem.Enable(False)
        self.rcu.Enable(False)
        self.pr_item.SetItemLabel("Pause Sync")

    def OnSyncUpdate(self, event):
        unicode_string = event.data.pop()
        self.sb.SetStatusText(unicode_string.encode('ascii', 'ignore'))

    #BusyStart : when a transfer starts
    def OnBusyStart(self, event):
        self.IsBusy = True
        unicode_string = event.data.pop()
        self.sb.SetStatusText(unicode_string.encode('ascii', 'ignore'))

    #BusyDone : when a transfer stops
    def OnBusyDone(self, event):
        self.IsBusy = False
        unicode_string = event.data.pop()
        self.sb.SetStatusText(unicode_string.encode('ascii', 'ignore'))

    def OnSyncDone(self, event):
        if not event.data:
            if self.sync_model.GetUseSystemNotifSetting():
                if wxgtk4:
                    nmsg = wx.adv.NotificationMessage(title="GoSync", message="Sync Completed!")
                    nmsg.SetFlags(wx.ICON_INFORMATION)
                    nmsg.Show(timeout=wx.adv.NotificationMessage.Timeout_Auto)
                else:
                    nmsg = wx.NotificationMessage("GoSync", "Sync Completed!")
                    nmsg.SetFlags(wx.ICON_INFORMATION)
                    nmsg.Show(timeout=wx.NotificationMessage.Timeout_Auto)
            self.sb.SetStatusText("Sync completed.")
        else:
            if self.sync_model.GetUseSystemNotifSetting():
                if wxgtk4:
                    nmsg = wx.adv.NotificationMessage(title="GoSync", message="Sync Completed with errors!\nPlease check ~/GoSync.log")
                    nmsg.SetFlags(wx.ICON_ERROR)
                    nmsg.Show(timeout=wx.adv.NotificationMessage.Timeout_Auto)
                else:
                    nmsg = wx.NotificationMessage("GoSync", "Sync Completed with errors!\nPlease check ~/GoSync.log")
                    nmsg.SetFlags(wx.ICON_ERROR)
                    nmsg.Show(timeout=wx.NotificationMessage.Timeout_Auto)
            self.sb.SetStatusText("Sync failed. Please check the logs.")
        self.sync_now_mitem.Enable(True)
        self.rcu.Enable(True)

    def OnScanUpdate(self, event):
        unicode_string = event.data.pop()
        self.sb.SetStatusText(unicode_string.encode('ascii', 'ignore'))

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

        if wxgtk4 :
            menu.Append(item)
        else:
            menu.AppendItem(item)
        return item

    def FileSizeHumanize(self, size):
        size = abs(size)
        if (size==0):
            return "0B"
        units = ['B','KB','MB','GB','TB','PB','EB','ZB','YB']
        p = math.floor(math.log(size, 2)/10)
        return "%.3f%s" % (size/math.pow(1024,p),units[long(p)])

    def OnExit(self, event):
        dial = wx.MessageDialog(None, 'GoSync will stop syncing files until restarted.\nAre you sure to quit?\n',
                                'Question', wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        res = dial.ShowModal()
        if res == wx.ID_YES:
            if self.sync_model.IsSyncEnabled() or self.sync_model.IsSyncRunning():
                self.sync_model.StopSync()
                self.Disable()
                if self.IsBusy :
                    self.sb.SetStatusText("Please wait while GoSync is Cancelling a Transfer")
                else :
                    self.sb.SetStatusText("Paused", 1)
                self.sync_model.StopTheShow()

            wx.CallAfter(self.Destroy)

    def OnToggleSync(self, evt):
        if self.sync_model.IsSyncEnabled():
            self.sync_model.StopSync()
            if self.IsBusy :
                self.sb.SetStatusText("Please wait while GoSync is Cancelling a Transfer")
            else :
                self.sb.SetStatusText("Sync is paused")
            self.sb.SetStatusText("Paused", 1)
            self.pr_item.SetItemLabel("Resume Sync")
            self.sync_now_mitem.Enable(False)
        else:
            self.sync_model.StartSync()
            self.sb.SetStatusText("Running", 1)
            self.pr_item.SetItemLabel("Pause Sync")
            self.sync_now_mitem.Enable(True)

    def OnSyncNow(self, evt):
        self.sync_model.time_left=1

    def OnAbout(self, evt):
        """About GoSync"""
        if wxgtk4 :
            about = wx.adv.AboutDialogInfo()
        else:
            about = wx.AboutDialogInfo()
        about.SetIcon(wx.Icon(ABOUT_ICON, wx.BITMAP_TYPE_PNG))
        about.SetName(APP_NAME)
        about.SetVersion(APP_VERSION)
        about.SetDescription(APP_DESCRIPTION)
        about.SetCopyright(APP_COPYRIGHT)
        about.SetWebSite(APP_WEBSITE)
        about.SetLicense(APP_LICENSE)
        about.AddDeveloper(APP_DEVELOPER)
        about.AddArtist(ART_DEVELOPER)
        if wxgtk4 :
            wx.adv.AboutBox(about)
        else:
            wx.AboutBox(about)

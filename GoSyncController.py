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

import sys, os, wx, gtk, ntpath, defines, threading, math
from GoSyncModel import GoSyncModel
#from defines import TRAY_ICON, TRAY_TOOLTIP, APP_NAME, APP_VERSION, APP_DESCRIPTION
from defines import *
from threading import Timer
from GoSyncPreferences import GoSyncPreferenceDialog

class GoSyncController:
    def __init__(self):
        try:
            self.sync_model = GoSyncModel()
        except:
            message = gtk.MessageDialog(type=gtk.MESSAGE_ERROR,
                                        buttons=gtk.BUTTONS_OK)
            message.set_markup("GoSync core failed to initialized!")
            message.run()
            message.destroy()
            gtk.main_quit()

        self.tray = gtk.StatusIcon()
        self.tray.set_from_file(TRAY_ICON)
        self.tray.connect('popup-menu', self.on_right_click)
        self.tray.set_tooltip((TRAY_TOOLTIP))


    def on_right_click(self, icon, event_button, event_time):
        self.make_menu(event_button, event_time)

    def CreateMenuItem(self, menu, label, func, icon=None):
        if icon is not None:
            img = gtk.Image()
            img.set_from_file(icon)
            newItem = gtk.ImageMenuItem(gtk.STOCK_NEW)
            newItem.set_image(img)
            newItem.set_always_show_image(True)
            newItem.set_label(label)
        else:
            newItem = gtk.MenuItem(label)

        newItem.show()
        menu.append(newItem)
        newItem.connect('activate', func)

    def make_menu(self, event_button, event_time):
        menu = gtk.Menu()
        aboutdrive = self.sync_model.DriveInfo()
        driveTotalSpace = float(aboutdrive['quotaBytesTotal'])
        driveUsedSpace = float(aboutdrive['quotaBytesUsed'])
        usage_string = "%s/%s" % (self.FileSizeHumanize(driveUsedSpace),
                                  self.FileSizeHumanize(driveTotalSpace))
        self.CreateMenuItem(menu, aboutdrive['name'], self.OnLeftDown,
                            'resources/user.png')
        self.CreateMenuItem(menu, usage_string, self.OnLeftDown,
                            'resources/usage.png')
        if self.sync_model.IsSyncEnabled():
            self.CreateMenuItem(menu, 'Stop Background Sync',
                                self.OnStopSync, 'resources/sync-menu.png')
        else:
            self.CreateMenuItem(menu, 'Start Background Sync',
                                self.OnSyncNow, 'resources/sync-menu.png')
        menu.append(gtk.SeparatorMenuItem())

        self.CreateMenuItem(menu, 'About', self.show_about_dialog,
                            'resources/info.png')

        self.CreateMenuItem(menu, 'Exit', gtk.main_quit,
                            'resources/exit.png')

        menu.popup(None, None, gtk.status_icon_position_menu,
                   event_button, event_time, self.tray)

    def show_about_dialog(self, widget):
        """About GoSync"""
        about = gtk.AboutDialog()
        about.set_destroy_with_parent(True)
        about.set_icon_name(APP_NAME)
        about.set_name(APP_NAME)
        about.set_version(APP_VERSION)
        about.set_comments(APP_DESCRIPTION)
        about.set_authors(APP_DEVELOPER)
        about.set_artists(APP_DEVELOPER)
        about.set_logo(gtk.gdk.pixbuf_new_from_file_at_size(TRAY_ICON, 128,128))
        about.set_copyright(APP_COPYRIGHT)
        about.set_license(APP_LICENSE)
        about.run()
        about.destroy()

    def FileSizeHumanize(self, size):
        size = abs(size)
        if (size==0):
            return "0B"
        units = ['B','KiB','MiB','GiB','TiB','PiB','EiB','ZiB','YiB']
        p = math.floor(math.log(size, 2)/10)
        return "%.3f%s" % (size/math.pow(1024,p),units[int(p)])

    def OnLeftDown(self, event):
        return

    def OnExit(self, event):
        dial = gtk.MessageDialog(parent=self,
                                 flags=gtk.DIALOG_MODAL,
                                 type=gtk.MESSAGE_QUESTION,
                                 buttons=gtk.BUTTONS_YES_NO)
        dial.set_markup('GoSync will stop syncing files until restarted.\nAre you sure to quit?')
        dial.connect("response", self.dialog_response)
        dial.show()

    def dialog_response(self, widget, response_id):
        if response_id == gtk.ResponseType.OK:
            gtk.main_quit()

    def OnSyncNow(self, evt):
        self.sync_model.StartSync()

    def OnStopSync(self, evt):
        """Stop syncing with google drive"""
        self.sync_model.StopSync()

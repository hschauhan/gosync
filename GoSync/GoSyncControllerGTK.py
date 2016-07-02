# GoSync is an open source Google Drive(TM) sync application for Linux
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

import os, time, sys, ntpath, threading, math, webbrowser, platform
from gi.repository import Gtk, GdkPixbuf
from GoSyncModel import GoSyncModel, ClientSecretsNotFound, ConfigLoadFailed
from defines import *
from threading import Timer

if platform.dist()[0] == 'Ubuntu':
        from gi.repository import AppIndicator3 as appindicator

import gi
gi.require_version('Gtk', '3.0')

def menuitem_close_response(w, buf):
	Gtk.main_quit()

class GoSyncSettingsWindowGTK(Gtk.Window):
	def __init__(self, sync_model=None):
		self.sync_model = sync_model
		Gtk.Window.__init__(self, title=APP_NAME)

		self.set_border_width(10)
		self.sync_all = True

		vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
		self.add(vbox)

		stack = Gtk.Stack()
		stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
		stack.set_transition_duration(1000)

		self.tree_store = Gtk.TreeStore(str, bool, object)
		self.tree_view = Gtk.TreeView(self.tree_store)
		self.tree_view.set_rules_hint(True)

		self.renderer = Gtk.CellRendererText()
		self.renderer.set_property('editable', False)

		self.renderer1 = Gtk.CellRendererToggle()
		self.renderer1.set_property('activatable', True)
		self.renderer1.connect('toggled', self.select_toggled_cb, self.tree_store)

		self.column0 = Gtk.TreeViewColumn("Folders", self.renderer, text=0)
		self.column1 = Gtk.TreeViewColumn("Sync", self.renderer1)
		self.column1.add_attribute(self.renderer1, "active", 1)

		self.tree_view.append_column(self.column0)
		self.tree_view.append_column(self.column1)

		driveTree = self.sync_model.GetDriveDirectoryTree()
		self.MakeDriveTree(driveTree.GetRoot(), None)

		vbox_so = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

		self.account_status = Gtk.Entry()
		self.account_status.set_editable(False)
		self.aboutdrive = self.sync_model.DriveInfo()
		self.account_status.set_text(("%s of %s used") % (self.FileSizeHumanize(long(self.aboutdrive['quotaBytesUsed'])), self.FileSizeHumanize(long(self.aboutdrive['quotaBytesTotal']))))
		self.account_status.set_progress_fraction(long(self.aboutdrive['quotaBytesUsed'])/long(self.aboutdrive['quotaBytesTotal']))
		self.set_title(self.aboutdrive['name'])

		self.sync_all_check = Gtk.CheckButton("Sync Everything")
		self.sync_all_check.connect("toggled", self.OnSyncAllToggled)

		label = Gtk.Label("Logged in as %s" % self.aboutdrive['user']['emailAddress'])

		button = Gtk.Button.new_with_label("Disconnect From Drive")
		button.connect("clicked", self.menuitem_logout)

		stack.add_titled(vbox_so, "sync_options", "Sync Options and Account")
		stack_switcher = Gtk.StackSwitcher()
		stack_switcher.set_stack(stack)

		vbox_so.pack_start(label, True, True, 0)
		vbox_so.pack_start(self.account_status, True, True, 0)
		vbox_so.pack_start(self.tree_view, True, True, 0)
		vbox_so.pack_start(self.sync_all_check, True, True, 0)
		vbox.pack_start(stack_switcher, True, True, 0)
		vbox.pack_start(stack, True, True, 0)
		vbox.pack_end(button, True, True, 0)

		self.SyncEntries()

		self.show_all()

	def MakeDriveTree(self, gparent, tparent):
		file_list = gparent.GetChildren()
		for f in file_list:
			nparent = self.tree_store.append(tparent, (f.GetName(), None, f))
			self.MakeDriveTree(f, nparent)

	def SyncEntries(self):
		sync_list = self.sync_model.GetSyncList()
		rootiter = self.tree_store.get_iter_first()
		for sync_entry in sync_list:
			if sync_entry[0] == "root":
				self.sync_all_check.set_active(True)
				self.sync_all = True
			else:
				self.sync_all_check.set_active(False)
				self.sync_all = False
				self.MarkSyncEntries(sync_entry, self.tree_store, rootiter)

	def MarkSyncEntries(self, sync_entry, store, treeiter):
		while treeiter != None:
			if store[treeiter][2].GetId() == sync_entry[1]:
				store[treeiter][1] = True;
			if store.iter_has_child(treeiter):
				childiter = store.iter_children(treeiter)
				self.MarkSyncEntries(sync_entry, store, childiter)
			treeiter = store.iter_next(treeiter)

	def DeselectEntriesAtIter(self, store, treeiter):
		while treeiter !=  None:
			store[treeiter][1] = False;
			if store.iter_has_child(treeiter):
				childiter = store.iter_children(treeiter)
				self.DeselectEntriesAtIter(store, childiter)
			treeiter = store.iter_next(treeiter)

	def DeselectAllInTreeView(self):
		rootiter = self.tree_store.get_iter_first()
		self.DeselectEntriesAtIter(self.tree_store, rootiter)

	def select_toggled_cb(self, cell, path, model):
		if not self.sync_all:
			model[path][1] = not model[path][1]
			f = model[path][2]
			self.sync_model.SetSyncSelection(f)
			print "Toggle '%s' to: %s Full Path: %s" % (model[path][0], model[path][1], model[path][2].GetPath())
		return

	def OnSyncAllToggled(self, button):
		self.sync_all = button.get_active()
		if self.sync_all:
			self.sync_model.SetSyncSelection('root')
			self.DeselectAllInTreeView()

	def FileSizeHumanize(self, size):
		size = abs(size)
		if (size==0):
			return "0B"
		units = ['B','KB','MB','GB','TB','PB','EB','ZB','YB']
		p = math.floor(math.log(size, 2)/10)
		return "%.3f%s" % (size/math.pow(1024,p),units[int(p)])

	def menuitem_logout(self, w):
		self.sync_model.DoUnAuthenticate()
		Gtk.main_quit()


class GoSyncControllerGTK(object):
	def __init__(self):
		try:
			self.sync_model = GoSyncModel()
		except ClientSecretsNotFound:
			print("Client secrets not found")
			return
		except ConfigLoadFailed:
			print("Config load failed")
			return
		except:
			print("GoSync model failed to initialize")
			return

		self.sync_model.SetTheBallRolling()

		self.aboutdrive = self.sync_model.DriveInfo()

		self.menu = None

		if platform.dist()[0] == 'Ubuntu':
			ind = appindicator.Indicator.new(APP_ID, "whatever", appindicator.IndicatorCategory.APPLICATION_STATUS)
			ind.set_status(appindicator.IndicatorStatus.ACTIVE)
			ind.set_icon_theme_path(RESOURCE_PATH)
			ind.set_icon("GoSyncIcon-32")
			self.CreateMenu()
			ind.set_menu(self.menu)
		else:
			self.tray = Gtk.StatusIcon()
			self.tray.set_from_pixbuf(GdkPixbuf.Pixbuf.new_from_file(TRAY_ICON))
			self.tray.connect('popup-menu', self.OnRightClick)

		Gtk.main()

	def CreateMenu(self):
		self.menu = Gtk.Menu()

		menu_item = Gtk.MenuItem(self.aboutdrive['name'])
		self.menu.append(menu_item)

		menu_item = Gtk.MenuItem(("%s used of %s") % (self.FileSizeHumanize(long(self.aboutdrive['quotaBytesUsed'])),
								self.FileSizeHumanize(long(self.aboutdrive['quotaBytesTotal']))))
		self.menu.append(menu_item)

		menu_item = Gtk.SeparatorMenuItem()
		self.menu.append(menu_item)

		if self.sync_model.IsSyncEnabled():
			menu_item = Gtk.MenuItem("Pause")
		else:
			menu_item = Gtk.MenuItem("Start")
		menu_item.connect("activate", self.menuitem_startstop_response, "startstop")
		self.menu.append(menu_item)

		menu_item = Gtk.MenuItem("Settings")
		menu_item.connect("activate", self.menuitem_settings_response, "Settings")
		self.menu.append(menu_item)

		menu_item = Gtk.SeparatorMenuItem()
		self.menu.append(menu_item)

		about = Gtk.MenuItem()
		about.set_label("About")
		about.connect("activate", self.ShowAboutDialog)
		self.menu.append(about)

		menu_item = Gtk.MenuItem("Quit")
		menu_item.connect("activate", menuitem_close_response, "Quit")
		self.menu.append(menu_item)

		self.menu.show_all()

	def OnRightClick(self, icon, event_button, event_time):
		if self.menu is None:
			self.CreateMenu()
		self.menu.popup(None, None, None, self.tray, event_button, event_time)

	def  ShowAboutDialog(self, widget):
		about_dialog = Gtk.AboutDialog()
		about_dialog.set_destroy_with_parent (True)
		about_dialog.set_icon_name(TRAY_ICON)
		about_dialog.set_name(APP_NAME)
		about_dialog.set_website(APP_WEBSITE)
		about_dialog.set_version(APP_VERSION)
		about_dialog.set_copyright(APP_COPYRIGHT)
		about_dialog.set_comments((APP_DESCRIPTION))
		about_dialog.set_authors([APP_DEVELOPER])
		about_dialog.set_artists([APP_DEVELOPER])
		about_dialog.set_logo(GdkPixbuf.Pixbuf.new_from_file(ABOUT_ICON))
		about_dialog.set_license(APP_LICENSE)
		about_dialog.run()
		about_dialog.destroy()

	def menuitem_startstop_response(self, item, buf):
		if item.get_label() == "Pause":
			print("Stop the sync")
			item.set_label("Start")
			self.sync_model.StartSync()
		else:
			print("Start the sync")
			item.set_label("Pause")
			self.sync_model.StopSync()

	def menuitem_settings_response(self, w, buf):
		self.settings_window = GoSyncSettingsWindowGTK(self.sync_model)
		self.settings_window.show_all()

	def FileSizeHumanize(self, size):
		size = abs(size)
		if (size==0):
			return "0B"
		units = ['B','KB','MB','GB','TB','PB','EB','ZB','YB']
		p = math.floor(math.log(size, 2)/10)
		return "%.3f%s" % (size/math.pow(1024,p),units[int(p)])


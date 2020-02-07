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

import os

class DriveFolder(object):
    def __init__(self, parent, id, name, data=None):
        self.children = []
        self.id = id
        self.parent = parent
        self.data = data
        self.name = name

    def SetData(self, data):
        self.data = data

    def GetData(self):
        return self.data

    def GetParent(self):
        return parent

    def GetId(self):
        return self.id

    def GetName(self):
        return self.name

    def AddChild(self, child):
        self.children.append(child)

    def DeleteChild(self, child):
        self.children.remove(child)

    def GetChildren(self):
        return self.children

    def GetPath(self):
        cpath =''
        if self.parent is not None:
            cpath = self.parent.GetPath()

        if self.parent is None:
            path = os.path.join(cpath, '')
        else:
            path = os.path.join(cpath, self.GetName())

        return path


class GoogleDriveTree(object):
    def __init__(self):
        self.root_node = DriveFolder(None, 'root', 'Google Drive Root', None)

    def GetRoot(self):
        return self.root_node

    def FindFolderInParent(self, parent, id):
        for f in parent.GetChildren():
            if f.GetId() == id:
                return f
            
            ret = self.FindFolderInParent(f, id)
            if ret:
                return ret

        return None

    def FindFolder(self, id):
        if id == 'root':
            return self.root_node
        else:
            return self.FindFolderInParent(self.root_node, id)

    def AddFolder(self, parent, folder_id, folder_name, data):
        if not parent:
            return None

        pnode = self.FindFolder(parent)

        if self.FindFolder(folder_id):
            return

        cnode = DriveFolder(pnode, folder_id, folder_name, data)
        pnode.AddChild(cnode)

    def DeleteFolder(self, folder_id):
        folder = self.FindFolder(folder_id)
        if folder:
            folder.GetParent().DeleteChild(folder)

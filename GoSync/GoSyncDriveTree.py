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

import os, threading, logging

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
        return self.parent

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
            print("FindFolderInParent - Parent: %s Child %s" % (parent, f.GetId()))
            if f.GetId() == id:
                print("FindFolderInParent - Found child with ID %s" % f.GetId())
                return f

            ret = self.FindFolderInParent(f, id)
            if ret:
                print("FindFolderInParent - Found Folder (ID: %s)", ret.GetId())
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

        print("AddFolder: Parent: %s Folder: %s Name: %s" % (parent, folder_id, folder_name))
        pnode = self.FindFolder(parent)
        print("AddFolder: Found parent Folder: %s" % parent)
        if self.FindFolder(folder_id):
            return

        cnode = DriveFolder(pnode, folder_id, folder_name, data)
        pnode.AddChild(cnode)
        print("AddFolder: Child added")

    def __DeleteFolder(self, folder_id, FolderDeleteCallback):
        print("__DeleteFolder: Folder: %s" % folder_id)
        pnode = self.FindFolder(folder_id)
        print("__DeleteFolder: Found folder to delete")

        if not pnode.GetChildren():
            print("__DeleteFolder: No child to folder %s" % folder_id)
            print("__DeleteFolder: Path %s" % pnode.GetPath())
            if FolderDeleteCallback:
                FolderDeleteCallback(pnode)
            print("__DeleteFolder: Deleting from parent: %s this: %s" % (pnode.GetParent().GetId(), pnode.GetId()))
            pnode.GetParent().DeleteChild(pnode)
            return

        print("__DeleteFolder: Folder %s has children. Deleting recursively" % folder_id)

        #This try is important. After Deleting child, the pnode's
        #for loop goes for a toss. So a call of pnode.GetChildren()
        #is required to start afresh.
        #
        #I have sweat enough on it, can I can't get this working in
        #a pure recursive way.
        while True:
            if not pnode.GetChildren():
                print("__DeleteFolder: No children? ID: %s" % pnode.GetId())
                break
            for child in pnode.GetChildren():
                print("__DeleteFolder: Recursive: child ID: %s name: %s" % (child.GetId(), child.GetName()))
                self.__DeleteFolder(child.GetId(), FolderDeleteCallback)
                break

    #This is really ugly. But while deleting child, the child list
    #keeps modifying and for loop goes for a toss. The "recursive"
    #function doesn't delete the root. So second call to get rid of
    #root node as well.
    def DeleteFolder(self, folder_id, FolderDeleteCallback=None):
        self.__DeleteFolder(folder_id, FolderDeleteCallback)
        self.__DeleteFolder(folder_id, FolderDeleteCallback)

    def PrintTree(self, folder_id):
        pnode = self.FindFolder(folder_id)

        if not pnode:
            return

        children = pnode.GetChildren()

        for child in children:
            if child:
                self.PrintTree(child.GetId())

        print("%s" % pnode.GetName())


#DRIVER CODE
#tree = GoogleDriveTree()
#tree.AddFolder('root', 'aaaa', 'a', None)
#tree.AddFolder('aaaa', 'bbbb', 'a/b', None)
#tree.AddFolder('aaaa', 'nnnn', 'a/n', None)
#tree.AddFolder('aaaa', 'oooo', 'a/o', None)
#tree.AddFolder('bbbb', 'cccc', 'a/b/c', None)
#tree.AddFolder('bbbb', 'llll', 'a/b/l', None)
#tree.AddFolder('bbbb', 'mmmm', 'a/b/m', None)
#tree.AddFolder('cccc', 'dddd', 'a/b/c/d', None)
#tree.AddFolder('dddd', 'eeee', 'a/b/c/d/e', None)
#tree.AddFolder('eeee', 'ffff', 'a/b/c/d/e/f', None)
#tree.AddFolder('ffff', 'gggg', 'a/b/c/d/e/f/g', None)
#tree.AddFolder('gggg', 'hhhh', 'a/b/c/d/e/f/g/h', None)
#tree.AddFolder('hhhh', 'iiii', 'a/b/c/d/e/f/g/h/i', None)
#tree.AddFolder('iiii', 'jjjj', 'a/b/c/d/e/f/g/h/i/j', None)
#tree.AddFolder('jjjj', 'kkkk', 'a/b/c/d/e/f/g/h/i/j/k', None)
#
#tree.PrintTree('root')
#print("++++++++++++++++++++++++++++")
#tree.DeleteFolder('aaaa')
#print("----------------------------")
#tree.DeleteFolder('aaaa')
#print("============================")
#tree.PrintTree('root')

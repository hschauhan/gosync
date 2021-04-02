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

class DriveFile(object):
    def __init__(self, parent, id, name, data=None):
        self.id = id
        self.parent = parent
        self.data = data
        self.name = name

    def IsFile(self):
        return True

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

    def GetPath(self):
        cpath =''
        if self.parent is not None:
            cpath = self.parent.GetPath()

        if self.parent is None:
            path = os.path.join(cpath, '')
        else:
            path = os.path.join(cpath, self.GetName())

        return path

class DriveFolder(object):
    def __init__(self, parent, id, name, data=None):
        self.children = []
        self.id = id
        self.parent = parent
        self.data = data
        self.name = name

    def IsFile(self):
        return False

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
            if f.GetId() == id:
                return f

            if not f.IsFile():
                ret = self.FindFolderInParent(f, id)
                if ret:
                    return ret

        return None

    def FindFolder(self, id):
        if id == 'root':
            return self.root_node
        else:
            return self.FindFolderInParent(self.root_node, id)

    def FindFolderByPath(self, rel_path, parent=None):
        if parent == None:
            parent = self.root_node

        for f in parent.GetChildren():
            if not f.IsFile() and f.GetPath() == rel_path:
                return f

            if not f.IsFile():
                ret = self.FindFolderByPath(rel_path, f)
                if ret:
                    return ret

        return None

    def FindFile(self, id):
        return self.FindFolderInParent(self.root_node, id)

    def FindFileByPath(self, rel_path, parent=None):
        if parent == None:
            parent = self.root_node

        for f in parent.GetChildren():
            if f.IsFile() and f.GetPath() == rel_path:
                return f

            if not f.IsFile():
                ret = self.FindFileByPath(rel_path, f)
                if ret:
                    return ret

        return None

    def AddFile(self, parent, file_id, file_name, data):
        if not parent:
            return None

        pnode = self.FindFolder(parent)
        if self.FindFile(file_id):
            return

        cnode = DriveFile(pnode, file_id, file_name, data)
        pnode.AddChild(cnode)

    def AddFolder(self, parent, folder_id, folder_name, data):
        if not parent:
            return None

        pnode = self.FindFolder(parent)
        if self.FindFolder(folder_id):
            return

        cnode = DriveFolder(pnode, folder_id, folder_name, data)
        pnode.AddChild(cnode)

    def __DeleteFolder(self, folder_id, FolderDeleteCallback):
        pnode = self.FindFolder(folder_id)

        if pnode is None:
            raise NameError("__DeleteFolder: Parent folder %s not found" % folder_id)

        if not pnode.GetChildren():
            try:
                if FolderDeleteCallback:
                    FolderDeleteCallback(pnode)
            except:
                #The folder delete callback should handle things properly
                pass
            pnode.GetParent().DeleteChild(pnode)
            return

        #This try is important. After Deleting child, the pnode's
        #for loop goes for a toss. So a call of pnode.GetChildren()
        #is required to start afresh.
        #
        #I have sweat enough on it, can I can't get this working in
        #a pure recursive way.
        while True:
            if not pnode.GetChildren():
                break
            for child in pnode.GetChildren():
                try:
                    self.__DeleteFolder(child.GetId(), FolderDeleteCallback)
                except:
                    raise
                else:
                    break

    #This is really ugly. But while deleting child, the child list
    #keeps modifying and for loop goes for a toss. The "recursive"
    #function doesn't delete the root. So second call to get rid of
    #root node as well.
    def DeleteFolder(self, folder_id, FolderDeleteCallback=None):
        try:
            self.__DeleteFolder(folder_id, FolderDeleteCallback)
            self.__DeleteFolder(folder_id, FolderDeleteCallback)
        except:
            raise
        else:
            return

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

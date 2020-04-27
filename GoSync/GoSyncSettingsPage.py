import wx
import wx.lib.agw.customtreectrl as CT
#from pydrive.drive import GoogleDrive
#from pydrive.auth import GoogleAuth
try :
    from .GoSyncEvents import *
except (ImportError, ValueError):
    from GoSyncEvents import *

class GoSyncDriveTree(CT.CustomTreeCtrl):
    def __init__(self, parent, *args, **kw):
        CT.CustomTreeCtrl.__init__(self, parent, *args, **kw)

    def GetCheckedItems(self, itemParent=None, checkedItems=None):
        if itemParent is None:
            itemParent = self.GetRootItem()

        if checkedItems is None:
            checkedItems = []

        child, cookie = self.GetFirstChild(itemParent)

        while child:

            if self.IsItemChecked(child):
                checkedItems.append(child)

            checkedItems = self.GetCheckedItems(child, checkedItems)
            child, cookie = self.GetNextChild(itemParent, cookie)

        return checkedItems

class SettingsPage(wx.Panel):
    def __init__(self, parent, sync_model):
        wx.Panel.__init__(self, parent)

        headerFont = wx.Font(11.5, wx.SWISS, wx.NORMAL, wx.NORMAL)

        self.sync_model = sync_model
        self.dstc = GoSyncDriveTree(self, pos=(0,0))

        t1 = wx.StaticText(self, -1, "Choose the directories to sync:\n", pos=(0,0))
        t1.SetFont(headerFont)

        self.cb = wx.CheckBox(self, -1, 'Sync Everything', (10, 10))
        self.cb.SetValue(True)
        self.dstc.Disable()
        self.cb.Bind(wx.EVT_CHECKBOX, self.SyncSetting)

        btn = wx.Button(self, label="Refresh")
        btn.Bind(wx.EVT_BUTTON, self.RefreshTree)
        self.Bind(CT.EVT_TREE_ITEM_CHECKED, self.ItemChecked)

        GoSyncEventController().BindEvent(self, GOSYNC_EVENT_CALCULATE_USAGE_DONE,
                                          self.RefreshTree)
        #wx.EVT_CHECKBOX(self, self.cb.GetId(), self.SyncSetting)
        self.cb.Bind(wx.EVT_CHECKBOX, self.SyncSetting)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(t1, 0, wx.ALL)
        sizer.Add(self.cb, 0, wx.ALL)
        sizer.Add(self.dstc, 1, wx.EXPAND)
        sizer.Add(btn, 0, wx.ALL|wx.CENTER, 5)
        self.SetSizer(sizer)


    def SyncSetting(self, event):
        if self.cb.GetValue():
            self.dstc.Disable()
            self.sync_model.SetSyncSelection('root')
        else:
            self.dstc.Enable()
            checkedItems = self.dstc.GetCheckedItems()
            for item in checkedItems:
                folder = self.dstc.GetPyData(item)
                self.sync_model.SetSyncSelection(folder)

    def ItemChecked(self, event):
        folder = self.dstc.GetPyData(event.GetItem())
        self.sync_model.SetSyncSelection(folder)

    def MakeDriveTree(self, gnode, tnode):
        file_list = gnode.GetChildren()
        for f in file_list:
            nnode = self.dstc.AppendItem(tnode, f.GetName(), ct_type=1)
            self.dstc.SetPyData(nnode, f)
            self.MakeDriveTree(f, nnode)

    def GetItemsToBeChecked(self, checklist, itemParent = None, itemToBeChecked = None):
        if itemParent is None:
            itemParent = self.dstc.GetRootItem()

        if itemToBeChecked is None:
            itemToBeChecked = []

        child, cookie = self.dstc.GetFirstChild(itemParent)

        while child:
            child_data = self.dstc.GetPyData(child)
            for d in checklist:
                if child_data.GetId() == d[1]:
                    itemToBeChecked.append(child)

            itemToBeChecked = self.GetItemsToBeChecked(checklist, child, itemToBeChecked)
            child, cookie = self.dstc.GetNextChild(itemParent, cookie)

        return itemToBeChecked

    def RefreshTree(self, event):
        driveTree = self.sync_model.GetDriveDirectoryTree()
        self.dstc.DeleteAllItems()
        self.dstc_root = self.dstc.AddRoot("Google Drive Root")
        self.MakeDriveTree(driveTree.GetRoot(), self.dstc_root)
        self.dstc.ExpandAll()
        sync_list = self.sync_model.GetSyncList()
        for d in sync_list:
            if d[0] == 'root':
                self.cb.SetValue(True)
                self.dstc.Disable()
                return
            else:
                self.cb.SetValue(False)
                self.dstc.Enable()
                break

        item_list = self.GetItemsToBeChecked(sync_list)
        for item in item_list:
            self.dstc.CheckItem(item)

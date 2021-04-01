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

class SelectionPage(wx.Panel):
    def __init__(self, parent, sync_model):
        wx.Panel.__init__(self, parent, style=wx.RAISED_BORDER)

        headerFont = wx.Font(11.5, wx.SWISS, wx.NORMAL, wx.NORMAL)

        self.sync_model = sync_model
        self.dstc = GoSyncDriveTree(self, pos=(0,0))

        self.t1 = wx.StaticText(self, -1, "Choose the directories to sync:", pos=(0,0))
        self.t1.SetFont(headerFont)

        self.cb = wx.CheckBox(self, -1, 'Sync Everything', (10, 10))
        self.cb.SetValue(True)
        self.cb.Disable()
        self.dstc.Disable()
        self.cb.Bind(wx.EVT_CHECKBOX, self.SyncSetting)

        self.Bind(CT.EVT_TREE_ITEM_CHECKED, self.ItemChecked)

        GoSyncEventController().BindEvent(self, GOSYNC_EVENT_CALCULATE_USAGE_DONE,
                                          self.RefreshTree)
        GoSyncEventController().BindEvent(self, GOSYNC_EVENT_CALCULATE_USAGE_STARTED,
                                          self.OnUsageCalculationStarted)

        self.cb.Bind(wx.EVT_CHECKBOX, self.SyncSetting)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.t1, 0, wx.ALL)
        sizer.Add(self.cb, 0, wx.ALL)
        sizer.Add(self.dstc, 1, wx.EXPAND,2)
        self.SetSizer(sizer)

    def OnUsageCalculationStarted(self, event):
        self.cb.Disable()
        self.dstc.Disable()
        self.t1.SetLabel("Scanning Google Drive to create directory tree. Please Wait...")

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
        self.dstc.AutoCheckChild(event.GetItem(), event.GetItem().IsChecked())
        checkedItems = self.dstc.GetCheckedItems()
        self.sync_model.ClearSyncSelection()
        for item in checkedItems:
            folder = self.dstc.GetPyData(item)
            self.sync_model.SetSyncSelection(folder)

        #folder = self.dstc.GetPyData(event.GetItem())
        #if event.GetItem().IsChecked():
        #    self.sync_model.SetSyncSelection(folder)
        #else:
        #    self.sync_model.RemoveSyncSelection(folder)

    def MakeDriveTree(self, gnode, tnode):
        if gnode.IsFile():
            return

        file_list = gnode.GetChildren()
        for f in file_list:
            if f.IsFile():
                continue
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
        self.Bind(CT.EVT_TREE_ITEM_CHECKED, None)
        driveTree = self.sync_model.GetDriveDirectoryTree()
        self.t1.SetLabel("Choose the directories to sync:")
        self.cb.Enable()
        self.dstc.DeleteAllItems()
        self.dstc_root = self.dstc.AddRoot("Google Drive Root")
        self.MakeDriveTree(driveTree.GetRoot(), self.dstc_root)
        self.dstc.Expand(self.dstc_root)
        sync_list = self.sync_model.GetSyncList()
        for d in sync_list:
            if d[0] == 'root':
                self.cb.SetValue(True)
                self.dstc.Disable()
                self.Bind(CT.EVT_TREE_ITEM_CHECKED, self.ItemChecked)
                return
            else:
                self.cb.SetValue(False)
                self.dstc.Enable()
                self.dstc.SetFocus()
                #break

        item_list = self.GetItemsToBeChecked(sync_list)
        for item in item_list:
            self.dstc.CheckItem(item)
            self.dstc.Expand(item)
        self.Bind(CT.EVT_TREE_ITEM_CHECKED, self.ItemChecked)


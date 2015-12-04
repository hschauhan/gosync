import configobj
import os
import sys
import wx
from wx.lib.buttons import GenBitmapTextButton
from defines import *

def createConfig():
    """
    Create the configuration file
    """
    config = configobj.ConfigObj()
    config.filename = INI_FILE
    config['LocalSyncDirectory'] = os.path.join(os.getenv("HOME"), "gosync")
    config.write()

def getConfig():
    """
    Open the config file and return a configobj
    """
    if not os.path.exists(INI_FILE):
        createConfig()
    return configobj.ConfigObj(INI_FILE)

class GoSyncPreferenceDialog(wx.Dialog):
    """
    Create a preference panel to get some required settings
    from user.
    """

    def __init__(self):
        wx.Dialog.__init__(self, None, wx.ID_ANY, 'GoSync Preferences', size=(600,230))

        font = wx.Font(11, wx.SWISS, wx.NORMAL, wx.NORMAL)
        localSyncDirLabel = wx.StaticText(self, wx.ID_ANY, "Local Folder:")
        self.userHome = "%s/gosync" % os.getenv("HOME")
        self.localSyncDirText = wx.TextCtrl(self, wx.ID_ANY, self.userHome)
        self.localSyncDirBrowseBtn = wx.Button(self, wx.ID_ANY, 'Browse')
        self.localSyncDirBrowseBtn.Bind(wx.EVT_BUTTON, self.onLocalBrowse)

        serverSyncDirLabel = wx.StaticText(self, wx.ID_ANY, "Server Folder(s):")
        self.serverSyncDirText = wx.TextCtrl(self, wx.ID_ANY, 'root')
        self.serverSyncDirBrowseBtn = wx.Button(self, wx.ID_ANY, 'Browse')
        self.serverSyncDirBrowseBtn.Bind(wx.EVT_BUTTON, self.onServerBrowse)

        self.syncRuleBox = wx.StaticBox(self, -1, 'Sync Rules', (5, 5), size=(590,50))
        self.serverDeleteLocalDelete = wx.CheckBox(self, -1, 'Delete locally if deleted on server.', (15, 30))
        self.localDeleteServerDelete = wx.CheckBox(self, -1, 'Delete on server when deleted locally.', (15,30))

        #widgets = [localSyncDirLabel, self.localSyncDirText, serverSyncDirLabel, self.serverSyncDirText]

        #for widget in widgets:
        #    widget.SetFont(font)

        #img = wx.Bitmap(r"%s/resources/filesave.png" % APP_PATH)
        #saveBtn = GenBitmapTextButton(self, wx.ID_ANY, img, "Save", size=(110, 50))
        saveBtn = wx.Button(self, wx.ID_SAVE, 'Save')
        saveBtn.Bind(wx.EVT_BUTTON, self.savePreferences)
        #cancelBtn = CloseBtn(self, label="Cancel")
        cancelBtn = wx.Button(self, wx.ID_CANCEL, 'Cancel')
        cancelBtn.Bind(wx.EVT_BUTTON, self.onCancel)

        # LAYOUT
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        btnSizer = wx.BoxSizer(wx.HORIZONTAL)
        ruleBoxSizer = wx.StaticBoxSizer(self.syncRuleBox, wx.VERTICAL)
        prefSizer = wx.FlexGridSizer(cols=3, hgap=5, vgap=5)
        prefSizer.AddGrowableCol(1)

        prefSizer.Add(localSyncDirLabel, 0, wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
        prefSizer.Add(self.localSyncDirText, 0, wx.EXPAND)
        prefSizer.Add(self.localSyncDirBrowseBtn, 0)

        prefSizer.Add(serverSyncDirLabel, 0, wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
        prefSizer.Add(self.serverSyncDirText, 0, wx.EXPAND)
        prefSizer.Add(self.serverSyncDirBrowseBtn, 0)

        ruleBoxSizer.Add(self.serverDeleteLocalDelete, 0, wx.EXPAND)
        ruleBoxSizer.Add(self.localDeleteServerDelete, 0, wx.EXPAND)

        mainSizer.Add(prefSizer, 0, wx.EXPAND|wx.ALL, 5)
        mainSizer.Add(ruleBoxSizer, 0, wx.EXPAND|wx.ALL, 10)
        btnSizer.Add(saveBtn, 0, wx.ALL, 5)
        btnSizer.Add(cancelBtn, 0, wx.ALL, 5)
        mainSizer.Add(btnSizer, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        self.SetSizer(mainSizer)

        # ---------------------------------------------------------------------
        # load preferences
        self.loadPreferences()


    def loadPreferences(self):
        """
        Load the preferences and fill the text controls
        """
        config = getConfig()
        localSyncDir = config['LocalSyncDirectory']
        self.localSyncDirText.SetValue(localSyncDir)

    def onLocalBrowse(self, event):
        browseDialog = wx.DirDialog(None, "Choose a directory:",
                                    style = wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        if browseDialog.ShowModal() == wx.ID_OK:
            self.localSyncDirText.SetValue(browseDialog.GetPath())
        browseDialog.Destroy()

    def onServerBrowse(self, event):
        print "someting\n"

    def onCancel(self, event):
        """
        Closes the dialog
        """
        self.EndModal(0)

    def savePreferences(self, event):
        """
        Save the preferences
        """
        config = getConfig()

        config['local_sync_dir'] = self.localSyncDirText.GetValue()
        config.write()

        dlg = wx.MessageDialog(self, "Preferences Saved!", 'Information',
                               wx.OK|wx.ICON_INFORMATION)
        dlg.ShowModal()

        self.EndModal(0)

if __name__ == "__main__":
    app = wx.PySimpleApp()
    dlg = GoSyncPreferenceDialog()
    dlg.ShowModal()
    dlg.Destroy()

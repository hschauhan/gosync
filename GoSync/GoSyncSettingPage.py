import wx, subprocess, sys
#import wx.lib.agw.customtreectrl as CT
#from pydrive.drive import GoogleDrive
#from pydrive.auth import GoogleAuth
try :
    from .GoSyncEvents import *
except (ImportError, ValueError):
    from GoSyncEvents import *

sync_help = "GoSync monitors the local mirror directory for any changes like Add, Move, Delete. These changes are immediately reflected your Google Drive. But the sync from the Google Drive is done on a periodic basis. Below you can change the interval at which the remote Drive is sync'ed locally. More aggressive adds more network traffic."

class SettingsPage(wx.Panel):
    def __init__(self, parent, sync_model):
        wx.Panel.__init__(self, parent, style=wx.RAISED_BORDER)

        headerFont = wx.Font(11.5, wx.SWISS, wx.NORMAL, wx.FONTWEIGHT_NORMAL)

        self.sync_model = sync_model

        self.cb = wx.CheckBox(self, -1, 'Start sync at launch', (10, 10))
        self.cb.SetValue(True)
        self.cb.Bind(wx.EVT_CHECKBOX, self.AutoSyncSetting)

        self.md = wx.StaticText(self, -1, self.sync_model.GetLocalMirrorDirectory(), pos=(0,0))
        self.md.SetFont(headerFont)
        self.md_button = wx.Button(self, -1, "Change")
        self.show_button = wx.Button(self, -1, "Open Mirror Directory")
        self.show_button.Bind(wx.EVT_BUTTON, self.OnOpenMirror)
        self.md_button.Bind(wx.EVT_BUTTON, self.OnChangeMirror)

        ssizer = wx.StaticBoxSizer(wx.VERTICAL, self, "Local Mirror Directory")
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        osizer = wx.StaticBoxSizer(wx.VERTICAL, self, "Other Settings")

        si_sizer = wx.BoxSizer(wx.HORIZONTAL)

        button_sizer.Add(self.md_button, 1, wx.ALL|wx.ALIGN_CENTER, border=5)
        button_sizer.Add(self.show_button, 2, wx.ALL|wx.ALIGN_CENTER)

        ssizer.Add(self.md, 0, wx.ALL, border=10)
        ssizer.AddSpacer(10)
        ssizer.Add(button_sizer, 1, wx.ALL|wx.ALIGN_CENTER)

        osizer.Add(self.cb, 0, wx.ALL|wx.EXPAND, border=5)
        osizer.Add(si_sizer, 2, wx.ALL)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.AddSpacer(10)
        sizer.Add(ssizer, 0, wx.EXPAND|wx.ALL)
        sizer.AddSpacer(20)
        sizer.Add(osizer, 1, wx.ALL|wx.EXPAND)
        sizer.AddSpacer(5)
        self.SetSizerAndFit(sizer)
        self.cb.SetValue(self.sync_model.GetAutoSyncState())

    def AutoSyncSetting(self, event):
        if self.cb.GetValue():
            self.sync_model.EnableAutoSync()
        else:
            self.sync_model.DisableAutoSync()

    def OnOpenMirror(self, event):
        subprocess.check_call(['xdg-open', self.sync_model.GetLocalMirrorDirectory()])

    def OnChangeMirror(self, event):
        new_dir_help = "Your new local mirror directory is set. This will take effect after GoSync restart.\n\nPlease note that GoSync hasn't moved your files from old location. You would need to copy or move your current directory to new location before restarting GoSync."

        dlg = wx.DirDialog(None, "Choose target directory", "",
                           wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)

        if dlg.ShowModal() == wx.ID_OK:
            self.sync_model.SetLocalMirrorDirectory(dlg.GetPath())
            resp = wx.MessageBox(new_dir_help, "IMPORTANT INFORMATION", (wx.OK | wx.ICON_WARNING))
            

        dlg.Destroy()


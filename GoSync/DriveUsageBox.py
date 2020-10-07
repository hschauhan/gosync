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

import wx, math
import sys
if sys.version_info > (3,):
    long = int


class DriveUsageBox(wx.Panel):
    def __init__(self, parent, drive_size_bytes, id=wx.ID_ANY):
        wx.Panel.__init__(self, parent, id=wx.ID_ANY, size=parent.GetSize())

        font = wx.Font(10, wx.SWISS, wx.NORMAL, wx.NORMAL)

        bar_size = (parent.GetSize()[0], 20)
        self.barWidth = bar_size[0]+20
        self.barHeight = bar_size[1]
        self.bar_position = (parent.GetPosition()[0]+3, parent.GetPosition()[1]+3)
        self.photoSize = 0
        self.moviesSize = 0
        self.audioSize = 0
        self.otherSize = 0
        self.documentSize = 0

        legendSize = (15,10)
        legendStyle = wx.BORDER_RAISED

        self.drive_size_bytes = drive_size_bytes

        self.t1 = wx.StaticText(self, -1, "Your Google Drive usage is shown below:\n", (0,0), size=(200,20))
        self.t1.SetFont(font)

        #self.basePanel = wx.Panel(self, id, self.bar_position, bar_size, wx.SUNKEN_BORDER)
        self.basePanel = wx.Panel(self, wx.ID_ANY, style=wx.SUNKEN_BORDER)

        self.audioPanel = wx.Panel(self.basePanel, wx.ID_ANY, size=(self.barWidth, self.barHeight))
        self.moviesPanel = wx.Panel(self.basePanel, wx.ID_ANY, size=(self.barWidth, self.barHeight))
        self.documentPanel = wx.Panel(self.basePanel, wx.ID_ANY, size=(self.barWidth, self.barHeight))
        self.photoPanel = wx.Panel(self.basePanel, wx.ID_ANY, size=(self.barWidth, self.barHeight))
        self.othersPanel = wx.Panel(self.basePanel, wx.ID_ANY, size=(self.barWidth, self.barHeight))

        self.basePanel.SetBackgroundColour(wx.WHITE)

        self.audioPanelWidth = 0
        self.moviesPanelWidth = 0
        self.documentPanelWidth = 0
        self.othersPanelWidth = 0
        self.photoPanelWidth = 0

        self.audioPanelColor = wx.Colour(255,255,51)
        self.moviesPanelColor = wx.Colour(0, 204, 0)
        self.documentPanelColor = wx.Colour(153,0,153)
        self.othersPanelColor = wx.Colour(255,204,204)
        self.photoPanelColor = wx.Colour(255,85, 0)

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        mainSizer.Add(self.t1, 0, wx.ALL|wx.EXPAND, 5)
        #mainSizer.Add(self.basePanel, 0, wx.ALL|wx.FIXED_MINSIZE, 5)
        mainSizer.Add(self.basePanel, 0, wx.ALL|wx.EXPAND, 10)

        legendAudio = wx.Panel(self, size=legendSize, style=legendStyle)
        legendAudio.SetBackgroundColour(self.audioPanelColor)
        self.legendAudioText = wx.StaticText(self, -1, "", size=(200,20))
        self.legendAudioText.SetFont(font)

        legendMovies = wx.Panel(self, size=legendSize, style=legendStyle)
        legendMovies.SetBackgroundColour(self.moviesPanelColor)
        self.legendMoviesText = wx.StaticText(self, -1, "", size=(200,20))
        self.legendMoviesText.SetFont(font)

        legendDocument = wx.Panel(self, size=legendSize, style=legendStyle)
        legendDocument.SetBackgroundColour(self.documentPanelColor)
        self.legendDocumentText = wx.StaticText(self, -1, "", size=(200,20))
        self.legendDocumentText.SetFont(font)

        legendOthers = wx.Panel(self, size=legendSize, style=legendStyle)
        legendOthers.SetBackgroundColour(self.othersPanelColor)
        self.legendOthersText = wx.StaticText(self, -1, "", size=(200,20))
        self.legendOthersText.SetFont(font)

        legendPhoto = wx.Panel(self, size=legendSize, style=legendStyle)
        legendPhoto.SetBackgroundColour(self.photoPanelColor)
        self.legendPhotoText = wx.StaticText(self, -1, "", size=(200,20))
        self.legendPhotoText.SetFont(font)

        legendFree = wx.Panel(self, size=legendSize, style=legendStyle)
        legendFree.SetBackgroundColour(wx.WHITE)
        legendFreeText = wx.StaticText(self, -1, "Free Space")
        legendFreeText.SetFont(font)

        legendSizer = wx.FlexGridSizer(cols=4, hgap=5, vgap=5)
        legendSizer.AddGrowableCol(1)

        legendSizer.Add(legendAudio, 0, wx.ALL|wx.EXPAND, 5)
        legendSizer.Add(self.legendAudioText, 0, wx.ALL|wx.EXPAND, 5)

        legendSizer.Add(legendMovies, 0, wx.ALL|wx.EXPAND, 5)
        legendSizer.Add(self.legendMoviesText, 0, wx.ALL|wx.EXPAND, 5)

        legendSizer.Add(legendPhoto, 0 , wx.ALL|wx.EXPAND, 5)
        legendSizer.Add(self.legendPhotoText, 0, wx.ALL|wx.EXPAND, 5)

        legendSizer.Add(legendDocument, 0, wx.ALL|wx.EXPAND, 5)
        legendSizer.Add(self.legendDocumentText, 0, wx.ALL|wx.EXPAND, 5)

        legendSizer.Add(legendOthers, 0, wx.ALL|wx.EXPAND, 5)
        legendSizer.Add(self.legendOthersText, 0, wx.ALL|wx.EXPAND, 5)

        legendSizer.Add(legendFree, 0, wx.ALL|wx.EXPAND, 5)
        legendSizer.Add(legendFreeText, 0, wx.ALL|wx.EXPAND, 5)

        mainSizer.Add(legendSizer, 1, wx.ALL|wx.EXPAND, 10)
        self.SetSizerAndFit(mainSizer)

    def FileSizeHumanize(self, size):
        size = abs(size)
        if (size==0):
            return "0B"
        units = [' B',' KB',' MB',' GB',' TB',' PB',' EB',' ZB',' YB']
        p = math.floor(math.log(size, 2)/10)
        return "%.3f%s" % (size/math.pow(1024,p),units[long(p)])

    def SetStatusMessage(self, msg):
        self.t1.SetLabel(msg)

    def SetAudioUsageColor(self, color):
        self.audioPanelColor = color

    def SetMoviesUsageColor(self, color):
        self.moviesPanelColour = color

    def SetDocumentUsageColor(self, color):
        self.documentPanelColor = color

    def SetOthersUsageColor(self, color):
        self.othersPanelColor = color

    def SetAudioUsage(self, size):
        self.audioPanelWidth = float((float(size) * 100)/self.drive_size_bytes)
        self.legendAudioText.SetLabel('Audio ' + self.FileSizeHumanize(size))

    def SetMoviesUsage(self, size):
        self.moviesPanelWidth = float((float(size) * 100)/self.drive_size_bytes)
        self.legendMoviesText.SetLabel('Videos ' + self.FileSizeHumanize(size))

    def SetPhotoUsage(self, size):
        self.photoPanelWidth = float((float(size) * 100)/self.drive_size_bytes)
        self.legendPhotoText.SetLabel('Photos ' + self.FileSizeHumanize(size))

    def SetDocumentUsage(self, size):
        self.documentPanelWidth = float((float(size) * 100)/self.drive_size_bytes)
        self.legendDocumentText.SetLabel('Documents ' + self.FileSizeHumanize(size))

    def SetOthersUsage(self, size):
        self.othersPanelWidth = float((float(size) * 100)/self.drive_size_bytes)
        self.legendOthersText.SetLabel('Others ' + self.FileSizeHumanize(size))

    def RePaint(self):
        panelList = [(self.audioPanel, self.audioPanelWidth, self.audioPanelColor),
                     (self.photoPanel, self.photoPanelWidth, self.photoPanelColor),
                     (self.moviesPanel, self.moviesPanelWidth, self.moviesPanelColor),
                     (self.documentPanel, self.documentPanelWidth, self.documentPanelColor),
                     (self.othersPanel, self.othersPanelWidth, self.othersPanelColor)]

        cpos = 0
        for ctuple in panelList:
            #pwidth = (self.barWidth * ctuple[1])/100
            pwidth = (self.GetSize()[0] * ctuple[1])/100
            if (pwidth < 0):
                pwidth = 0

            #print "pcent: %f width: %d pwidth: %d\n" % (ctuple[1], self.barWidth, pwidth)
            ctuple[0].SetBackgroundColour(ctuple[2])
            ctuple[0].SetSize((0,0))
            ctuple[0].SetSize((pwidth, self.barHeight))
            ctuple[0].SetPosition((cpos,0))
            cpos += pwidth

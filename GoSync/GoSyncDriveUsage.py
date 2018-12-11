# GoSync is an open source Google Drive(TM) sync application for Linux
#
# Copyright (C) 2018 Himanshu Chauhan
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

import gi, enum
gi.require_version('Gtk', '3.0')

import os, time, sys, ntpath, threading, math, webbrowser, platform, datetime, cairo
from gi.repository import Gtk, GdkPixbuf
from GoSyncModel import GoSyncModel, ClientSecretsNotFound, ConfigLoadFailed, AuthenticationFailed
from defines import *

class GoSyncLegendSquare(Gtk.DrawingArea):
        def __init__(self, w, h, r=0.0, g=0.0, b=0.0):
                super(GoSyncLegendSquare, self).__init__()
                self.r = r
                self.g = g
                self.b = b
                self.w = w
                self.h = h
                self.connect("draw", self.on_legend_draw)

        def on_legend_draw(self, wid, cr):
                cr.set_source_rgb(self.r, self.g, self.b)
                cr.rectangle(0, 0, self.w, self.h)
                cr.set_line_join(cairo.LINE_JOIN_MITER)
                cr.stroke
                cr.fill()

class GoSyncAudioLegendSquare(GoSyncLegendSquare):
        def __init__(self, w, h):
                super(GoSyncAudioLegendSquare, self).__init__(w, h, r=0.9, g=0.9, b=0.2)

class GoSyncMovieLegendSquare(GoSyncLegendSquare):
        def __init__(self, w, h):
                super(GoSyncMovieLegendSquare, self).__init__(w, h, r=0.0, g=0.8, b=0.0)

class GoSyncDocumentLegendSquare(GoSyncLegendSquare):
        def __init__(self, w, h):
                super(GoSyncDocumentLegendSquare, self).__init__(w, h, r=0.6, g=0.0, b=0.6)

class GoSyncPhotoLegendSquare(GoSyncLegendSquare):
        def __init__(self, w, h):
                super(GoSyncPhotoLegendSquare, self).__init__(w, h, r=0.99, g=0.33, b=0.0)

class GoSyncOtherLegendSquare(GoSyncLegendSquare):
        def __init__(self, w, h):
                super(GoSyncOtherLegendSquare, self).__init__(w, h, r=0.0, g=0.9, b=0.9)

class GoSyncLegendType(enum.Enum):
        AUDIO=1
        MOVIE=2
        DOCUMENT=3
        PHOTO=4
        OTHER=5

class GoSyncLegend(Gtk.Box):
        def __init__(self, type, usage="Invalid", ls=6):
                super(GoSyncLegend, self).__init__(spacing=ls)
                w = 20
                h = 20

                if type == GoSyncLegendType.AUDIO:
                        self.legend_square = GoSyncAudioLegendSquare(w, h)
                        self.label_text = "Audio: %s"
                elif type == GoSyncLegendType.MOVIE:
                        self.legend_square = GoSyncMovieLegendSquare(w, h)
                        self.label_text = "Movie: %s"
                elif type == GoSyncLegendType.DOCUMENT:
                        self.legend_square = GoSyncDocumentLegendSquare(w, h)
                        self.label_text = "Document: %s"
                elif type == GoSyncLegendType.PHOTO:
                        self.legend_square = GoSyncPhotoLegendSquare(w, h)
                        self.label_text = "Photos: %s"
                else:
                        self.legend_square = GoSyncOtherLegendSquare(w, h)
                        self.label_text = "Others: %s"

                self.label = Gtk.Label(self.label_text % usage)
                self.pack_start(self.legend_square, True, True, 0)
                self.pack_start(self.label, False, False, 0)

                
                        
class GoSyncDriveUsageWindowGTK(Gtk.Window):
	def __init__(self, sync_model=None):
		self.sync_model = sync_model

		Gtk.Window.__init__(self, title="Categorical Drive Usage")

                darea = Gtk.DrawingArea()
                darea.connect("draw", self.on_draw)
                vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
                self.add(vbox)

                w, h = self.get_size()
                self.resize(400, 250)
                self.set_position(Gtk.WindowPosition.CENTER)

                self.quota = self.sync_model.GetTotalQuota()
                self.audio_size = self.sync_model.GetAudioUsage()
                self.movie_size = self.sync_model.GetMovieUsage()
                self.document_size = self.sync_model.GetDocumentUsage()
                self.photo_size = self.sync_model.GetPhotoUsage()
                self.other_size = self.sync_model.GetOthersUsage()

                self.audio_percent = (float(self.audio_size))/self.quota
                self.movie_percent = (float(self.movie_size))/self.quota
                self.document_percent = (float(self.document_size))/self.quota
                self.photo_percent = (float(self.photo_size))/self.quota
                self.other_percent = (float(self.other_size))/self.quota
                self.set_default_size(w, h)
		self.set_border_width(10)


                event_box = Gtk.EventBox()
                event_box.add(darea)
                vbox.pack_start(event_box, True, True, 0)

                als = GoSyncLegend(GoSyncLegendType.AUDIO, self.FileSizeHumanize(self.audio_size), ls=1)
                vbox.pack_start(als, False, True, 0)
                pls = GoSyncLegend(GoSyncLegendType.PHOTO, self.FileSizeHumanize(self.photo_size), ls=1)
                vbox.pack_start(pls, False, True, 0)
                mls = GoSyncLegend(GoSyncLegendType.MOVIE, self.FileSizeHumanize(self.movie_size), ls=1)
                vbox.pack_start(mls, False, True, 0)
                dls = GoSyncLegend(GoSyncLegendType.DOCUMENT, self.FileSizeHumanize(self.document_size), ls=1)
                vbox.pack_start(dls, False, True, 0)
                ols = GoSyncLegend(GoSyncLegendType.OTHER, self.FileSizeHumanize(self.other_size), ls=1)
                vbox.pack_start(ols, False, True, 0)

                self.show_all()


        def on_draw(self, wid, cr):
                cr.set_line_width(90)
                w, h = self.get_size()
                audio_width = self.audio_percent * w
                movie_width = self.movie_percent * w
                document_width = self.document_percent * w
                photo_width = self.photo_percent * w
                other_width = self.other_percent * w

                #White for free
                cr.set_source_rgb(0.9, 0.9, 0.9)
                cr.rectangle(0, 0, w, 20)
                cr.set_line_join(cairo.LINE_JOIN_MITER)
                cr.stroke
                cr.fill()

                #Orange for Photos
                running_x = 0
                cr.set_source_rgb(0.99, 0.33, 0.0)
                cr.rectangle(running_x, 0, photo_width, 20)
                cr.set_line_join(cairo.LINE_JOIN_MITER)
                cr.stroke
                cr.fill()

                #Green for Movies
                running_x += photo_width
                cr.set_source_rgb(0.0, 0.8, 0.0)
                cr.rectangle(running_x, 0, movie_width, 20)
                cr.set_line_join(cairo.LINE_JOIN_MITER)
                cr.stroke
                cr.fill()

                #Purple for documents
                cr.set_source_rgb(0.6, 0.0, 0.6)
                running_x += movie_width
                cr.rectangle(running_x, 0, document_width, 20)
                cr.set_line_join(cairo.LINE_JOIN_MITER)
                cr.stroke
                cr.fill()

                #Yellow for Audio
                cr.set_source_rgb(0.9, 0.9, 0.2)
                running_x += document_width
                cr.rectangle(running_x, 0, audio_width, 20)
                cr.set_line_join(cairo.LINE_JOIN_MITER)
                cr.stroke
                cr.fill()

                #Pink for others
                cr.set_source_rgb(0.0, 0.9, 0.9)
                running_x += audio_width
                cr.rectangle(running_x, 0, other_width, 20)
                cr.set_line_join(cairo.LINE_JOIN_MITER)
                cr.stroke
                cr.fill()

        def FileSizeHumanize(self, size):
		size = abs(size)
		if (size==0):
			return "0B"
		units = ['B','KB','MB','GB','TB','PB','EB','ZB','YB']
		p = math.floor(math.log(size, 2)/10)
		return "%.3f%s" % (size/math.pow(1024,p),units[int(p)])

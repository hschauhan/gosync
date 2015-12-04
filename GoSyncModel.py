# gosync is an open source google drive sync application for Linux
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

import sys, os, wx, ntpath, defines, threading, hashlib, time
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from os.path import expanduser
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from threading import Thread

class FileNotFound(RuntimeError):
    """File was not found on google drive"""
class FolderNotFound(RuntimeError):
    """Folder on Google Drive was not found"""
class UnknownError(RuntimeError):
    """Unknown/Unexpected error happened"""
class MD5ChecksumCalculationFailed(RuntimeError):
    """Calculation of MD5 checksum on a given file failed"""
class RegularFileUploadFailed(RuntimeError):
    """Upload of a regular file failed"""

class GoSyncModel(object):
    def __init__(self):
        self.config_path = expanduser("~") + "/.gosync"
        self.credential_file = self.config_path + "/.credentials.json"
        self.do_sync = True
        self.settings_file = os.path.dirname(os.path.realpath(__file__)) + "/settings.yaml"
        self.mirror_directory = expanduser("~") + "/gosync-drive"
        if not os.path.exists(self.config_path):
            os.mkdir(self.config_path, 0755)

        if not os.path.exists(self.mirror_directory):
            os.mkdir(self.mirror_directory, 0755)

        if not os.path.isfile(self.settings_file):
            sfile = open(self.settings_file, 'w')
            sfile.write("save_credentials: True")
            sfile.write("\n")
            sfile.write("save_credentials_file: ")
            sfile.write(self.credential_file)
            sfile.write("\n")
            sfile.write("client_config_file: .client_secrets.json\n")
            sfile.write("save_credentials_backend: file\n")
            sfile.close()


        self.observer = Observer()
        self.DoAuthenticate()
        self.sync_thread = threading.Thread(target=self.run)
        self.sync_thread.daemon = True
        self.cancelRunningSync = True
        self.sync_thread.start()
        self.sync_lock = threading.Lock()

        self.observer.start()

    def IsUserLoggedIn(self):
        return self.is_logged_in

    def HashOfFile(self, abs_filepath):
        data = open(abs_filepath, "r").read()
        return hashlib.md5(data).hexdigest()

    def DoAuthenticate(self):
        try:
            self.authToken = GoogleAuth()
            self.authToken.LocalWebserverAuth()
            self.drive = GoogleDrive(self.authToken)
            self.is_logged_in = True
            self.iobserv_handle = self.observer.schedule(FileModificationNotifyHandler(self),
                                                         self.mirror_directory, recursive=True)
        except:
            dial = wx.MessageDialog(None, "Authentication Rejected!\n",
                                    'Information', wx.ID_OK | wx.ICON_EXCLAMATION)
            dial.ShowModal()
            self.is_logged_in = False
            pass

    def DoUnAuthenticate(self):
            self.do_sync = False
            self.observer.unschedule(self.iobserv_handle)
            self.iobserv_handle = None
            os.remove(self.credential_file)
            self.is_logged_in = False

    def DriveInfo(self):
        return self.authToken.AboutDrive()

    def PathLeaf(self, path):
        head, tail = ntpath.split(path)
        return tail or ntpath.basename(head)

    def GetFolderOnDrive(self, folder_name, parent='root'):
        """
        Return the folder with name in "folder_name" in the parent folder
        mentioned in parent.
        """
        print "GetFolderOnDrive: searching %s on %s... " % (folder_name, parent)
        file_list = self.drive.ListFile({'q': "'%s' in parents and trashed=false" % parent}).GetList()
        for f in file_list:
            if f['title'] == folder_name and f['mimeType']=='application/vnd.google-apps.folder':
                print "Found!\n"
                return f

        print "Not found\n"
        return None

    def LocateFolderOnDrive(self, folder_path):
        """
        Locate and return the directory in the path. The complete path
        is walked and the last directory is returned. An exception is raised
        if the path walking fails at any stage.
        """
        dir_list = folder_path.split(os.sep)
        print dir_list
        croot = 'root'
        for dir1 in dir_list:
            print dir1
            folder = self.GetFolderOnDrive(dir1, croot)
            if not folder:
                raise FolderNotFound()

            croot = folder['id']

        return folder

    def LocateFileInFolder(self, filename, parent='root'):
        file_list = self.drive.ListFile({'q': "'%s' in parents and trashed=false" % parent}).GetList()
        for f in file_list:
            if f['title'] == filename:
                print "found file %s in %s\n" % (filename, parent)
                return f

        raise FileNotFound()

    def LocateFileOnDrive(self, abs_filepath):
        dirpath = os.path.dirname(abs_filepath)
        filename = self.PathLeaf(abs_filepath)
        print "LocateFileOnDrive: dirpath %s filename %s\n" % (dirpath, filename)
        try:
            f = self.LocateFolderOnDrive(dirpath)
            print "LocateFileOnDrive: Folder %s found\n" % dirpath
        except FolderNotFound:
            print "LocateFileOnDrive: Folder %s not found\n" % dirpath
            raise

        try:
            fil = self.LocateFileInFolder(filename, f['id'])
            print "LocateFileOnDrive: File %s found on %s\n" % (filename, f['id'])
            return fil
        except FileNotFound:
            print "LocateFileOnDrive: File %s not found\n" % filename
            raise

    def CreateDirectoryInParent(self, dirname, parent_id='root'):
        upfile = self.drive.CreateFile({'title': dirname,
                                        'mimeType': "application/vnd.google-apps.folder",
                                        "parents": [{"kind": "drive#fileLink", "id": parent_id}]})
        print "Creating directory by name %s\n" % dirname
        upfile.Upload()

    def CreateDirectoryByPath(self, dirpath):
        drivepath = dirpath.split(self.mirror_directory+'/')[1]
        basepath = os.path.dirname(drivepath)
        dirname = self.PathLeaf(dirpath)

        try:
            print "Locating %s on Drive\n" % drivepath
            f = self.LocateFolderOnDrive(drivepath)
            print "Folder %s already exists on Drive\n" % dirpath
            return
        except FolderNotFound:
            print "New folder %s\n" % dirpath
            if basepath == '':
                self.CreateDirectoryInParent(dirname)
            else:
                try:
                    parent_folder = self.LocateFolderOnDrive(basepath)
                    self.CreateDirectoryInParent(dirname, parent_folder['id'])
                except:
                    errorMsg = "Failed to locate directory path %s on drive.\n" % basepath
                    dial = wx.MessageDialog(None, errorMsg, 'Directory Not Found',
                                            wx.ID_OK | wx.ICON_EXCLAMATION)
                    dial.ShowModal()
                    return

    def CreateRegularFile(self, file_path, parent='root', uploaded=False):
        filename = self.PathLeaf(file_path)
        upfile = self.drive.CreateFile({'title': filename,
                                       "parents": [{"kind": "drive#fileLink", "id": parent}]})
        upfile.SetContentFile(file_path)
        print "uploading file %s\n" % file_path
        upfile.Upload()

    def UploadFile(self, file_path):
        self.sync_lock.acquire()
        if os.path.isfile(file_path):
            drivepath = file_path.split(self.mirror_directory+'/')[1]
            print "Uploadfile drive path: %s\n" % drivepath
            try:
                f = self.LocateFileOnDrive(drivepath)
                newfile = False
                if f['md5Checksum'] == self.HashOfFile(file_path):
                    print "File found on drive and is same.\n"
                    self.sync_lock.release()
                    return
                else:
                    print "File found on drive but hash don't match. modified?\n"
            except (FileNotFound, FolderNotFound):
                newfile = True
                print "File not found on drive new file.\n"

            dirpath = os.path.dirname(drivepath)
            if dirpath == '':
                self.CreateRegularFile(file_path, 'root', newfile)
            else:
                try:
                    f = self.LocateFolderOnDrive(dirpath)
                    print "Found folder %s id %s\n" % (f['title'], f['id'])
                    self.CreateRegularFile(file_path, f['id'], newfile)
                except FolderNotFound:
                    # We are coming from premise that upload comes as part
                    # of observer. So before notification of this file's
                    # creation happens, a notification of its parent directory
                    # must have come first.
                    # So,
                    # Folder not found? That cannot happen. Can it?
                    raise RegularFileUploadFailed()
        else:
            self.CreateDirectoryByPath(file_path)
        self.sync_lock.release()

    ####### DOWNLOAD SECTION #######
    def TotalFilesInFolder(self, parent='root'):
        file_count = 0
        file_list = self.drive.ListFile({'q': "'%s' in parents and trashed=false" % parent}).GetList()
        for f in file_list:
            if f['mimeType'] == 'application/vnd.google-apps.folder':
                file_count += self.TotalFilesInFolder(f['id'])
            else:
                file_count += 1

        return file_count

    def IsGoogleDocument(self, file_obj):
        if file_obj['mimeType'] == 'application/vnd.google-apps.spreadsheet' \
                or file_obj['mimeType'] == 'application/vnd.google-apps.sites' \
                or file_obj['mimeType'] == 'application/vnd.google-apps.script' \
                or file_obj['mimeType'] == 'application/vnd.google-apps.presentation' \
                or file_obj['mimeType'] == 'application/vnd.google-apps.fusiontable' \
                or file_obj['mimeType'] == 'application/vnd.google-apps.form' \
                or file_obj['mimeType'] == 'application/vnd.google-apps.drawing' \
                or file_obj['mimeType'] == 'application/vnd.google-apps.document':
            return True
        else:
            return False

    def TotalFilesInDrive(self):
        return TotalFilesInFolder()

    def DownloadFileByObject(self, file_obj, download_path):
        dfile = self.drive.CreateFile({'id': file_obj['id']})
        abs_filepath = os.path.join(download_path, file_obj['title'])
        abs_filepath.replace(' ', '\ ')
        if os.path.exists(abs_filepath):
            if self.HashOfFile(abs_filepath) == file_obj['md5Checksum']:
                return
        else:
            print "Downloading file %s\n" % abs_filepath
            dfile.GetContentFile(abs_filepath)

    def SyncDirectory(self, parent, pwd):
        if self.cancelRunningSync:
            return

        file_list = self.drive.ListFile({'q': "'%s' in parents and trashed=false" % parent}).GetList()
        for f in file_list:
            if self.cancelRunningSync:
                return

            if f['mimeType'] == 'application/vnd.google-apps.folder':
                abs_dirpath = os.path.join(self.mirror_directory, pwd, f['title'])
                if not os.path.exists(abs_dirpath):
                    os.makedirs(abs_dirpath)
                self.SyncDirectory(f['id'], os.path.join(pwd, f['title']))
            else:
                if not self.IsGoogleDocument(f):
                    self.DownloadFileByObject(f, os.path.join(self.mirror_directory, pwd))

    def run(self):
        while True:
            if not self.cancelRunningSync:
                self.sync_lock.acquire()
                self.SyncDirectory('root', '')
                self.sync_lock.release()
            time.sleep(10)

    def StartSync(self):
        self.cancelRunningSync = False

    def StopSync(self):
        self.cancelRunningSync = True

    def IsSyncEnabled(self):
        return not self.cancelRunningSync

class FileModificationNotifyHandler(PatternMatchingEventHandler):
    patterns = ["*"]

    def __init__(self, sync_handler):
        super(FileModificationNotifyHandler, self).__init__()
        self.sync_handler = sync_handler

    def on_created(self, evt):
        print "%s created\n" % evt.src_path
        self.sync_handler.UploadFile(evt.src_path)

    def on_moved(self, evt):
        print "file %s moved to %s: Not supported yet!\n" % (evt.src_path, evt.dest_path)

    def on_deleted(self, evt):
        print "file %s deleted: Not supported yet!\n" % (evt.src_path)

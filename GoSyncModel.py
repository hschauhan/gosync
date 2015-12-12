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
class FileListQueryFailed(RuntimeError):
    """The query of file list failed"""

audio_file_mimelist = ['audio/mpeg', 'audio/x-mpeg-3', 'audio/mpeg3', 'audio/aiff', 'audio/x-aiff']
movie_file_mimelist = ['video/mp4', 'video/x-msvideo', 'video/mpeg', 'video/flv', 'video/quicktime']
image_file_mimelist = ['image/png', 'image/jpeg', 'image/jpg', 'image/tiff']
document_file_mimelist = ['application/powerpoint', 'applciation/mspowerpoint', \
                              'application/x-mspowerpoint', 'application/pdf', \
                              'application/x-dvi']
google_docs_mimelist = ['application/vnd.google-apps.spreadsheet', \
                            'application/vnd.google-apps.sites', \
                            'application/vnd.google-apps.script', \
                            'application/vnd.google-apps.presentation', \
                            'application/vnd.google-apps.fusiontable', \
                            'application/vnd.google-apps.form', \
                            'application/vnd.google-apps.drawing', \
                            'application/vnd.google-apps.document', \
                            'application/vnd.google-apps.map']

class GoSyncModel(object):
    def __init__(self):
        self.calculatingDriveUsage = False
        self.driveAudioUsage = 0
        self.driveMoviesUsage = 0
        self.drivePhotoUsage = 0
        self.driveDocumentUsage = 0
        self.driveOthersUsage = 0
        self.totalFilesToCheck = 0

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
        self.about_drive = self.authToken.service.about().get().execute()
        self.sync_lock = threading.Lock()
        self.sync_thread = threading.Thread(target=self.run)
        self.usage_calc_thread = threading.Thread(target=self.calculateUsage)
        self.sync_thread.daemon = True
        self.usage_calc_thread.daemon = True
        self.cancelRunningSync = True
        self.sync_thread.start()
        self.usage_calc_thread.start()

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
        return self.about_drive

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

        return None

    def LocateFolderOnDrive(self, folder_path):
        """
        Locate and return the directory in the path. The complete path
        is walked and the last directory is returned. An exception is raised
        if the path walking fails at any stage.
        """
        dir_list = folder_path.split(os.sep)
        croot = 'root'
        for dir1 in dir_list:
            try:
                folder = self.GetFolderOnDrive(dir1, croot)
                if not folder:
                    raise FolderNotFound()
            except:
                raise

            croot = folder['id']

        return folder

    def LocateFileInFolder(self, filename, parent='root'):
        try:
            file_list = self.MakeFileListQuery({'q': "'%s' in parents and trashed=false" % parent})
            for f in file_list:
                if f['title'] == filename:
                    return f

            raise FileNotFound()
        except:
            raise


    def LocateFileOnDrive(self, abs_filepath):
        dirpath = os.path.dirname(abs_filepath)
        filename = self.PathLeaf(abs_filepath)
        try:
            f = self.LocateFolderOnDrive(dirpath)
        except FolderNotFound:
            raise
        except FileListQueryFailed:
            raise

        try:
            fil = self.LocateFileInFolder(filename, f['id'])
            return fil
        except FileNotFound:
            raise
        except FileListQueryFailed:
            raise

    def CreateDirectoryInParent(self, dirname, parent_id='root'):
        upfile = self.drive.CreateFile({'title': dirname,
                                        'mimeType': "application/vnd.google-apps.folder",
                                        "parents": [{"kind": "drive#fileLink", "id": parent_id}]})
        upfile.Upload()

    def CreateDirectoryByPath(self, dirpath):
        drivepath = dirpath.split(self.mirror_directory+'/')[1]
        basepath = os.path.dirname(drivepath)
        dirname = self.PathLeaf(dirpath)

        try:
            f = self.LocateFolderOnDrive(drivepath)
            return
        except FolderNotFound:
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
        except FileListQueryFailed:
            errorMsg = "Server Query Failed!\n"
            dial = wx.MessageDialog(None, errorMsg, 'Directory Not Found',
                                    wx.ID_OK | wx.ICON_EXCLAMATION)
            dial.ShowModal()
            return

    def CreateRegularFile(self, file_path, parent='root', uploaded=False):
        filename = self.PathLeaf(file_path)
        upfile = self.drive.CreateFile({'title': filename,
                                       "parents": [{"kind": "drive#fileLink", "id": parent}]})
        upfile.SetContentFile(file_path)
        upfile.Upload()

    def UploadFile(self, file_path):
        self.sync_lock.acquire()
        if os.path.isfile(file_path):
            drivepath = file_path.split(self.mirror_directory+'/')[1]
            try:
                f = self.LocateFileOnDrive(drivepath)
                newfile = False
                if f['md5Checksum'] == self.HashOfFile(file_path):
                    self.sync_lock.release()
                    return
            except (FileNotFound, FolderNotFound):
                newfile = True

            dirpath = os.path.dirname(drivepath)
            if dirpath == '':
                self.CreateRegularFile(file_path, 'root', newfile)
            else:
                try:
                    f = self.LocateFolderOnDrive(dirpath)
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
    def MakeFileListQuery(self, query):
        # Retry 5 times to get the query
        for n in range (0, 5):
            try:
                return self.drive.ListFile(query).GetList()
            except HttpError as error:
                if error.resp.reason in ['userRateLimitExceeded', 'quotaExceeded']:
                    time.sleep((2**n) + random.random())

        raise FileListQueryFailed

    def TotalFilesInFolder(self, parent='root'):
        file_count = 0
        try:
            file_list = self.MakeFileListQuery({'q': "'%s' in parents and trashed=false" % parent})
            for f in file_list:
                if f['mimeType'] == 'application/vnd.google-apps.folder':
                    file_count += self.TotalFilesInFolder(f['id'])
                else:
                    file_count += 1

            return file_count
        except:
            raise

    def IsGoogleDocument(self, f):
        if any(f['mimeType'] in s for s in google_docs_mimelist):
            return True
        else:
            return False

    def TotalFilesInDrive(self):
        return self.TotalFilesInFolder()

    def DownloadFileByObject(self, file_obj, download_path):
        dfile = self.drive.CreateFile({'id': file_obj['id']})
        abs_filepath = os.path.join(download_path, file_obj['title'])
        abs_filepath.replace(' ', '\ ')
        if os.path.exists(abs_filepath):
            if self.HashOfFile(abs_filepath) == file_obj['md5Checksum']:
                return
        else:
            dfile.GetContentFile(abs_filepath)

    def SyncDirectory(self, parent, pwd):
        if self.cancelRunningSync:
            return

        try:
            file_list = self.MakeFileListQuery({'q': "'%s' in parents and trashed=false" % parent})
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
        except:
            raise

    def run(self):
        while True:
            if not self.cancelRunningSync:
                self.sync_lock.acquire()
                self.SyncDirectory('root', '')
                self.sync_lock.release()
            time.sleep(10)

    def GetFileSize(self, f):
        try:
            size = f['fileSize']
            return long(size)
        except:
            print "Failed to get size of file %s (mime: %s)\n" % (f['title'], f['mimeType'])
            return 0

    def calculateUsageOfFolder(self, folder_id):
        try:
            file_list = self.MakeFileListQuery({'q': "'%s' in parents and trashed=false" % folder_id})
            for f in file_list:
                if f['mimeType'] == 'application/vnd.google-apps.folder':
                    self.calculateUsageOfFolder(f['id'])
                else:
                    if not self.IsGoogleDocument(f):
                        if any(f['mimeType'] in s for s in audio_file_mimelist):
                            self.driveAudioUsage += self.GetFileSize(f)
                        elif  any(f['mimeType'] in s for s in image_file_mimelist):
                            self.drivePhotoUsage += self.GetFileSize(f)
                        elif any(f['mimeType'] in s for s in movie_file_mimelist):
                            self.driveMoviesUsage += self.GetFileSize(f)
                        elif any(f['mimeType'] in s for s in document_file_mimelist):
                            self.driveDocumentUsage += self.GetFileSize(f)
                        else:
                            self.driveOthersUsage += self.GetFileSize(f)
        except:
            raise

    def calculateUsage(self):
        while True:
            self.sync_lock.acquire()
            self.calculatingDriveUsage = True
            self.driveAudioUsage = 0
            self.driveMoviesUsage = 0
            self.driveDocumentUsage = 0
            self.drivePhotoUsage = 0
            self.driveOthersUsage = 0
            try:
                self.totalFilesToCheck = self.TotalFilesInDrive()
                print "Total files to check %d\n" % self.totalFilesToCheck
            except:
                print "failed to get the total files in drive\n"

            try:
                self.calculateUsageOfFolder('root')
            except:
                self.driveAudioUsage = 0
                self.driveMoviesUsage = 0
                self.driveDocumentUsage = 0
                self.drivePhotoUsage = 0
                self.driveOthersUsage = 0

            self.calculatingDriveUsage = False
            self.sync_lock.release()
            time.sleep(300)

    def IsCalculatingDriveUsage(self):
        return self.calculatingDriveUsage

    def GetAudioUsage(self):
        return self.driveAudioUsage

    def GetMovieUsage(self):
        return self.driveMoviesUsage

    def GetDocumentUsage(self):
        return self.driveDocumentUsage

    def GetOthersUsage(self):
        return self.driveOthersUsage

    def GetPhotoUsage(self):
        return self.drivePhotoUsage

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

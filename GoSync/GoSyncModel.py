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

import sys, os, wx, ntpath, defines, threading, hashlib, time, copy
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from os.path import expanduser
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from threading import Thread
from apiclient.errors import HttpError
from apiclient import errors
import logging
from defines import *
from GoSyncEvents import *
from GoSyncDriveTree import GoogleDriveTree
import json, pickle

class ClientSecretsNotFound(RuntimeError):
    """Client secrets file was not found"""
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
class RegularFileTrashFailed(RuntimeError):
    """Could not move file to trash"""
class FileListQueryFailed(RuntimeError):
    """The query of file list failed"""
class ConfigLoadFailed(RuntimeError):
    """Failed to load the GoSync configuration file"""

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
        self.savedTotalSize = 0
        self.fcount = 0
        self.updates_done = 0

        self.config_path = os.path.join(os.environ['HOME'], ".gosync")
        self.credential_file = os.path.join(self.config_path, "credentials.json")
        self.settings_file = os.path.join(self.config_path, "settings.yaml")
        self.base_mirror_directory = os.path.join(os.environ['HOME'], "Google Drive")
        self.client_secret_file = os.path.join(os.environ['HOME'], '.gosync', 'client_secrets.json')
        self.sync_selection = []
        self.config_file = os.path.join(os.environ['HOME'], '.gosync', 'gosyncrc')
        self.config_dict = {}
        self.account_dict = {}
        self.drive_usage_dict = {}
        self.config=None
        self.creatingDriveTreeReplica = 0
        self.force_update_tree = 0

        if not os.path.exists(self.config_path):
            os.mkdir(self.config_path, 0755)
            raise ClientSecretsNotFound()

        if not os.path.exists(self.base_mirror_directory):
            os.mkdir(self.base_mirror_directory, 0755)

        if not os.path.exists(self.client_secret_file):
            raise ClientSecretsNotFound()

        if not os.path.exists(self.settings_file) or \
                not os.path.isfile(self.settings_file):
            sfile = open(self.settings_file, 'w')
            sfile.write("save_credentials: True")
            sfile.write("\n")
            sfile.write("save_credentials_file: ")
            sfile.write(self.credential_file)
            sfile.write("\n")
            sfile.write('client_config_file: ' + self.client_secret_file + "\n")
            sfile.write("save_credentials_backend: file\n")
            sfile.close()

        self.logger = logging.getLogger(APP_NAME)
        self.logger.setLevel(logging.INFO)
        fh = logging.FileHandler(os.path.join(os.environ['HOME'], 'GoSync.log'))
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

        self.observer = Observer()
        self.DoAuthenticate()
        self.about_drive = self.authToken.service.about().get().execute()
        self.user_email = self.about_drive['user']['emailAddress']

        self.mirror_directory = os.path.join(self.base_mirror_directory, self.user_email)
        if not os.path.exists(self.mirror_directory):
            os.mkdir(self.mirror_directory, 0755)

        self.tree_pickle_file = os.path.join(self.config_path, 'gtree-' + self.user_email + '.pick')

        if not os.path.exists(self.config_file):
            self.CreateDefaultConfigFile()

        try:
            self.LoadConfig()
        except:
            raise

        self.iobserv_handle = self.observer.schedule(FileModificationNotifyHandler(self),
                                                     self.mirror_directory, recursive=True)

        self.sync_lock = threading.Lock()
        self.sync_thread = threading.Thread(target=self.run)
        self.usage_calc_thread = threading.Thread(target=self.calculateUsage)
        self.drive_replica_thread = threading.Thread(target=self.CreateDriveTreeReplica)
        self.sync_thread.daemon = True
        self.usage_calc_thread.daemon = True
        self.drive_replica_thread.daemon = True
        self.syncRunning = threading.Event()
        self.syncRunning.clear()
        self.usageCalculateEvent = threading.Event()

        if not self.drive_usage_dict:
            self.logger.info("No drive tree usage found. Re-calculating...")
            self.usageCalculateEvent.set()
        else:
            self.logger.info("Found saved drive tree usage. Not calculating untils updates are done in the drive.")
            self.usageCalculateEvent.clear()

        self.calculateDriveTreeReplicaEvent = threading.Event()
        self.calculateDriveTreeReplicaEvent.clear()

        if not os.path.exists(self.tree_pickle_file):
            self.driveTree = GoogleDriveTree()
            self.calculateDriveTreeReplicaEvent.set()
            self.logger.info("Didn't find saved tree in configuration. Fetching remote tree structure")
        else:
            self.driveTree = pickle.load(open(self.tree_pickle_file, "rb"))
            self.logger.info("Loading saved drive tree")

    def StartServices(self):
        self.sync_thread.start()
        self.usage_calc_thread.start()
        self.observer.start()
        self.syncRunning.set()
        self.drive_replica_thread.start()

    def ShutdownServices(self):
        self.syncRunning.clear()
        self.usageCalculateEvent.clear()
        self.observer.stop()

    def IsUserLoggedIn(self):
        return self.is_logged_in

    def HashOfFile(self, abs_filepath):
        data = open(abs_filepath, "r").read()
        return hashlib.md5(data).hexdigest()

    def CreateDefaultConfigFile(self):
        f = open(self.config_file, 'w')
        self.config_dict['Sync Selection'] = [['root', '']]
        self.account_dict[self.user_email] = self.config_dict
        json.dump(self.account_dict, f)
        f.close()

    def LoadConfig(self):
        try:
            f = open(self.config_file, 'r')
            try:
                self.config = json.load(f)
                try:
                    self.config_dict = self.config[self.user_email]
                    self.sync_selection = self.config_dict['Sync Selection']
                    try:
                        self.drive_usage_dict = self.config_dict['Drive Usage']
                        self.totalFilesToCheck = self.drive_usage_dict['Total Files']
                        self.savedTotalSize = self.drive_usage_dict['Total Size']
                        self.driveAudioUsage = self.drive_usage_dict['Audio Size']
                        self.driveMoviesUsage = self.drive_usage_dict['Movies Size']
                        self.driveDocumentUsage = self.drive_usage_dict['Document Size']
                        self.drivePhotoUsage = self.drive_usage_dict['Photo Size']
                        self.driveOthersUsage = self.drive_usage_dict['Others Size']
                        self.logger.info("Loaded drive tree usage")
                        print self.drive_usage_dict
                    except:
                        self.logger.error("Failed to load drive tree usage. Forcing to recalculate")
                        self.drive_usage_dict = {}
                        pass
                except:
                    self.logger.error("Failed to load sync selection")
                    pass

                f.close()
            except:
                raise ConfigLoadFailed()
        except:
            raise ConfigLoadFailed()

    def SaveConfig(self):
        f = open(self.config_file, 'w')
        f.truncate()
        if not self.sync_selection:
            self.config_dict['Sync Selection'] = [['root', '']]

        self.account_dict[self.user_email] = self.config_dict

        json.dump(self.account_dict, f)
        f.close()

    def DoAuthenticate(self):
        try:
            self.authToken = GoogleAuth(self.settings_file)
            print "Generating auth token %s" % self.credential_file
            self.authToken.LoadCredentialsFile(self.credential_file)
            if self.authToken is None:
                print "Going for local webserver auth"
                self.authToken.LocalWebserverAuth()
            elif self.authToken.access_token_expired:
                print "Token expired. Refreshing token"
                self.authToken.Refresh()
            else:
                print "Authorizing with saved credentials"
                self.authToken.Authorize()

            print "Authorization done. Saving file"
            self.authToken.SaveCredentialsFile(self.credential_file)
            print "Authorization file saved"
            self.drive = GoogleDrive(self.authToken)
            self.is_logged_in = True
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
        self.logger.debug("GetFolderOnDrive: searching %s on %s... " % (folder_name, parent))
        file_list = self.drive.ListFile({'q': "'%s' in parents and trashed=false" % parent}).GetList()
        for f in file_list:
            if f['title'] == folder_name and f['mimeType']=='application/vnd.google-apps.folder':
                self.logger.debug("Found!\n")
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
            raise FileNotFound()


    def LocateFileOnDrive(self, abs_filepath):
        dirpath = os.path.dirname(abs_filepath)
        filename = self.PathLeaf(abs_filepath)

        if dirpath != '':
            try:
                f = self.LocateFolderOnDrive(dirpath)
                try:
                    fil = self.LocateFileInFolder(filename, f['id'])
                    return fil
                except FileNotFound:
                    self.logger.debug("LocateFileOnDrive: File not found.\n")
                    raise
                except FileListQueryFailed:
                    self.logger.debug("LocateFileOnDrive: File list query failed\n")
                    raise
            except FolderNotFound:
                self.logger.debug("LocateFileOnDrive: Folder not found\n")
                raise
            except FileListQueryFailed:
                self.logger.debug("LocateFileOnDrive:  %s folder not found\n" % dirpath)
                raise
        else:
            try:
                fil = self.LocateFileInFolder(filename)
                return fil
            except FileNotFound:
                self.logger.debug("LocateFileOnDrive: File not found.\n")
                raise
            except FileListQueryFailed:
                self.logger.debug("LocateFileOnDrive: File list query failed.\n")
                raise
            except:
                self.logger.error("LocateFileOnDrive: Unknown error in locating file in drive\n")
                raise

    def CreateDirectoryInParent(self, dirname, parent_id='root'):
        upfile = self.drive.CreateFile({'title': dirname,
                                        'mimeType': "application/vnd.google-apps.folder",
                                        "parents": [{"kind": "drive#fileLink", "id": parent_id}]})
        upfile.Upload()

    def CreateDirectoryByPath(self, dirpath):
        self.logger.debug("create directory: %s\n" % dirpath)
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
                    self.logger.error(errorMsg)
                    dial = wx.MessageDialog(None, errorMsg, 'Directory Not Found',
                                            wx.ID_OK | wx.ICON_EXCLAMATION)
                    dial.ShowModal()
                    return
        except FileListQueryFailed:
            errorMsg = "Server Query Failed!\n"
            self.logger.error(errorMsg)
            dial = wx.MessageDialog(None, errorMsg, 'Directory Not Found',
                                    wx.ID_OK | wx.ICON_EXCLAMATION)
            dial.ShowModal()
            return

    def CreateRegularFile(self, file_path, parent='root', uploaded=False):
        self.logger.debug("Create file %s\n" % file_path)
        filename = self.PathLeaf(file_path)
        upfile = self.drive.CreateFile({'title': filename,
                                       "parents": [{"kind": "drive#fileLink", "id": parent}]})
        upfile.SetContentFile(file_path)
        upfile.Upload()

    def UploadFile(self, file_path):
        if os.path.isfile(file_path):
            drivepath = file_path.split(self.mirror_directory+'/')[1]
            self.logger.debug("file: %s drivepath is %s\n" % (file_path, drivepath))
            try:
                f = self.LocateFileOnDrive(drivepath)
                self.logger.debug('Found file %s on remote (dpath: %s)\n' % (f['title'], drivepath))
                newfile = False
                self.logger.debug('Checking if they are same... ')
                if f['md5Checksum'] == self.HashOfFile(file_path):
                    self.logger.debug('yes\n')
                    return
                else:
                    self.logger.debug('no\n')
            except (FileNotFound, FolderNotFound):
                self.logger.debug("A new file!\n")
                newfile = True

            dirpath = os.path.dirname(drivepath)
            if dirpath == '':
                self.logger.debug('Creating %s file in root\n' % file_path)
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

    def UploadObservedFile(self, file_path):
        self.sync_lock.acquire()
        self.UploadFile(file_path)
        self.sync_lock.release()

    def RenameFile(self, file_object, new_title):
        try:
            file = {'title': new_title}

            updated_file = self.authToken.service.files().patch(fileId=file_object['id'],
                                                                body=file, fields='title').execute()
            return updated_file
        except errors.HttpError, error:
            self.logger.error('An error occurred while renaming file: %s' % error)
            return None
        except:
            self.logger.exception('An unknown error occurred file renaming file\n')
            return None

    def RenameObservedFile(self, file_path, new_name):
        self.sync_lock.acquire()
        drive_path = file_path.split(self.mirror_directory+'/')[1]
        self.logger.debug("RenameObservedFile: Rename %s to new name %s\n"
                          % (file_path, new_name))
        try:
            ftd = self.LocateFileOnDrive(drive_path)
            nftd = self.RenameFile(ftd, new_name)
            if not nftd:
                self.logger.error("File rename failed\n")
        except:
            self.logger.exception("Could not locate file on drive.\n")

        self.sync_lock.release()

    def TrashFile(self, file_object):
        try:
            self.authToken.service.files().trash(fileId=file_object['id']).execute()
            self.logger.info({"TRASH_FILE: File %s deleted successfully.\n" % file_object['title']})
        except errors.HttpError, error:
            self.logger.error("TRASH_FILE: HTTP Error\n")
            raise RegularFileTrashFailed()

    def TrashObservedFile(self, file_path):
        self.sync_lock.acquire()
        drive_path = file_path.split(self.mirror_directory+'/')[1]
        self.logger.debug({"TRASH_FILE: dirpath to delete: %s\n" % drive_path})
        try:
            ftd = self.LocateFileOnDrive(drive_path)
            try:
                self.TrashFile(ftd)
            except RegularFileTrashFailed:
                self.logger.error({"TRASH_FILE: Failed to move file %s to trash\n" % drive_path})
                raise
            except:
                raise
        except (FileNotFound, FileListQueryFailed, FolderNotFound):
            self.logger.error({"TRASH_FILE: Failed to locate %s file on drive\n" % drive_path})
            pass

        self.sync_lock.release()

    def MoveFile(self, src_file, dst_folder='root', src_folder='root'):
        try:
            if dst_folder != 'root':
                did = dst_folder['id']
            else:
                did = 'root'

            if src_folder != 'root':
                sid = src_folder['id']
            else:
                sid = 'root'

            updated_file = self.authToken.service.files().patch(fileId=src_file['id'],
                                                                body=src_file,
                                                                addParents=did,
                                                                removeParents=sid).execute()
        except:
            self.logger.exception("move failed\n")

    def MoveObservedFile(self, src_path, dest_path):
        from_drive_path = src_path.split(self.mirror_directory+'/')[1]
        to_drive_path = os.path.dirname(dest_path.split(self.mirror_directory+'/')[1])

        self.logger.debug("Moving file %s to %s\n" % (from_drive_path, to_drive_path))

        try:
            ftm = self.LocateFileOnDrive(from_drive_path)
            self.logger.debug("MoveObservedFile: Found source file on drive\n")
            if os.path.dirname(from_drive_path) == '':
                sf = 'root'
            else:
                sf = self.LocateFolderOnDrive(os.path.dirname(from_drive_path))
            self.logger.debug("MoveObservedFile: Found source folder on drive\n")
            try:
                if to_drive_path == '':
                    df = 'root'
                else:
                    df = self.LocateFolderOnDrive(to_drive_path)
                self.logger.debug("MoveObservedFile: Found destination folder on drive\n")
                try:
                    self.logger.debug("MovingFile() ")
                    self.MoveFile(ftm, df, sf)
                    self.logger.debug("done\n")
                except (Unkownerror, FileMoveFailed):
                    self.logger.error("MovedObservedFile: Failed\n")
                    return
                except:
                    self.logger.error("?????\n")
                    return
            except FolderNotFound:
                self.logger.error("MoveObservedFile: Couldn't locate destination folder on drive.\n")
                return
            except:
                self.logger.error("MoveObservedFile: Unknown error while locating destination folder on drive.\n")
                return
        except FileNotFound:
            self.logger.error("MoveObservedFile: Couldn't locate file on drive.\n")
            return
        except FileListQueryFailed:
            self.logger.error("MoveObservedFile: File Query failed. aborting.\n")
            return
        except FolderNotFound:
            self.logger.error("MoveObservedFile: Folder not found\n")
            return
        except:
            self.logger.error("MoveObservedFile: Unknown error while moving file.\n")
            return

    def HandleMovedFile(self, src_path, dest_path):
        drive_path1 = os.path.dirname(src_path.split(self.mirror_directory+'/')[1])
        drive_path2 = os.path.dirname(dest_path.split(self.mirror_directory+'/')[1])

        if drive_path1 == drive_path2:
            self.logger.debug("Rename file\n")
            self.RenameObservedFile(src_path, self.PathLeaf(dest_path))
        else:
            self.logger.debug("Move file\n")
            self.MoveObservedFile(src_path, dest_path)

    ####### DOWNLOAD SECTION #######
    def MakeFileListQuery(self, query):
        # Retry 5 times to get the query
        for n in range (0, 5):
            try:
                return self.drive.ListFile(query).GetList()
            except HttpError as error:
                if error.resp.reason in ['userRateLimitExceeded', 'quotaExceeded']:
                    self.logger.error("user rate limit/quota exceeded. Will try later\n")
                    time.sleep((2**n) + random.random())
            except:
                self.logger.error("MakeFileListQuery: failed with reason %s\n" % error.resp.reason)
                time.sleep((2**n) + random.random())

        self.logger.error("Can't get the connection back after many retries. Bailing out\n")
        raise FileListQueryFailed

    def TotalFilesInFolder(self, parent='root'):
        file_count = 0
        try:
            file_list = self.MakeFileListQuery({'q': "'%s' in parents and trashed=false" % parent})
            for f in file_list:
                if f['mimeType'] == 'application/vnd.google-apps.folder':
                    file_count += self.TotalFilesInFolder(f['id'])
                    file_count += 1
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
        if os.path.exists(abs_filepath):
            if self.HashOfFile(abs_filepath) == file_obj['md5Checksum']:
                self.logger.debug('%s file is same as local. not downloading\n' % abs_filepath)
                return
            else:
                self.logger.debug("DownloadFileByObject: Local and remote file with same name but different content. Skipping. (local file: %s)\n" % abs_filepath)
        else:
            self.logger.info('Downloading %s ' % abs_filepath)
            fd = abs_filepath.split(self.mirror_directory+'/')[1]
            GoSyncEventController().PostEvent(GOSYNC_EVENT_SYNC_UPDATE,
                                              {'Downloading %s' % fd})
            dfile.GetContentFile(abs_filepath)
            self.updates_done = 1
            self.logger.info('Done\n')

    def SyncRemoteDirectory(self, parent, pwd, recursive=True):
        if not self.syncRunning.is_set():
            self.logger.debug("SyncRemoteDirectory: Sync has been paused. Aborting.\n")
            return

        if not os.path.exists(os.path.join(self.mirror_directory, pwd)):
            os.makedirs(os.path.join(self.mirror_directory, pwd))

        try:
            file_list = self.MakeFileListQuery({'q': "'%s' in parents and trashed=false" % parent})
            for f in file_list:
                if not self.syncRunning.is_set():
                    self.logger.debug("SyncRemoteDirectory: Sync has been paused. Aborting.\n")
                    return

                if f['mimeType'] == 'application/vnd.google-apps.folder':
                    if not recursive:
                        continue

                    abs_dirpath = os.path.join(self.mirror_directory, pwd, f['title'])
                    self.logger.debug("Checking directory %s\n" % f['title'])
                    if not os.path.exists(abs_dirpath):
                        self.logger.debug("creating directory %s " % abs_dirpath)
                        os.makedirs(abs_dirpath)
                        self.logger.debug("done\n")
                    self.logger.debug('syncing directory %s\n' % f['title'])
                    self.SyncRemoteDirectory(f['id'], os.path.join(pwd, f['title']))
                    if not self.syncRunning.is_set():
                        self.logger.debug("SyncRemoteDirectory: Sync has been paused. Aborting.\n")
                        return
                else:
                    self.logger.debug("Checking file %s\n" % f['title'])
                    if not self.IsGoogleDocument(f):
                        self.DownloadFileByObject(f, os.path.join(self.mirror_directory, pwd))
                    else:
                        self.logger.info("%s is a google document\n" % f['title'])
        except:
            self.logger.error("Failed to sync directory\n")
            raise

    def SyncLocalDirectory(self):
        for root, dirs, files in os.walk(self.mirror_directory):
            for names in files:
                try:
                    dirpath = os.path.join(root, names)
                    drivepath = dirpath.split(self.mirror_directory+'/')[1]
                    f = self.LocateFileOnDrive(drivepath)
                except FileListQueryFailed:
                    # if the file list query failed, we can't delete the local file even if
                    # its gone in remote drive. Let the next sync come and take care of this
                    # Log the event though
                    self.logger.info("File check on remote directory has failed. Aborting local sync.\n")
                    return
                except:
                    if os.path.exists(dirpath) and os.path.isfile(dirpath):
                        self.logger.info("%s has been removed from drive. Deleting local copy\n" % dirpath)
                        os.remove(dirpath)

            for names in dirs:
                try:
                    dirpath = os.path.join(root, names)
                    drivepath = dirpath.split(self.mirror_directory+'/')[1]
                    f = self.LocateFileOnDrive(drivepath)
                except FileListQueryFailed:
                    # if the file list query failed, we can't delete the local file even if
                    # its gone in remote drive. Let the next sync come and take care of this
                    # Log the event though
                    self.logger.info("Folder check on remote directory has failed. Aborting local sync.\n")
                    return
                except:
                    if os.path.exists(dirpath) and os.path.isdir(dirpath):
                        self.logger.info("%s folder has been removed from drive. Deleting local copy\n" % dirpath)
                        os.remove(dirpath)


    def validate_sync_settings(self):
        for d in self.sync_selection:
            if d[0] != 'root':
                try:
                    f = self.LocateFolderOnDrive(d[0])
                    if f['id'] != d[1]:
                        raise FolderNotFound()
                    break
                except FolderNotFound:
                    raise
                except:
                    raise FolderNotFound()
            else:
                if d[1] != '':
                    raise FolderNotFound()

    def run(self):
        while True:
            self.syncRunning.wait()

            self.sync_lock.acquire()

            try:
                self.validate_sync_settings()
            except:
                GoSyncEventController().PostEvent(GOSYNC_EVENT_SYNC_INV_FOLDER, 0)
                self.syncRunning.clear()
                self.sync_lock.release()
                continue

            try:
                GoSyncEventController().PostEvent(GOSYNC_EVENT_SYNC_STARTED, None)
                for d in self.sync_selection:
                    self.logger.info("Syncing remote (%s)... " % d[0])
                    if d[0] != 'root':
                        #Root folder files are always synced
                        self.SyncRemoteDirectory('root', '', False)
                        self.SyncRemoteDirectory(d[1], d[0])
                    else:
                        self.SyncRemoteDirectory('root', '')
                    self.logger.info("done\n")
                self.logger.info("Syncing local...")
                self.SyncLocalDirectory()
                self.logger.info("done\n")
                if self.updates_done:
                    self.usageCalculateEvent.set()
                GoSyncEventController().PostEvent(GOSYNC_EVENT_SYNC_DONE, 0)
            except:
                GoSyncEventController().PostEvent(GOSYNC_EVENT_SYNC_DONE, -1)

            self.sync_lock.release()

            time_left = 600

            while (time_left):
                GoSyncEventController().PostEvent(GOSYNC_EVENT_SYNC_TIMER,
                                                  {'Sync starts in %02dm:%02ds' % ((time_left/60), (time_left % 60))})
                time_left -= 1
                self.syncRunning.wait()
                time.sleep(1)

    def GetFileSize(self, f):
        try:
            size = f['fileSize']
            return long(size)
        except:
            self.logger.error("Failed to get size of file %s (mime: %s)\n" % (f['title'], f['mimeType']))
            return 0

    def calculateUsageOfFolder(self, folder_id):
        try:
            file_list = self.MakeFileListQuery({'q': "'%s' in parents and trashed=false" % folder_id})
            for f in file_list:
                self.fcount += 1
                GoSyncEventController().PostEvent(GOSYNC_EVENT_CALCULATE_USAGE_UPDATE, self.fcount)
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
            self.usageCalculateEvent.wait()
            self.usageCalculateEvent.clear()

            if self.drive_usage_dict and not self.updates_done:
                self.logger.info("No updates done. Not calculating drive tree usage.")
                GoSyncEventController().PostEvent(GOSYNC_EVENT_CALCULATE_USAGE_DONE, 0)
                continue

            self.updates_done = 0
            self.calculatingDriveUsage = True
            self.driveAudioUsage = 0
            self.driveMoviesUsage = 0
            self.driveDocumentUsage = 0
            self.drivePhotoUsage = 0
            self.driveOthersUsage = 0
            self.fcount = 0
            self.logger.info("Staring the drive tree usage calculation")
            try:
                self.totalFilesToCheck = self.TotalFilesInDrive()
                self.logger.info("Total files to check %d\n" % self.totalFilesToCheck)
                GoSyncEventController().PostEvent(GOSYNC_EVENT_CALCULATE_USAGE_STARTED,
                                                  self.totalFilesToCheck)
                try:
                    self.calculateUsageOfFolder('root')
                    GoSyncEventController().PostEvent(GOSYNC_EVENT_CALCULATE_USAGE_DONE, 0)
                    self.drive_usage_dict['Total Files'] = self.totalFilesToCheck
                    self.drive_usage_dict['Total Size'] = long(self.about_drive['quotaBytesTotal'])
                    self.drive_usage_dict['Audio Size'] = self.driveAudioUsage
                    self.drive_usage_dict['Movies Size'] = self.driveMoviesUsage
                    self.drive_usage_dict['Document Size'] = self.driveDocumentUsage
                    self.drive_usage_dict['Photo Size'] = self.drivePhotoUsage
                    self.drive_usage_dict['Others Size'] = self.driveOthersUsage
                    self.config_dict['Drive Usage'] = self.drive_usage_dict
                    self.SaveConfig()
                    self.logger.info("Drive tree usage calculation successful!")
                except:
                    self.driveAudioUsage = 0
                    self.driveMoviesUsage = 0
                    self.driveDocumentUsage = 0
                    self.drivePhotoUsage = 0
                    self.driveOthersUsage = 0
                    GoSyncEventController().PostEvent(GOSYNC_EVENT_CALCULATE_USAGE_DONE, -1)
                    self.logger.error("Drive tree usage calculation failed!")
            except:
                GoSyncEventController().PostEvent(GOSYNC_EVENT_CALCULATE_USAGE_DONE, -1)
                self.logger.error("Failed to get the total number of files in drive\n")

            self.calculatingDriveUsage = False

    def ForceUpdateTreeReplica(self):
        self.force_update_tree = 1
        self.calculateDriveTreeReplicaEvent.set()

    def GetFoldersInFolder(self, folder_id):
        try:
            file_list = self.MakeFileListQuery({'q': "'%s' in parents and trashed=false" % folder_id})
            for f in file_list:
                if f['mimeType'] == 'application/vnd.google-apps.folder':
                    self.driveTree.AddFolder(folder_id, f['id'], f['title'], f)
                    self.GetFoldersInFolder(f['id'])
        except:
            raise

    def CreateDriveTreeReplica(self):
        while True:
            self.creatingDriveTreeReplica = 0
            self.calculateDriveTreeReplicaEvent.wait()
            self.calculateDriveTreeReplicaEvent.clear()

            if not self.updates_done and not self.force_update_tree:
                self.logger.info("No updates or force tree update. Not creating drive tree replica")
                continue

            GoSyncEventController().PostEvent(GOSYNC_EVENT_TREE_RETRIEVAL_STARTED, 0)
            self.creatingDriveTreeReplica = 1
            self.logger.info("Creating drive tree replica")
            try:
                self.GetFoldersInFolder('root')
                pickle.dump(self.driveTree, open(self.tree_pickle_file, "wb"))
                GoSyncEventController().PostEvent(GOSYNC_EVENT_TREE_RETRIEVAL_DONE, 0)
                self.logger.info("Created drive tree replica")
            except:
                GoSyncEventController().PostEvent(GOSYNC_EVENT_TREE_RETRIEVAL_FAILED, -1)
                self.logger.error("Failed to retrieve remote drive tree.")

    def GetDriveDirectoryTree(self):
        ref_tree = copy.deepcopy(self.driveTree)
        return ref_tree

    def IsCalculatingDriveUsage(self):
        return self.calculatingDriveUsage

    def IsCreatingDriveTreeReplica(self):
        return self.creatingDriveTreeReplica

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
        self.syncRunning.set()

    def StopSync(self):
        self.syncRunning.clear()

    def IsSyncEnabled(self):
        return self.syncRunning.is_set()

    def SetSyncSelection(self, folder):
        if folder == 'root':
            self.sync_selection = [['root', '']]
        else:
            for d in self.sync_selection:
                if d[0] == 'root':
                    self.sync_selection = []
            for d in self.sync_selection:
                if d[0] == folder.GetPath() and d[1] == folder.GetId():
                    return
            self.sync_selection.append([folder.GetPath(), folder.GetId()])
        self.config_dict['Sync Selection'] = self.sync_selection
        self.SaveConfig()

    def GetSyncList(self):
        return copy.deepcopy(self.sync_selection)

class FileModificationNotifyHandler(PatternMatchingEventHandler):
    patterns = ["*"]

    def __init__(self, sync_handler):
        super(FileModificationNotifyHandler, self).__init__()
        self.sync_handler = sync_handler

    def on_created(self, evt):
        self.sync_handler.logger.info("Observer: %s created\n" % evt.src_path)
        self.sync_handler.UploadObservedFile(evt.src_path)

    def on_moved(self, evt):
        self.sync_handler.logger.info("Observer: file %s moved to %s: Not supported yet!\n" % (evt.src_path, evt.dest_path))
        self.sync_handler.HandleMovedFile(evt.src_path, evt.dest_path)

    def on_deleted(self, evt):
        self.sync_handler.logger.info("Observer: file %s deleted on drive.\n" % evt.src_path)
        self.sync_handler.TrashObservedFile(evt.src_path)

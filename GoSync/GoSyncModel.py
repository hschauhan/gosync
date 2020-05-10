# gosync is an open source Google Drive(TM) sync application for Linux
# modify it under the terms of the GNU General Public License
#
# Copyright (C) 2015 Himanshu Chauhan
# This program is free software; you can redistribute it and/or
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
#

import sys, os, wx, ntpath, threading, hashlib, time, copy, io
import shutil
if sys.version_info > (3,):
    long = int
#from pydrive.auth import GoogleAuth
#from pydrive.drive import GoogleDrive
from os.path import expanduser
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from threading import Thread
from apiclient.errors import HttpError
from apiclient import errors
from apiclient.http import MediaFileUpload
from apiclient.http import MediaIoBaseDownload
import logging
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import json, pickle
try :
	from .GoSyncDriveTree import GoogleDriveTree
	from .defines import *
	from .GoSyncEvents import *
except (ImportError, ValueError):
	from GoSyncDriveTree import GoogleDriveTree
	from defines import *
	from GoSyncEvents import *

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

Log_Level = 3 # 1=error, 2=info, 3=debug

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
        self.client_pickle = os.path.join(self.config_path, "token.pickle")
        self.settings_file = os.path.join(self.config_path, "settings.yaml")
        self.base_mirror_directory = os.path.join(os.environ['HOME'], "Google Drive")
        self.client_secret_file = os.path.join(os.environ['HOME'], '.gosync', 'client_secrets.json')
        self.sync_selection = []
        self.config_file = os.path.join(os.environ['HOME'], '.gosync', 'gosyncrc')
        self.config_dict = {}
        self.account_dict = {}
        self.drive_usage_dict = {}
        self.config=None

        self.logger = logging.getLogger(APP_NAME)
        self.logger.setLevel(logging.DEBUG)
        fh = logging.FileHandler(os.path.join(os.environ['HOME'], 'GoSync.log'))
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

        self.SendlToLog(3,"Initialize - Started Initialize")

        if not os.path.exists(self.config_path):
            os.mkdir(self.config_path, 0o0755)

        if not os.path.exists(self.base_mirror_directory):
            os.mkdir(self.base_mirror_directory, 0o0755)

        if not os.path.exists(self.credential_file):
        #check if Credentials.json file exists
            self.SendlToLog(3,"Initialize - Missing Credentials File")
            if (self.AskChooseCredentialsFile()):
                self.SendlToLog(3,"Initialize - Ask Location of Credentials File")    
                if (self.getCredentialFile() == False) :
                    self.SendlToLog(1,"Initialize - Failled to load Credentials File")    
                    raise ClientSecretsNotFound()
            else:
                self.SendlToLog(3,"Initialize - Declined to Locate Credentials File")    
                raise ClientSecretsNotFound()
        self.SendlToLog(2,"Initialize - Completed Credentials Verification")

        self.SendlToLog(2, "Initialize - Saving credentials")
        if not os.path.exists(self.settings_file) or not os.path.isfile(self.settings_file):
            sfile = open(self.settings_file, 'w')
            sfile.write("save_credentials: False")
            sfile.write("\n")
            sfile.write("save_credentials_file: ")
            sfile.write(self.credential_file)
            sfile.write("\n")
            sfile.write("save_credentials_backend: file\n")
            sfile.close()

        self.SendlToLog(2, "Initialize - starting oberserver")
        self.observer = Observer()
        self.SendlToLog(2, "Initialize - Going for authentication")
        self.DoAuthenticate()
        self.about_drive = self.drive.about().get(fields='user, storageQuota').execute()
        self.SendlToLog(2,"Initialize - Completed Drive Quota Execution")

        self.user_email = self.about_drive['user']['emailAddress']
        self.SendlToLog(3,"Initialize - Completed Account Information Load")

#create subdir linked to active account
        self.mirror_directory = os.path.join(self.base_mirror_directory, self.user_email)
        if not os.path.exists(self.mirror_directory):
            os.mkdir(self.mirror_directory, 0o0755)
        self.SendlToLog(3,"Initialize - Completed mirror_directory validation")

        self.tree_pickle_file = os.path.join(self.config_path, 'gtree-' + self.user_email + '.pick')

        if not os.path.exists(self.config_file):
            self.CreateDefaultConfigFile()
            self.SendlToLog(3,"Initialize - Completed Default Config File Creation")
#todo : add default config logic in method
        try:
            self.LoadConfig()

        except:
            raise
        self.SendlToLog(3,"Initialize - Completed Config File Load")


#todo : confirm this is to monitor file changes
        self.iobserv_handle = self.observer.schedule(FileModificationNotifyHandler(self), self.mirror_directory, recursive=True)
        self.sync_lock = threading.Lock()
        self.sync_thread = threading.Thread(target=self.run)
        self.usage_calc_thread = threading.Thread(target=self.calculateUsage)
        self.sync_thread.daemon = True
        self.usage_calc_thread.daemon = True
        self.syncRunning = threading.Event()
        self.syncRunning.clear()
        self.usageCalculateEvent = threading.Event()
        self.usageCalculateEvent.set()

        if not os.path.exists(self.tree_pickle_file):
            self.driveTree = GoogleDriveTree()
        else:
            try:
                self.driveTree = pickle.load(open(self.tree_pickle_file, "rb"))
            except:
                self.driveTree = GoogleDriveTree()
        self.SendlToLog(3,"Initialize - Completed GoogleDriveTree File")
        self.SendlToLog(3,"Initialize - Completed Initialize")

# Sends Log Level Message to Log File
# Depends on Log_Level constant
    def SendlToLog(self, LogType, LogMsg):
        if (Log_Level >= LogType) :
            if (LogType == 3) :
                self.logger.debug(LogMsg)
            if (LogType == 2) :
                self.logger.info(LogMsg)
            if (LogType == 1) :
                self.logger.error(LogMsg)

    def SetTheBallRolling(self):
        self.sync_thread.start()
        self.usage_calc_thread.start()
        self.observer.start()

    def IsUserLoggedIn(self):
        return self.is_logged_in

    def HashOfFile(self, abs_filepath):
        data = open(abs_filepath, "rb").read()
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
                    except:
                        pass
                except:
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

    def AskChooseCredentialsFile(self):
        dial = wx.MessageDialog(None, 'No Credentials file was found!\n\nDo you want to load one?\n',
                                'Error', wx.YES_NO | wx.ICON_EXCLAMATION)
        res = dial.ShowModal()
        if res == wx.ID_YES:
            return True
        else:
            return false


    def getCredentialFile(self):
        # ask for the Credential file and save it in Config directory then return True
        defDir, defFile = '', ''
        dlg = wx.FileDialog(None,
               'Load Credential File',
                 '~', 'Credentials.json',
                 'json files (*.json)|*.json',
                 wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_CANCEL:
            return False
        try:
            print(dlg.GetPath())
            print(self.credential_file)
            shutil.copy(dlg.GetPath(), self.credential_file)
            return True
        except:
            return False

    def DoAuthenticate(self):
        try:
            # If modifying these scopes, delete the file token.pickle.
            SCOPES = ['https://www.googleapis.com/auth/drive']
            creds = None
            # The file token.pickle stores the user's access and refresh tokens, and is
            # created automatically when the authorization flow completes for the first
            # time.
            if os.path.exists(self.client_pickle):
                with open(self.client_pickle, 'rb') as token:
                    self.SendlToLog(2, "Authenticate - Loading pickle file")
                    creds = pickle.load(token)
            # If there are no (valid) credentials available, let the user log in.
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    self.SendlToLog(2, "Authenticate - expired. Refreshing")
                    creds.refresh(Request())
                else:
                    self.SendlToLog(2, "Authenticate - New authentication")
                    self.SendlToLog(2, "Authenticate - File %s" % (self.credential_file))
                    flow = InstalledAppFlow.from_client_secrets_file(self.credential_file, SCOPES)
                    self.SendlToLog(2, "Authenticate - running local server")
                    creds = flow.run_local_server(port=0)
                self.SendlToLog(2, "Authenticate - Saving pickle file")
                # Save the credentials for the next run
                with open(self.client_pickle, 'wb') as token:
                    pickle.dump(creds, token)

            service = build('drive', 'v3', credentials=creds)
            self.drive = service
            self.is_logged_in = True
            return service
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


    def CreateDirectoryInParent(self, dirname, parent_id='root'):
        file_metadata = {'name': dirname,
                        'mimeType':'application/vnd.google-apps.folder'}
        file_metadata['parents'] = [parent_id]
        upfile = self.drive.files().create(body=file_metadata, fields='id').execute()

    def CreateDirectoryByPath(self, dirpath):
        self.SendlToLog(3,"create directory: %s\n" % dirpath)
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
                    self.SendlToLog(1,errorMsg)
                    dial = wx.MessageDialog(None, errorMsg, 'Directory Not Found',
                                            wx.ID_OK | wx.ICON_EXCLAMATION)
                    dial.ShowModal()
                    return
        except FileListQueryFailed:
            errorMsg = "Server Query Failed!\n"
            self.SendlToLog(1,errorMsg)
            dial = wx.MessageDialog(None, errorMsg, 'Directory Not Found',
                                    wx.ID_OK | wx.ICON_EXCLAMATION)
            dial.ShowModal()
            return

    def CreateRegularFile(self, file_path, parent='root', uploaded=False):
        self.SendlToLog(3,"Create file %s\n" % file_path)
        filename = self.PathLeaf(file_path)
        file_metadata = {'name': filename}
        file_metadata['parents'] = [parent]
        media = MediaFileUpload(file_path, resumable=True)
        upfile = self.drive.files().create(body=file_metadata,
                                    media_body=media,
                                    fields='id').execute()

    def UploadFile(self, file_path):
        if os.path.isfile(file_path):
            drivepath = file_path.split(self.mirror_directory+'/')[1]
            self.SendlToLog(3,"file: %s drivepath is %s\n" % (file_path, drivepath))
            try:
                f = self.LocateFileOnDrive(drivepath)
                self.SendlToLog(3,'Found file %s on remote (dpath: %s)\n' % (f['name'], drivepath))
                newfile = False
                self.SendlToLog(3,'Checking if they are same... ')
                if f['md5Checksum'] == self.HashOfFile(file_path):
                    self.SendlToLog(3,'yes\n')
                    return
                else:
                    self.SendlToLog(3,'no\n')
            except (FileNotFound, FolderNotFound):	
                self.SendlToLog(3,"A new file!\n")
                newfile = True

            dirpath = os.path.dirname(drivepath)
            if dirpath == '':
                self.SendlToLog(3,'Creating %s file in root\n' % file_path)
                self.CreateRegularFile(file_path, 'root', newfile)
                GoSyncEventController().PostEvent(GOSYNC_EVENT_SYNC_UPDATE, {'UpLoading %s' % file_path})
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
##        GoSyncEventController().PostEvent(GOSYNC_EVENT_SYNC_UPDATE, {''})

    def RenameFile(self, file_object, new_title):
        try:
            file = {'name': new_title}

            updated_file = self.drive.files().update( body= file,
                                                         fileId=file_object['id'],
                                                         fields='id, appProperties').execute()
            return updated_file
        except errors.HttpError as error:
            self.SendlToLog(1,'An error occurred while renaming file: %s' % error)
            return None
        except:
            self.logger.exception('An unknown error occurred file renaming file\n')
            return None

    def RenameObservedFile(self, file_path, new_name):
        self.sync_lock.acquire()
        drive_path = file_path.split(self.mirror_directory+'/')[1]
        self.SendlToLog(3,"RenameObservedFile: Rename %s to new name %s\n"
                          % (file_path, new_name))
        try:
            ftd = self.LocateFileOnDrive(drive_path)
            nftd = self.RenameFile(ftd, new_name)
            if not nftd:
                self.SendlToLog(1,"File rename failed\n")
        except:
            self.logger.exception("Could not locate file on drive.\n")

        self.sync_lock.release()

    def TrashFile(self, file_object):
        try:
            file_metadata = {'trashed':True}
            self.drive.files().update(body=file_metadata,fileId=file_object['id']).execute()
            self.SendlToLog(2,{"TRASH_FILE: File %s deleted successfully.\n" % file_object['name']})
        except errors.HttpError as error:
            self.SendlToLog(1,"TRASH_FILE: HTTP Error\n")
            raise RegularFileTrashFailed()

    def TrashObservedFile(self, file_path):
        self.sync_lock.acquire()
        drive_path = file_path.split(self.mirror_directory+'/')[1]
        self.SendlToLog(3,{"TRASH_FILE: dirpath to delete: %s\n" % drive_path})
        try:
            ftd = self.LocateFileOnDrive(drive_path)
            try:
                self.TrashFile(ftd)
            except RegularFileTrashFailed:
                self.SendlToLog(1,{"TRASH_FILE: Failed to move file %s to trash\n" % drive_path})
                raise
            except:
                raise
        except (FileNotFound, FileListQueryFailed, FolderNotFound):
            self.SendlToLog(1,{"TRASH_FILE: Failed to locate %s file on drive\n" % drive_path})
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

            updated_file = self.drive.files().update(fileId=src_file['id'],
                                    addParents=did,
                                    removeParents=sid,
                                    fields='id, parents').execute()

        except:
            self.logger.exception("move failed\n")

    def MoveObservedFile(self, src_path, dest_path):
        from_drive_path = src_path.split(self.mirror_directory+'/')[1]
        to_drive_path = os.path.dirname(dest_path.split(self.mirror_directory+'/')[1])

        self.SendlToLog(3,"Moving file %s to %s\n" % (from_drive_path, to_drive_path))

        try:
            ftm = self.LocateFileOnDrive(from_drive_path)
            self.SendlToLog(3,"MoveObservedFile: Found source file on drive\n")
            if os.path.dirname(from_drive_path) == '':
                sf = 'root'
            else:
                sf = self.LocateFolderOnDrive(os.path.dirname(from_drive_path))
            self.SendlToLog(3,"MoveObservedFile: Found source folder on drive\n")
            try:
                if to_drive_path == '':
                    df = 'root'
                else:
                    df = self.LocateFolderOnDrive(to_drive_path)
                self.SendlToLog(3,"MoveObservedFile: Found destination folder on drive\n")
                try:
                    self.SendlToLog(3,"MovingFile() ")
                    self.MoveFile(ftm, df, sf)
                    self.SendlToLog(3,"done\n")
                except (Unkownerror, FileMoveFailed):
                    self.SendlToLog(1,"MovedObservedFile: Failed\n")
                    return
                except:
                    self.SendlToLog(1,"?????\n")
                    return
            except FolderNotFound:
                self.SendlToLog(1,"MoveObservedFile: Couldn't locate destination folder on drive.\n")
                return
            except:
                self.SendlToLog(1,"MoveObservedFile: Unknown error while locating destination folder on drive.\n")
                return
        except FileNotFound:
                self.SendlToLog(1,"MoveObservedFile: Couldn't locate file on drive.\n")
                return
        except FileListQueryFailed:
            self.SendlToLog(1,"MoveObservedFile: File Query failed. aborting.\n")
            return
        except FolderNotFound:
            self.SendlToLog(1,"MoveObservedFile: Folder not found\n")
            return
        except:
            self.SendlToLog(1,"MoveObservedFile: Unknown error while moving file.\n")
            return

    def HandleMovedFile(self, src_path, dest_path):
        drive_path1 = os.path.dirname(src_path.split(self.mirror_directory+'/')[1])
        drive_path2 = os.path.dirname(dest_path.split(self.mirror_directory+'/')[1])

        if drive_path1 == drive_path2:
            self.SendlToLog(3,"Rename file\n")
            self.RenameObservedFile(src_path, self.PathLeaf(dest_path))
        else:
            self.SendlToLog(3,"Move file\n")
            self.MoveObservedFile(src_path, dest_path)

    #################################################
    ####### DOWNLOAD SECTION (Syncing local) #######
    #################################################


#### LocateFileInFolder
    def LocateFileInFolder(self, filename, parent='root'):
        try:
            file_list = self.MakeFileListQuery("'%s' in parents and trashed=false" % parent)
            for f in file_list:
                if f['name'] == filename:
                    return f

            raise FileNotFound()
        except:
            raise FileNotFound()

#### LocateFileOnDrive
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
                    self.SendlToLog(3,"LocateFileOnDrive: Local File (%s) not in remote." % filename)
                    raise
                except FileListQueryFailed:
                    self.SendlToLog(3,"LocateFileOnDrive: Locate File (%s) list query failed" % filename)
                    raise
            except FolderNotFound:
                self.SendlToLog(3,"LocateFileOnDrive: Local Folder (%s) not in remote" % dirpath)
                raise
            except FileListQueryFailed:
                self.SendlToLog(3,"LocateFileOnDrive: Locate Folder (%s) list query failed" % dirpath)
                raise
        else:
            try:
                fil = self.LocateFileInFolder(filename)
                return fil
            except FileNotFound:
                self.SendlToLog(3,"LocateFileOnDrive: Local File (%s) not in remote." % filename)
                raise
            except FileListQueryFailed:
                self.SendlToLog(3,"LocateFileOnDrive: File (%s) list query failed." % filename)
                raise
            except:
                self.SendlToLog(1,"LocateFileOnDrive: Unknown error in locating file (%s) in local folder (root)" % filename)
                raise

#### LocateFolderOnDrive
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

#### GetFolderOnDrive
    def GetFolderOnDrive(self, folder_name, parent='root'):
        """
        Return the folder with name in "folder_name" in the parent folder
        mentioned in parent.
        """
        self.SendlToLog(3,"GetFolderOnDrive: Checking Folder (%s) on (%s)" % (folder_name, parent))
        file_list = self.MakeFileListQuery("'%s' in parents and trashed=false"  % parent)
        for f in file_list:
            if f['name'] == folder_name and f['mimeType']=='application/vnd.google-apps.folder':
                self.SendlToLog(2,"GetFolderOnDrive: Found Folder (%s) on (%s)" % (folder_name, parent))
                return f

        return None

#### SyncLocalDirectory
    def SyncLocalDirectory(self):
        self.SendlToLog(2,"### SyncLocalDirectory: - Sync Started")
        for root, dirs, files in os.walk(self.mirror_directory):
            for names in files:
                try:
                    dirpath = os.path.join(root, names)
                    drivepath = dirpath.split(self.mirror_directory+'/')[1]
                    self.SendlToLog(3,"SyncLocalDirectory: Checking Local File (%s)" % drivepath)
                    f = self.LocateFileOnDrive(drivepath)
                    self.SendlToLog(2,"SyncLocalDirectory: Skipping Local File (%s) same as Remote\n" % dirpath)
                except FileListQueryFailed:
                    # if the file list query failed, we can't delete the local file even if
                    # its gone in remote drive. Let the next sync come and take care of this
                    # Log the event though
                    self.SendlToLog(2,"SyncLocalDirectory: Remote File (%s) Check Failed. Aborting.\n" % dirpath)
                    return
                except:
                    if os.path.exists(dirpath) and os.path.isfile(dirpath):
                        self.SendlToLog(2,"SyncLocalDirectory: Deleting Local File (%s) - Not in Remote\n" % dirpath)
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
                    self.SendlToLog(2,"SyncLocalDirectory: Remote Folder (%s) Check Failed. Aborting.\n" % dirpath)
                    return
                except:
                    if os.path.exists(dirpath) and os.path.isdir(dirpath):
                        self.SendlToLog(2,"SyncLocalDirectory: Deleting Local Folder (%s) - Not in Remote\n" % dirpath)
                        #to delete none empty directory recursively
#                        os.remove(dirpath)
                        shutil.rmtree(dirpath, ignore_errors=False, onerror=None)
        self.SendlToLog(2,"### SyncLocalDirectory: - Sync Completed")


    #################################################
    ####### DOWNLOAD SECTION (Syncing remote) #######
    #################################################


    def MakeFileListQuery(self, query):
        try:
            page_token = None
            filelist = []
            while True:
                response = self.drive.files().list(q=query,
                                      spaces='drive',
                                      fields='nextPageToken, files(id, name, mimeType, size, md5Checksum)',
                                      pageToken=page_token).execute()
                filelist.extend(response.get('files',[]))
                page_token = response.get('nextPageToken', None)
                if page_token is None:
                    break
            return filelist
        except HttpError as error:
            if error.resp.reason in ['userRateLimitExceeded', 'quotaExceeded']:
                self.SendlToLog(1,"MakeFileListQuery: User Rate Limit/Quota Exceeded. Will try later\n")
#            time.sleep((2**n) + random.random())
        except:
            self.SendlToLog(1,"MakeFileListQuery: failed with reason %s\n" % error.resp.reason)
#        time.sleep((2**n) + random.random())
#    self.SendlToLog(1,"Can't get the connection back after many retries. Bailing out\n")
        raise FileListQueryFailed

    def TotalFilesInFolder(self, parent='root'):
        file_count = 0
        try:
            file_list = self.MakeFileListQuery("'%s' in parents and trashed=false"  % parent)
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

#### DownloadFileByObject
    def DownloadFileByObject(self, file_obj, download_path):
        abs_filepath = os.path.join(download_path, file_obj['name'])
        if os.path.exists(abs_filepath):
            if self.HashOfFile(abs_filepath) == file_obj['md5Checksum']:
                self.SendlToLog(2,'DownloadFileByObject: Skipping File (%s) - same as remote.\n' % abs_filepath)
                return
            else:
                self.SendlToLog(2,"DownloadFileByObject: Skipping File (%s) - Local and Remote - Same Name but Different Content.\n" % abs_filepath)
        else:
            self.SendlToLog(3,'DownloadFileByObject: Download Started - File (%s)' % abs_filepath)
            fd = abs_filepath.split(self.mirror_directory+'/')[1]
            GoSyncEventController().PostEvent(GOSYNC_EVENT_SYNC_UPDATE,
                                              {'Downloading %s' % fd})
            request = self.drive.files().get_media(fileId=file_obj['id'])
            fh = io.FileIO(abs_filepath, 'wb')
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()            
            fh.close()
            self.updates_done = 1
            self.SendlToLog(2,'DownloadFileByObject: Download Completed - File (%s)\n' % abs_filepath)

#### SyncRemoteDirectory
    def SyncRemoteDirectory(self, parent, pwd, recursive=True):
        self.SendlToLog(2,"### SyncRemoteDirectory: - Sync Started - Remote Directory (%s) ... Recursive = %s\n" % (pwd, recursive))
        if not self.syncRunning.is_set():
            self.SendlToLog(3,"SyncRemoteDirectory: Sync has been paused. Aborting.\n")
            return

        if not os.path.exists(os.path.join(self.mirror_directory, pwd)):
            os.makedirs(os.path.join(self.mirror_directory, pwd))

        try:
            file_list = self.MakeFileListQuery("'%s' in parents and trashed=false" % parent)
            for f in file_list:
                if not self.syncRunning.is_set():
                    self.SendlToLog(3,"SyncRemoteDirectory: Sync has been paused. Aborting.\n")
                    return

                if f['mimeType'] == 'application/vnd.google-apps.folder':
                    if not recursive:
                        continue

                    abs_dirpath = os.path.join(self.mirror_directory, pwd, f['name'])
                    self.SendlToLog(3,"SyncRemoteDirectory: Checking directory (%s)" % f['name'])
                    if not os.path.exists(abs_dirpath):
                        self.SendlToLog(3,"SyncRemoteDirectory: Creating directory (%s)" % abs_dirpath)
                        os.makedirs(abs_dirpath)
                        self.SendlToLog(3,"SyncRemoteDirectory: Created directory (%s)" % abs_dirpath)
                    self.SendlToLog(3,"SyncRemoteDirectory: Syncing directory (%s)\n" % f['name'])
                    self.SyncRemoteDirectory(f['id'], os.path.join(pwd, f['name']))
                    if not self.syncRunning.is_set():
                        self.SendlToLog(3,"SyncRemoteDirectory: Sync has been paused. Aborting.\n")
                        return
                else:
                    self.SendlToLog(3,"SyncRemoteDirectory: Checking file (%s)" % f['name'])
                    if not self.IsGoogleDocument(f):
                        self.DownloadFileByObject(f, os.path.join(self.mirror_directory, pwd))
                    else:
                        self.SendlToLog(2,"SyncRemoteDirectory: Skipping file (%s) is a google document.\n" % f['name'])
        except:
            self.SendlToLog(1,"SyncRemoteDirectory: Failed to sync directory (%s)" % f['name'])
            raise
        self.SendlToLog(2,"### SyncRemoteDirectory: - Sync Completed - Remote Directory (%s) ... Recursive = %s\n" % (pwd, recursive))

#### validate_sync_settings
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

#### run (Sync Local and Remote Directory)
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
                self.SendlToLog(2,"###############################################")
                self.SendlToLog(2,"Start - Syncing remote directory")
                self.SendlToLog(2,"###############################################")
                for d in self.sync_selection:
                    if d[0] != 'root':
                        #Root folder files are always synced (not recursive)
                        self.SyncRemoteDirectory('root', '', False)
                        #Then sync current folder (recursively)
                        self.SyncRemoteDirectory(d[1], d[0])
                    else:
                        #Sync Root folder (recursively)
                        self.SyncRemoteDirectory('root', '')
                self.SendlToLog(2,"###############################################")
                self.SendlToLog(2,"End - Syncing remote directory")
                self.SendlToLog(2,"###############################################\n")
                self.SendlToLog(2,"###############################################")
                self.SendlToLog(2,"Start - Syncing local directory")
                self.SendlToLog(2,"###############################################")
                self.SyncLocalDirectory()
                self.SendlToLog(2,"###############################################")
                self.SendlToLog(2,"End - Syncing local directory")
                self.SendlToLog(2,"###############################################\n")
                if self.updates_done:
                    self.usageCalculateEvent.set()
                GoSyncEventController().PostEvent(GOSYNC_EVENT_SYNC_DONE, 0)
            except:
                GoSyncEventController().PostEvent(GOSYNC_EVENT_SYNC_DONE, -1)

            self.sync_lock.release()
            self.time_left = 600
#
#todo to review time to wait
            self.time_left = 600

            while (self.time_left):
                GoSyncEventController().PostEvent(GOSYNC_EVENT_SYNC_TIMER,
                                                  {'Sync starts in %02dm:%02ds' % ((self.time_left/60), (self.time_left % 60))})
                self.time_left -= 1
                self.syncRunning.wait()
                time.sleep(1)

#### GetFileSize
    def GetFileSize(self, f):
        try:
            size = f['size']
            return long(size)
        except:
#Migration V3 API
#            self.SendlToLog(1,"Failed to get size of file %s (mime: %s)\n" % (f['title'], f['mimeType']))
            self.SendlToLog(1,"Failed to get size of file %s (mime: %s)\n" % (f['name'], f['mimeType']))
            return 0

#### calculateUsageOfFolder
    def calculateUsageOfFolder(self, folder_id):
        try:
            file_list = self.MakeFileListQuery("'%s' in parents and trashed=false" % folder_id)
            for f in file_list:
                self.fcount += 1
                GoSyncEventController().PostEvent(GOSYNC_EVENT_CALCULATE_USAGE_UPDATE, self.fcount)
                if f['mimeType'] == 'application/vnd.google-apps.folder':
                    self.driveTree.AddFolder(folder_id, f['id'], f['name'], f)
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

#### calculateUsage
    def calculateUsage(self):
        while True:
            self.usageCalculateEvent.wait()
            self.usageCalculateEvent.clear()

            self.sync_lock.acquire()
            if self.drive_usage_dict and not self.updates_done:
                GoSyncEventController().PostEvent(GOSYNC_EVENT_CALCULATE_USAGE_DONE, 0)
                self.sync_lock.release()
                continue

            self.updates_done = 0
            self.calculatingDriveUsage = True
            self.driveAudioUsage = 0
            self.driveMoviesUsage = 0
            self.driveDocumentUsage = 0
            self.drivePhotoUsage = 0
            self.driveOthersUsage = 0
            self.fcount = 0
            try:
                self.totalFilesToCheck = self.TotalFilesInDrive()
                self.SendlToLog(2,"Total files to check %d\n" % self.totalFilesToCheck)
                GoSyncEventController().PostEvent(GOSYNC_EVENT_CALCULATE_USAGE_STARTED, self.totalFilesToCheck)
                try:
                    self.calculateUsageOfFolder('root')
                    GoSyncEventController().PostEvent(GOSYNC_EVENT_CALCULATE_USAGE_DONE, 0)
                    self.drive_usage_dict['Total Files'] = self.totalFilesToCheck
                    self.drive_usage_dict['Total Size'] = long(self.about_drive['storageQuota']['limit'])
                    self.drive_usage_dict['Audio Size'] = self.driveAudioUsage
                    self.drive_usage_dict['Movies Size'] = self.driveMoviesUsage
                    self.drive_usage_dict['Document Size'] = self.driveDocumentUsage
                    self.drive_usage_dict['Photo Size'] = self.drivePhotoUsage
                    self.drive_usage_dict['Others Size'] = self.driveOthersUsage
                    pickle.dump(self.driveTree, open(self.tree_pickle_file, "wb"))
                    self.config_dict['Drive Usage'] = self.drive_usage_dict
                    self.SaveConfig()
                except:
                    self.driveAudioUsage = 0
                    self.driveMoviesUsage = 0
                    self.driveDocumentUsage = 0
                    self.drivePhotoUsage = 0
                    self.driveOthersUsage = 0
                    GoSyncEventController().PostEvent(GOSYNC_EVENT_CALCULATE_USAGE_DONE, -1)
            except:
                GoSyncEventController().PostEvent(GOSYNC_EVENT_CALCULATE_USAGE_DONE, -1)
                self.SendlToLog(1,"Failed to get the total number of files in drive\n")

            self.calculatingDriveUsage = False
            self.sync_lock.release()

    def GetDriveDirectoryTree(self):
        self.sync_lock.acquire()
        ref_tree = copy.deepcopy(self.driveTree)
        self.sync_lock.release()
        return ref_tree

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
        self.sync_handler.logger.debug("Observer: %s created\n" % evt.src_path)
        self.sync_handler.UploadObservedFile(evt.src_path)

    def on_moved(self, evt):
        self.sync_handler.logger.info("Observer: file %s moved to %s: Not supported yet!\n" % (evt.src_path, evt.dest_path))
        self.sync_handler.HandleMovedFile(evt.src_path, evt.dest_path)

    def on_deleted(self, evt):
        self.sync_handler.logger.info("Observer: file %s deleted on drive.\n" % evt.src_path)
        self.sync_handler.TrashObservedFile(evt.src_path)

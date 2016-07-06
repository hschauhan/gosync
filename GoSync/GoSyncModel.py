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

import sys, os, ntpath, defines, threading, hashlib, time, copy
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
from GoSyncDriveTree import GoogleDriveTree
import json, pickle, datetime
from gi.repository import GObject

class ClientSecretsNotFound(Exception):
	"""Client secrets file was not found"""
	def __init__(self, msg=None):
		Exception.__init__(self, msg)

class FileNotFound(Exception):
	"""File was not found on google drive"""
	def __init__(self, msg=None):
		Exception.__init__(self, msg)

class FolderNotFound(Exception):
	"""Folder on Google Drive was not found"""
        def __init__(self, msg=None):
		Exception.__init__(self, msg)

class UnknownError(Exception):
	"""Unknown/Unexpected error happened"""
        def __init__(self):
		Exception.__init__(self, "An unknown/unexpected error has happened. Please restart.")

class MD5ChecksumCalculationFailed(Exception):
	"""Calculation of MD5 checksum on a given file failed"""
        def __init__(self, msg=None):
		Exception.__init__(self, msg)

class RegularFileUploadFailed(Exception):
	"""Upload of a regular file failed"""
        def __init__(self, msg=None):
		Exception.__init__(self, msg)

class RegularFileTrashFailed(Exception):
	"""Could not move file to trash"""
        def __init__(self, msg=None):
		Exception.__init__(self, msg)

class FileListQueryFailed(Exception):
	"""The query of file list failed"""
        def __init__(self, msg=None):
		Exception.__init__(self, msg)

class ConfigLoadFailed(Exception):
	"""Failed to load the GoSync configuration file"""
        def __init__(self, msg=None):
		Exception.__init__(self, msg)

class AuthenticationFailed(Exception):
	"""Authentication failed with pydrive because of some issue"""
        def __init__(self, msg=None):
		Exception.__init__(self, msg)


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

class GoSyncModel(GObject.GObject):
    __gsignals__ = {
        'sync_update' : (GObject.SIGNAL_RUN_FIRST, None, (str, str, str,)),
	'sync_timer' : (GObject.SIGNAL_RUN_FIRST, None, (str,)),
	'sync_started' : (GObject.SIGNAL_RUN_FIRST, None, (int,)),
	'sync_done' : (GObject.SIGNAL_RUN_FIRST, None, (int, )),
	'calculate_usage_started' : (GObject.SIGNAL_RUN_FIRST, None, (int, )),
	'calculate_usage_done' : (GObject.SIGNAL_RUN_FIRST, None, (int, )),
	'calculate_usage_update' : (GObject.SIGNAL_RUN_FIRST, None, (int, ))
    }

    def __init__(self):

	GObject.GObject.__init__(self)

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

        self.logger = logging.getLogger(APP_NAME)
        self.logger.setLevel(logging.INFO)
        fh = logging.FileHandler(os.path.join(os.environ['HOME'], 'GoSync.log'))
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

        self.logger.info("Starting up...")
        self.config_path = os.path.join(os.environ['HOME'], ".gosync")
        self.logger.info("Config Path: %s" % self.config_path)
        self.credential_file = os.path.join(self.config_path, "credentials.json")
        self.logger.info("Crediential File: %s" % self.credential_file)
        self.settings_file = os.path.join(self.config_path, "settings.yaml")
        self.base_mirror_directory = os.path.join(os.environ['HOME'], "Google Drive")
        self.logger.info("Mirror Directory Base: %s" % self.base_mirror_directory)
        self.client_secret_file = os.path.join(os.environ['HOME'], '.gosync', 'client_secrets.json')
        self.logger.info("Secret File: %s" % self.client_secret_file)
        self.sync_selection = []
        self.config_file = os.path.join(os.environ['HOME'], '.gosync', 'gosyncrc')
        self.logger.info("Confile file: %s" % self.config_file)
        self.config_dict = {}
        self.account_dict = {}
        self.drive_usage_dict = {}
        self.config=None

        if not os.path.exists(self.config_path):
            self.logger.error("Config path doesn't exist. Creating one. Also return client secret not found error.")
            os.mkdir(self.config_path, 0755)
            raise ClientSecretsNotFound("Running GoSync for the first time?\n\nGoSync was unable to find client_secrets.json file in .gosync folder in your home directory.")

        if not os.path.exists(self.base_mirror_directory):
            self.logger.info("Creating base mirror directory.")
            os.mkdir(self.base_mirror_directory, 0755)

        if not os.path.exists(self.client_secret_file):
            self.logger.error("Client secrets not found.")
            raise ClientSecretsNotFound("GoSync was unable to find client_secrets.json file in .gosync folder in your home directory.")

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

        self.logger.info("Creating observer.")
        self.observer = Observer()
        self.logger.info("Going for authentication from user.")
        self.DoAuthenticate()
        self.about_drive = self.authToken.service.about().get().execute()
        self.user_email = self.about_drive['user']['emailAddress']

        self.mirror_directory = os.path.join(self.base_mirror_directory, self.user_email)
        if not os.path.exists(self.mirror_directory):
            os.mkdir(self.mirror_directory, 0755)

        self.logger.info("Creating drive tree shadow copy...")
        self.tree_pickle_file = os.path.join(self.config_path, 'gtree-' + self.user_email + '.pick')

        if not os.path.exists(self.config_file):
            self.logger.info("Creating default config file.")
            self.CreateDefaultConfigFile()

        try:
            self.LoadConfig()
        except:
            self.logger.error("Configuration load failed.")
            raise

        self.logger.info("Scheduling file modification notify handler.")
        self.iobserv_handle = self.observer.schedule(FileModificationNotifyHandler(self),
                                                     self.mirror_directory, recursive=True)

        self.sync_lock = threading.Lock()
        self.sync_thread = threading.Thread(target=self.run)
        self.logger.info("Creating the usage calculation thread.")
        self.usage_calc_thread = threading.Thread(target=self.calculateUsage)
        self.sync_thread.daemon = True
        self.usage_calc_thread.daemon = True
        self.syncRunning = threading.Event()
        self.syncRunning.clear()
        self.usageCalculateEvent = threading.Event()
        self.logger.info("Starting the usage calculator thread.")
        self.usageCalculateEvent.set()

        if not os.path.exists(self.tree_pickle_file):
            self.logger.info("No saved device tree. Creating a new tree to sync with server.")
            self.driveTree = GoogleDriveTree()
            self.drive_usage_dict = {}
            self.updates_done = 1
        else:
            self.logger.info("Loading last tree from file.")
            try:
                    self.driveTree = pickle.load(open(self.tree_pickle_file, "rb"))
                    self.logger.info("done")
            except:
                    self.logger.error("Failed to load the drive tree from file. Resetting...")
                    self.driveTree = GoogleDriveTree()
                    self.drive_usage_dict = {}
                    self.updates_done = 1

            self.logger.info("All done.")

    def do_sync_udpate(self, arg):
	print("class method for sync_update called with argument", arg)

    def SetTheBallRolling(self):
        self.sync_thread.start()
        self.usage_calc_thread.start()
        self.observer.start()

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
                    except:
                        pass
                except:
                    pass

                f.close()
            except:
                raise ConfigLoadFailed("Failed to load configuration file (%s)" % self.config_file)
        except:
            raise ConfigLoadFailed("Failed to open/read configuration file (%s)" % self.config_file)

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
            self.authToken = GoogleAuth(settings_file=self.settings_file)
            if self.authToken.credentials is None:
                self.logger.info("No credentials loaded from file. Doing authentication again.")
                try:
                    self.authToken.LocalWebserverAuth()
                    self.authToken.Authorize()
                except AuthenticationRejected:
                    print("Authentication rejected")
                    raise AuthenticationFailed("Authentication was rejected for your Google(&#8482) account.")

                except AuthenticationError:
                    print("Authentication error")
                    raise AuthenticationFailed()
                except:
                    print("Unknown error in doing authentication.")
                    raise AuthenticationFailed()

            elif self.authToken.access_token_expired:
                self.logger.info("Token is expired. Refreshing.")
                self.authToken.Refresh()
            else:
                self.authToken.Authorize()

            self.drive = GoogleDrive(self.authToken)
            self.is_logged_in = True
        except:
            raise AuthenticationFailed()

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
                    raise FolderNotFound("Folder %s wasn't found on drive" % dir1)
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
            except FolderNotFound as e:
                self.logger.debug(e)
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
		now = datetime.datetime.now()
                try:
		    self.emit('sync_update', dirname, 'Upload', now.strftime("%Y-%m-%d %H:%M"))
                except:
                    print "CreateDirectoryByPath: sync_update signal failed."
            else:
                try:
                    parent_folder = self.LocateFolderOnDrive(basepath)
                    self.CreateDirectoryInParent(dirname, parent_folder['id'])
		    now = datetime.datetime.now()
                    try:
		        self.emit('sync_update', dirname, 'Upload', now.strftime("%Y-%m-%d %H:%M"))
                    except:
                        print "CreateDirectoryByPath: sync_update signal failed (basepath)"

                except:
                    errorMsg = "Failed to locate directory path %s on drive.\n" % basepath
                    self.logger.error(errorMsg)
                    return
        except FileListQueryFailed:
            errorMsg = "Server Query Failed!\n"
            self.logger.error(errorMsg)
            return

    def CreateRegularFile(self, file_path, parent='root', uploaded=False):
        self.logger.debug("Create file %s\n" % file_path)
        filename = self.PathLeaf(file_path)
        upfile = self.drive.CreateFile({'title': filename,
                                       "parents": [{"kind": "drive#fileLink", "id": parent}]})
        upfile.SetContentFile(file_path)
        upfile.Upload()
	now = datetime.datetime.now()
        try:
		self.emit('sync_update', file_path, 'Upload', now.strftime("%Y-%m-%d %H:%M"))
        except:
                print "CreateRegularFile: sync_update signal failed."

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
                    raise RegularFileUploadFailed("Failed upload file possibly because parent folder (%s) was not found on drive" % dirpath)
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
            except FolderNotFound as e:
                self.logger.error(e + " MoveObservedFile: Couldn't locate destination folder on drive.\n")
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
	except FolderNotFound as e:
	    self.logger.error(e + " MoveObservedFile: Folder not found\n")
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
            now = datetime.datetime.now()
            print now.strftime("%Y-%m-%d %H:%M")
            try:
		self.emit('sync_update', fd, 'Download', now.strftime("%Y-%m-%d %H:%M"))
            except:
                print "DownloadFileByObject: sync_udpate signal failed"

            #GoSyncEventController().PostEvent(GOSYNC_EVENT_SYNC_UPDATE,
            #                                  {'Downloading %s' % fd})
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
                        raise FolderNotFound("Can't locate folder %s on drive" % d[0])
                    break
                except FolderNotFound as e:
                    self.logger.error(e)
                    raise
                except:
                    raise FolderNotFound("Can't locate folder %s on drive" % d[0])
            else:
                if d[1] != '':
                    raise FolderNotFound("Folder to sync is root but ID is defined as %s" % d[1])

    def run(self):
        while True:
            self.syncRunning.wait()

            self.logger.debug("Sync thread unblocked")
            self.sync_lock.acquire()
            self.logger.debug("Sync lock is acquired")

            try:
                self.validate_sync_settings()
            except:
                #GoSyncEventController().PostEvent(GOSYNC_EVENT_SYNC_INV_FOLDER, 0)
                self.logger.error("Sync settings are not valid")
                self.syncRunning.clear()
                self.sync_lock.release()
                continue

            try:
		#self.emit('sync_started', 0)
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
		#self.emit('sync_done', 0)
            except:
		print("SYNC DONE ERROR")
		#self.emit('sync_done', -1)

            self.sync_lock.release()

            time_left = 600

            while (time_left):
		#self.emit('sync_timer', ('Sync starts in %02dm:%02ds' % ((time_left/60), (time_left % 60))))
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
		self.emit('calculate_usage_update', self.fcount)
                if f['mimeType'] == 'application/vnd.google-apps.folder':
                    self.driveTree.AddFolder(folder_id, f['id'], f['title'], f)
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

            self.sync_lock.acquire()
            if self.drive_usage_dict and not self.updates_done:
		self.emit('calculate_usage_done', 0)
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
                #self.totalFilesToCheck = self.TotalFilesInDrive()
                #self.logger.info("Total files to check %d\n" % self.totalFilesToCheck)
		#self.emit('calculate_usage_started', 0)
                try:
                    self.calculateUsageOfFolder('root')
		    self.emit('calculate_usage_done', 0)
                    self.drive_usage_dict['Total Files'] = self.totalFilesToCheck
                    self.drive_usage_dict['Total Size'] = long(self.about_drive['quotaBytesTotal'])
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
		    self.emit('calculate_usage_done', -1)
            except:
		self.emit('calculate_usage_done', -1)
                self.logger.error("Failed to get the total number of files in drive\n")

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

    def RemoveSyncSelection(self, folder):
	i = 0
	deleted = False
	for d in self.sync_selection:
	        if d[0] == folder.GetPath() and d[1] == folder.GetId():
			del self.sync_selection[i]
			deleted = True
		i = i + 1

	if deleted:
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

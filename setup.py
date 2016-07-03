from GoSync.defines import *
from codecs import open
from os import path
import os
from setuptools import setup, find_packages
from setuptools.command.install import install


here = path.abspath(path.dirname(__file__))
###################################################################
# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

class PostInstallCommand(install):
    """Post-installation for installation mode."""
    def run(self):
	icon_dir = os.path.join(os.environ['HOME'], '.icons/')
	if not os.path.exists(icon_dir):
		os.mkdir(icon_dir)
	icon_source = os.path.join(here, 'GoSync/resources/GoSyncIcon.png')
	icon_symlink = os.path.join(icon_dir, 'GoSyncIcon.png')

	if os.path.exists(icon_symlink):
		os.remove(icon_symlink)

	os.symlink(icon_source, icon_symlink)
	resource_dir = os.path.join(here, 'GoSync/resources')
	desktop_path = os.path.join(os.environ['HOME'], 'Desktop')
	dest_dot_desktop = os.path.join(desktop_path, 'GoSync.desktop')

	if os.path.exists(dest_dot_desktop):
		os.remove(dest_dot_desktop)

	try:
		launch_file = open(dest_dot_desktop, 'w')
		launch_file.write('[Desktop Entry]\n')
		launch_file.write('Type=Application\n')
		launch_file.write(('Version=%s\n' % APP_VERSION))
		launch_file.write('Name=%s\n' % APP_NAME)
		launch_file.write('Comment=%s\n' % APP_DESCRIPTION)
		launch_file.write('Icon=%s\n' % DESKTOP_ICON_NAME)
		exfile = os.path.join(here, 'GoSync/GoSync.py')
		launch_file.write('Exec=%s\n' % exfile)
		launch_file.write('Terminal=false\n')
		launch_file.write('Path=%s\n' % (os.path.join(here, 'GoSync')))
		launch_file.close()
		os.chmod(dest_dot_desktop, 0777)
	except:
		print("Failed to create desktop icon")

        # PUT YOUR POST-INSTALL SCRIPT HERE or CALL A FUNCTION
        install.run(self)

setup(
    name = APP_NAME,
    version = APP_VERSION,
    description = APP_DESCRIPTION,
    long_description = long_description,
    url = APP_WEBSITE,
    author = APP_DEVELOPER,
    author_email = APP_DEVELOPER_EMAIL,
    license='GPL',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Programming Language :: Python :: 2.7',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
    keywords='Google Drive client Linux Python',
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),

    cmdclass={
        'install': PostInstallCommand,
    },
    package_data={
        'GoSync':['resources/*.png'],
    },

    install_requires=['google-api-python-client', 'pydrive', 'watchdog'],
    entry_points={
        'console_scripts':[
            'GoSync=GoSync.GoSync:main',
        ],
    },
)

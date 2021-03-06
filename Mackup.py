import paho.mqtt.publish as publish
from shutil import copy, copy2, rmtree
from datetime import datetime
from pathlib import Path
import os
import stat
import time
import logging
import zipfile

class Mackup:

    TODAY = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][datetime.today().weekday()]
    BUSY = 'busy'
    ERROR = 'error'
    FINISHED = 'done'

    def __init__(self, device_name, script_folder='.', samba_folder='', server='pinas/backup'):
        self.server = server
        self.device_name = device_name
        self.samba_folder = Path(samba_folder)
        self.script_folder = Path(script_folder)

        # / Path(self.TODAY) appears twice as outer is the backup folder and inner holds the backup zip and log
        self.backup_folder = self.samba_folder / Path(self.device_name) / Path(self.TODAY) / Path(self.TODAY)
        self.ignore_folders_list = self.script_folder / Path('ignore.cfg')
        self.log_file = self.samba_folder / Path(self.device_name) / Path(self.TODAY) / Path(f'{self.TODAY}_log.txt')

        if not self.log_file.exists():
            self.log_file.parent.mkdir(exist_ok=True, parents=True)

        logging.basicConfig(filename=self.log_file,
                            filemode='w',
                            format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                            datefmt='%H:%M:%S',
                            level=logging.DEBUG)


    @property
    def save_folders(self):
        self.backup_folders_list = self.script_folder / Path('list.cfg')
        txt = open(self.backup_folders_list, 'r')
        return [Path(line) for line in txt.read().splitlines()]

    """
    def wait_for_previous(self, previous_device, follow_order=True, timeout=30, wait_time=30):
        logging.info('Waiting for previous device...')

        while True:
            dweet = dweepy.get_latest_dweet_for('Mackup')[0]
            dweet_device = dweet['content']['device']

            if dweet['content']['status'] == self.BUSY:
                time.sleep(wait_time)
            else:
                if dweet_device == previous_device:
                    logging.info('Previous Device finished, continuing')
                    break
                else:
                    if follow_order:
                        print(f'Pinas not busy but {previous_device} was not last to go and follow_order is True...')
                        time.sleep(wait_time)
                    else:
                        logging.warning(f'Pinas not busy, backing up {self.device_name} out of order...')
    """


    
    def run_backup(self):
        try:
            self.__backup()
        except Exception as e:
            print(e)
            self.__post_mqtt(self.ERROR)
            logging.critical(f'Backup Crashed!\n{e}')

    def __backup(self):
        print(f'Starting {self.device_name} Back Up!')
        logging.info(f'Starting {self.device_name} Back Up!')

        self.__post_mqtt(self.BUSY)

        self.backup_folder.mkdir(exist_ok=True, parents=True)
        
        Z = self.backup_folder.parent / Path(self.TODAY + '.zip')
        if Z.exists():
            Z.unlink()
            print('Removed Previous Week Backup')
            logging.info('Removed Previous Week Backup')
        else:
            print('No Previous Week Backup Found')
            logging.info('No Previous Week Backup Found')

        print('Starting Backup...')
        logging.info('Starting Backup...')
        for folder in self.save_folders:
            print(f'Current Folder: {folder.stem}')
            logging.info(f'Current Folder: {folder.stem}')
            self.__copy_directory(folder)
            print('Done!')
            logging.info('Done!')

        print('Zipping Folder')
        logging.info('Zipping Folder')
        self.__zip_backup()

        print('Deleting Unzipped Folder')
        logging.info('Deleting Unzipped Folder')
        self.__delete_folder()

        self.__post_mqtt(self.FINISHED)

        print(f'{self.device_name} Finished!')
        logging.info(f'{self.device_name} Finished!')

    def __copy_directory(self, copy_folder):
        # Make base folder
        base_destination_folder = self.backup_folder / copy_folder.stem
        base_destination_folder.mkdir()
        # Copy everything from p to c
        for item in copy_folder.glob('**/*'):
            dest = base_destination_folder / item.relative_to(copy_folder)
            if item.is_file():
                try:
                    copy2(str(item), str(dest))
                except:
                    print(f'Error: copy2 failed for {str(item)}, using copy')
                    logging.warning(f'copy2 failed for {str(item)}, using copy')
                    copy(str(item), str(dest))
            else:
                dest.mkdir(parents=True)

    def __delete_folder(self):
        def readonly_handler(func, path, execinfo): 
            os.chmod(path, stat.S_IWRITE)
            func(path)
        rmtree(str(self.backup_folder), onerror=readonly_handler)

    def __zip_backup(self):
        def zipdir(path, ziph):
            for item in self.backup_folder.glob('**/*'):
                if item.is_file():
                    ziph.write(item, arcname=item.relative_to(self.backup_folder))

        zipf = zipfile.ZipFile(f'{str(self.backup_folder)}.zip', 'w', zipfile.ZIP_DEFLATED, allowZip64=True)
        zipdir(str(self.backup_folder), zipf)
        zipf.close()

    def mount_samba(self):
        os.system(f"mount_smbfs //pi@{self.server} '{self.samba_folder}'")
    
    def __post_mqtt(self, status):
        Broker = '192.168.1.2'
        pub_topic = f'Mackup/{self.device_name}'.replace(' ', '-')
        publish.single(pub_topic, status, hostname=Broker, port=1883)
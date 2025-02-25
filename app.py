import os
import time
import shutil
import json
import logging
import pandas as pd
from datetime import datetime
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import sys
import daemon  # You'll need to install python-daemon
from daemon import pidfile

class FileOrganizer(FileSystemEventHandler):
    def __init__(self, download_dir):
        self.download_dir = download_dir
        self.load_config()
        self.setup_logging()
        self.log_file = os.path.join(self.download_dir, 'file_organizer_logs', 'file_records.xlsx')
        self.initialize_excel_log()
        self.tracked_files = set()  # Add tracking set

    def setup_logging(self):
        log_dir = os.path.join(self.download_dir, 'file_organizer_logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f'organizer_{datetime.now().strftime("%Y%m%d")}.log')
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(message)s'
        )

    def load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        default_config = {
            'categories': {
                'Images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp'],
                'Documents': ['.pdf', '.doc', '.docx', '.txt', '.xlsx', '.csv'],
                'Videos': ['.mp4', '.mov', '.avi', '.mkv'],
                'Audio': ['.mp3', '.wav', '.flac'],
                'Archives': ['.zip', '.rar', '.7z', '.tar', '.gz'],
                'Others': []
            },
            'organize_by_date': True,
            'handle_duplicates': True,
            'size_categories': {
                'Small': 1024 * 1024,  # 1MB
                'Medium': 1024 * 1024 * 50,  # 50MB
                'Large': float('inf')
            }
        }

        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            self.config = default_config
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=4)

        self.file_categories = self.config['categories']

    def initialize_excel_log(self):
        log_dir = os.path.join(self.download_dir, 'file_organizer_logs')
        os.makedirs(log_dir, exist_ok=True)
        
        if not os.path.exists(self.log_file):
            df = pd.DataFrame(columns=[
                'Filename', 'Category', 'Original Location', 
                'Current Location', 'Size (bytes)', 'Date Moved',
                'Date Modified', 'Status', 'File Extension'
            ])
            df.to_excel(self.log_file, index=False)

    def update_file_record(self, file_name, category, original_path, new_path, file_size):
        try:
            if os.path.exists(self.log_file):
                df = pd.read_excel(self.log_file)
            else:
                df = pd.DataFrame(columns=[
                    'Filename', 'Category', 'Original Location', 
                    'Current Location', 'Size (bytes)', 'Date Moved',
                    'Date Modified', 'Status', 'File Extension'
                ])

            new_record = pd.DataFrame([{
                'Filename': file_name,
                'Category': category,
                'Original Location': original_path,
                'Current Location': new_path,
                'Size (bytes)': file_size,
                'Date Moved': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'Date Modified': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'Status': 'Active',
                'File Extension': os.path.splitext(file_name)[1]
            }])

            df = pd.concat([df, new_record], ignore_index=True)
            df.to_excel(self.log_file, index=False)
            
        except Exception as e:
            logging.error(f"Error updating Excel log: {str(e)}")

    def get_unique_filename(self, destination):
        if not os.path.exists(destination):
            return destination
        
        base, ext = os.path.splitext(destination)
        counter = 1
        while os.path.exists(f"{base}_{counter}{ext}"):
            counter += 1
        return f"{base}_{counter}{ext}"

    def get_size_category(self, file_size):
        for category, limit in self.config['size_categories'].items():
            if file_size <= limit:
                return category
        return 'Large'

    def track_file_movement(self, event, movement_type="Moved In"):
        """Track files being moved into or within the directory"""
        try:
            df = pd.read_excel(self.log_file)
            file_path = event.src_path if movement_type == "Moved Out" else event.dest_path
            file_name = os.path.basename(file_path)
            file_stat = os.stat(file_path) if os.path.exists(file_path) else None
            
            new_record = pd.DataFrame([{
                'Filename': file_name,
                'Category': 'Pending',
                'Original Location': event.src_path,
                'Current Location': event.dest_path if hasattr(event, 'dest_path') else event.src_path,
                'Size (bytes)': file_stat.st_size if file_stat else 0,
                'Date Moved': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'Date Modified': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'Status': movement_type,
                'File Extension': os.path.splitext(file_name)[1]
            }])
            
            df = pd.concat([df, new_record], ignore_index=True)
            df.to_excel(self.log_file, index=False)
            logging.info(f"File {movement_type}: {file_name}")
            
        except Exception as e:
            logging.error(f"Error tracking file movement: {str(e)}")

    def on_created(self, event):
        if event.is_directory:
            return
        # Track new files
        self.track_file_movement(event, "Created")
        self.organize_file(event.src_path)

    def on_modified(self, event):
        if event.is_directory:
            return
        self.organize_file(event.src_path)

    def on_deleted(self, event):
        if event.is_directory:
            return
        try:
            df = pd.read_excel(self.log_file)
            file_name = os.path.basename(event.src_path)
            mask = df['Filename'] == file_name
            if any(mask):
                df.loc[mask, 'Status'] = 'Deleted'
                df.loc[mask, 'Date Modified'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                df.to_excel(self.log_file, index=False)
            logging.info(f"File deleted: {file_name}")
        except Exception as e:
            logging.error(f"Error updating delete record: {str(e)}")

    def on_moved(self, event):
        if event.is_directory:
            return

        # Track files moving in or out of the watched directory
        if self.download_dir in event.dest_path:
            if self.download_dir not in event.src_path:
                # File moved into directory
                self.track_file_movement(event, "Moved In")
                self.organize_file(event.dest_path)
            else:
                # File moved within directory
                self.track_file_movement(event, "Internal Move")
        elif self.download_dir in event.src_path:
            # File moved out of directory
            self.track_file_movement(event, "Moved Out")

    def organize_file(self, file_path):
        if any(file_path.endswith(ext) for ext in ['.crdownload', '.part', '.download', '.tmp']):
            return
            
        if not os.path.exists(file_path):
            return

        # Add to tracked files
        self.tracked_files.add(os.path.basename(file_path))
        
        file_ext = os.path.splitext(file_path)[1].lower()
        file_stat = os.stat(file_path)
        file_date = datetime.fromtimestamp(file_stat.st_mtime)
        file_size = file_stat.st_size

        category = 'Others'
        for cat, extensions in self.file_categories.items():
            if file_ext in extensions:
                category = cat
                break

        category_path = os.path.join(self.download_dir, category)
        
        if self.config['organize_by_date']:
            category_path = os.path.join(category_path, 
                                       str(file_date.year), 
                                       file_date.strftime("%B"))

        if 'organize_by_size' in self.config and self.config['organize_by_size']:
            size_category = self.get_size_category(file_size)
            category_path = os.path.join(category_path, size_category)

        os.makedirs(category_path, exist_ok=True)

        file_name = os.path.basename(file_path)
        destination = os.path.join(category_path, file_name)

        if self.config['handle_duplicates']:
            destination = self.get_unique_filename(destination)

        try:
            shutil.move(file_path, destination)
            self.update_file_record(
                file_name=os.path.basename(file_path),
                category=category,
                original_path=file_path,
                new_path=destination,
                file_size=file_stat.st_size
            )
            logging.info(f"Moved {file_name} to {os.path.relpath(destination, self.download_dir)}")
            print(f"Moved {file_name} to {category}")
        except Exception as e:
            logging.error(f"Error moving {file_name}: {str(e)}")
            print(f"Error moving {file_name}: {str(e)}")

    def organize_existing_files(self):
        print("Organizing existing files...")
        for filename in os.listdir(self.download_dir):
            file_path = os.path.join(self.download_dir, filename)
            if os.path.isfile(file_path):
                self.organize_file(file_path)
        print("Finished organizing existing files")

def run_watcher():
    download_dir = os.path.expanduser("~/Downloads")
    event_handler = FileOrganizer(download_dir)
    event_handler.organize_existing_files()
    
    observer = Observer()
    observer.schedule(event_handler, download_dir, recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--daemon':
        # Run as daemon
        pid_file = '/tmp/file_watcher.pid'
        with daemon.DaemonContext(
            working_directory='/',
            pidfile=pidfile.TimeoutPIDLockFile(pid_file),
            stdout=open('/tmp/file_watcher.log', 'w+'),
            stderr=open('/tmp/file_watcher.err', 'w+')
        ):
            run_watcher()
    else:
        # Run normally
        run_watcher()

if __name__ == "__main__":
    main()

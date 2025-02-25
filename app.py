import os
import time
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class FileOrganizer(FileSystemEventHandler):
    def __init__(self, download_dir):
        self.download_dir = download_dir
        self.file_categories = {
            'Images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp'],
            'Documents': ['.pdf', '.doc', '.docx', '.txt', '.xlsx', '.csv'],
            'Videos': ['.mp4', '.mov', '.avi', '.mkv'],
            'Audio': ['.mp3', '.wav', '.flac'],
            'Archives': ['.zip', '.rar', '.7z', '.tar', '.gz'],
            'Others': []
        }

    def on_created(self, event):
        if event.is_directory:
            return
        # Add delay before processing new files
        time.sleep(3)  # Wait 3 seconds
        self.organize_file(event.src_path)

    def on_modified(self, event):
        if event.is_directory:
            return
        # Add delay before processing modified files
        time.sleep(3)  # Wait 3 seconds
        self.organize_file(event.src_path)

    def organize_file(self, file_path):
        # Ignore temporary files and partial downloads
        if any(file_path.endswith(ext) for ext in ['.crdownload', '.part', '.download', '.tmp']):
            return
            
        if not os.path.exists(file_path):
            return

        file_ext = os.path.splitext(file_path)[1].lower()
        category = 'Others'

        # Find the right category for the file
        for cat, extensions in self.file_categories.items():
            if file_ext in extensions:
                category = cat
                break

        # Create category directory if it doesn't exist
        category_path = os.path.join(self.download_dir, category)
        os.makedirs(category_path, exist_ok=True)

        # Move file to appropriate category folder
        file_name = os.path.basename(file_path)
        destination = os.path.join(category_path, file_name)

        try:
            shutil.move(file_path, destination)
            print(f"Moved {file_name} to {category}")
        except Exception as e:
            print(f"Error moving {file_name}: {str(e)}")

    def organize_existing_files(self):
        print("Organizing existing files...")
        for filename in os.listdir(self.download_dir):
            file_path = os.path.join(self.download_dir, filename)
            if os.path.isfile(file_path):
                self.organize_file(file_path)
        print("Finished organizing existing files")

def main():
    # Get user's download directory
    download_dir = os.path.expanduser("~/Downloads")
    
    # Create event handler and organize existing files
    event_handler = FileOrganizer(download_dir)
    event_handler.organize_existing_files()
    
    # Create and start the observer
    observer = Observer()
    observer.schedule(event_handler, download_dir, recursive=False)
    observer.start()

    print(f"Watching Downloads folder: {download_dir}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\nFile watcher stopped")
    
    observer.join()

if __name__ == "__main__":
    main()

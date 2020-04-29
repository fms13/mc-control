#!/usr/bin/env python3
# \author fms13
# \date April 30, 2020
#
# \brief Opens a file and tries a number of matching lines in a row
#
# Under development, not working currently.
#

import sys
import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
    
if __name__ == "__main__":
    # directory where file is:
    path = '/home/homeassistant/.homeassistant/'
    file_name = "OZW_Log.txt"
    path_and_file_name = path + file_name
    
    # open file
    f = open(path_and_file_name, 'r')
    
    # go to the end of the file:
    f.seek(0, 2)

    my_event_handler = FileSystemEventHandler()

    def on_modified(event):
        #print(f"{event.src_path} has been modified")
        if event.src_path == path_and_file_name:
            print("new Z-Wave messages")
            buf = f.readline()
            print(buf)
            while buf:
                buf = f.readline()
                print(buf)
    
    my_event_handler.on_modified = on_modified
    
    my_observer = Observer()
    my_observer.schedule(my_event_handler, path, recursive=False)
    
    print("Starting observer")
    my_observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        my_observer.stop()
        my_observer.join()
        
    
    f.close()
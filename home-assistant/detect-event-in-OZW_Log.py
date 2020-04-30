#!/usr/bin/env python3
# \author fms13
# \date April 30, 2020
#
# \brief Opens a file and tries a number of matching lines in a row
#
# Under development, not working currently.
#
# The script is looking for the first and the last of these three lines as an example:
#     Node004, Received a MultiChannelEncap from node 4, endpoint 1
#     Node004, Received SwitchBinary report from node 4: level=On
#     Node004, Refreshed Value: old value=true, new value=true, type=bool
#
# The node number and the endpoints to be checked can be configured.

import sys
import time
import argparse
import pycurl
import json
import io

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import collections

# search line:
node_enpoint_numbers = [ [ 4, [1, 2] ] ]
search_strings_1 = []

# the Home Assistant authentication token, to be obtained from
home_assistant_authentication_token = ""

# ip and port of Home Assistant instance, e.g. 192.168.0.10:8123
home_assistant_ip_port = ""

if __name__ == "__main__":

#    parser = argparse.ArgumentParser()
#    parser.add_argument("home_assistant_url", type=str, help="the URL of the Home Assistant instance to call in case an override was detected")

    # directory where file is:
    path = '/home/homeassistant/.homeassistant/'
    path = './'
    file_name = "OZW_Log.txt"
    path_and_file_name = path + file_name

    # open file
    f = open(path_and_file_name, 'r')

    # go to the end of the file:
    f.seek(0, 2)

    print("checking for these nodes and endpoints ")
    for node in node_enpoint_numbers:
        for endpoint in node[1]:
            print(f"Node{node[0]:03d}, endpoint {endpoint}")

    # create the strings wer're searching for in step 1:
    print("search strings for step 1:")
    for node in node_enpoint_numbers:
        search_strings_1.append(f"Node{node[0]:03d}, Refreshed Value: old value=false, new value=true, type=bool")
        print(search_strings_1[-1])

    # create a list of strings to store the last three lines of the file:
    lines = collections.deque(maxlen=3)

    my_event_handler = FileSystemEventHandler()

    def on_modified(event):
        #print(f"{event.src_path} has been modified")
        if event.src_path == path_and_file_name:
            print("new Z-Wave messages")

            while True:
                buf = f.readline()
                #print("buf: ", buf)
                if not buf:
                    break

                lines.append(buf)

                # check if one of the search strings is in the last line:
                for idx, search_string in enumerate(search_strings_1):
                    #print(f"searching for {search_string} in {buf}")
                    if lines[-1].find(search_string) != -1:
                        #print("found search string 1: ", buf)
                        # check for endpoints in lines that came in two lines before:
                        for endpoint in node_enpoint_numbers[idx][1]:
                            node = node_enpoint_numbers[idx][0]
                            search_string_2 = f"Node{node:03d}, Received a MultiChannelEncap from node {node}, endpoint {endpoint}"
                            #print(f"step 2: searching for {search_string_2} in {lines[-3]}")
                            if lines[-3].find(search_string_2) != -1:
                                print("found search string 2 in: ", lines[-3])

                                # using pycurl for this curl POST request:
                                # #print(f"calling /usr/bin/curl -X POST -H \"Authorization: Bearer {home_assistant_authentication_token}\" -H \"Content-Type: application/json\" -d \'{{\"state\": \"on\"}}\' http://{home_assistant_ip_port}/api/states/input_boolean.override_node{node}_endpoint{endpoint}")
                                pycurl_connect = pycurl.Curl()
                                pycurl_connect.setopt(pycurl.URL, f"http://{home_assistant_ip_port}/api/states/input_boolean.override_node{node}_endpoint{endpoint}")
                                pycurl_connect.setopt(pycurl.HTTPHEADER, [f'Authorization: Bearer {home_assistant_authentication_token}',
                                          'Content-Type: application/json'])
                                pycurl_connect.setopt(pycurl.POST, 1)
                                data = json.dumps({"state": "on"})
                                data_as_file_object = io.StringIO(data)
                                pycurl_connect.setopt(pycurl.READDATA, data_as_file_object)
                                pycurl_connect.setopt(pycurl.POSTFIELDSIZE, len(data))
                                pycurl_connect.perform()

            print("done.")

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
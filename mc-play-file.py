##
# @file mc-play-file.py
#
# @date Jan 14, 2018
# @author fms13
#
# This script plays a single file exported by a DLNA server on a Yamaha Musiccast-compatible
# device. Currently only the device's 'main' zone is accessed. 
#
# Command line parameters:
#
# -d, --device: IP address or host name of musiccast device
# -p, --path: path to file to be played on musiccast device play
# -v, --volume: Volume to be set before file starts to play. According to Yamaha's documentation, range
#               differs from device to device.
#
# Example call:
#
# mc-play-single-file.py -d 192.168.0.3 'raspberrypi: minidlna/Browse Folders/voice-message-01'
#
# Known issues: 
#
#  + Contains still debug output
#
# Documentation on how to control Yamaha's MusicCast devices: YXC_API_Spec_Basic.pdf
#

import requests
import argparse

##
# @brief dictionary with error codes:
error_messages = {
    0: "Successful request", 1: "Initializing", 2: "Internal Error",
    3: "Invalid Request (A method did not exist, a method was not appropriate etc.)",
    4: "Invalid Parameter (Out of range, invalid characters etc.)", 
    5: "Guarded (Unable to setup in current status etc.)", 6: "Time Out", 
    99: "Firmware Updating", 
    100: "Streaming Service related error Access Error", 
    101: "Streaming Service related error: Other Errors", 
    102: "Streaming Service related error: Wrong User Name", 
    103: "Streaming Service related error: Wrong Password", 
    104: "Streaming Service related error: Account Expired", 
    105: "Streaming Service related error: Account Disconnected/Gone Off/Shut Down", 
    106: "Streaming Service related error: Account Number Reached to the Limit", 
    107: "Streaming Service related error: Server Maintenance", 
    108: "Streaming Service related error: Invalid Account", 
    109: "Streaming Service related error: License Error", 
    110: "Streaming Service related error: Read Only Mode", 
    111: "Streaming Service related error: Max Stations", 
    112: "Streaming Service related error: Access Denied"
}

##
# @brief Error handler function. Raises an exception with an error message in case of
# an error_code that differs from zero.
#
# @param error_code Error code
def error_handler(error_code):
    # is there an error?
    if error_code != 0:
        # is the error_code contained in dictionary with error messages?
        if error_code not in error_messages:
            # no:
            raise RuntimeError("Unknown error code {}".format(error_code))
        # yes, output error message:
        raise RuntimeError("Error: {}".format(error_messages[error_code]))

    # no error:
    return

##
# @brief Turns a musiccast device on
#
# @param ip_addr IP address of the device
def turn_on(ip_addr):
    url = 'http://{}/YamahaExtendedControl/v1/main/setPower?power=on'.format(ip_addr)
    response = requests.get(url).json()

    error_handler(response['response_code'])
    
    return response

##
# @brief Sets the volume of a musiccast device
#
# @param ip_addr IP address of the device
# @param volume Volume level to be set. According to documentation ranges differ from device to device
def set_volume(ip_addr, volume):    
    url = 'http://{}/YamahaExtendedControl/v1/main/setVolume?volume={}'.format(ip_addr, volume)
    response = requests.get(url).json()

    error_handler(response['response_code'])
    
    return response

##
# @brief Sets the repeat status.
#
# Repeat status can only be toggled, so the status is queried first and then toggled in case it
# differs.
#
# @param ip_addr IP address of the device
# @param new_status can be 'off', 'one', 'all'
def set_repeat(ip_addr, new_status):
    if new_status != "off" and new_status != "one" and new_status != "all":
        raise RuntimeError('set_repeat: new_status can only be one of off, one, and all, but it is {}.'.format(new_status))

    tries = 0
            
    while True:
        # get current status:
        url = 'http://{}/YamahaExtendedControl/v1/netusb/getPlayInfo'.format(ip_addr)
        response = requests.get(url).json()

        error_handler(response['response_code'])
                    
        if response['repeat'] == new_status:            
            print 'set_repeat: present status ({}) is equal to new_status, no action'.format(response['repeat'])    
            break
        else:
            print 'set_repeat: present status ({}) is not equal to new_status ({}), toggling repeat'.format(response['repeat'], new_status)    

            # toggle repeat status:
            url = 'http://{}/YamahaExtendedControl/v1/netusb/toggleRepeat'.format(ip_addr)
            response = requests.get(url).json()

            error_handler(response['response_code'])
                        
        tries += 1
        
        if tries > 4:
            raise RuntimeError('set_repeat: could not set new repeat status {}: too many tries.'.format(new_status))
            
##
# @brief Queries the list of entries of the 'server' input of the current directory.
#
# @param ip_addr IP address of the device
def get_list(ip_addr):
    # start index:
    index = 0

    entries = []

    while True:
        url = 'http://{}/YamahaExtendedControl/v1/netusb/getListInfo?input=server&size=8&index={}'.format(ip_addr, index)
        response = requests.get(url).json()

        error_handler(response['response_code'])

        #print 'index: ', index, 'dict: ', dict
        for entry in response['list_info']:
            #print 'appending ', entry['text']
            entries.append(entry['text'])
        
        index += 8
        
        if index > response['max_line']:
            break
        
    return entries, response
    
##
# @brief Selects a list item of the 'server' input of the current directory.
#
# @param ip_addr IP address of the device
def select_item(ip_addr, item):
    # get list:
    entries, last_dict = get_list(ip_addr)
    
    print 'entries: ', entries
    # get index for zwerg:
    found = False
    for idx, server in enumerate(entries):
        if server == item:
            print 'found index: {} for entry {}'.format(idx, item)
            found = True
            break
    
    if found == False:
        raise RuntimeError('item {} not found in dict {}'.format(item, entries))

    # get list for zwerg:
    url = 'http://{}/YamahaExtendedControl/v1/netusb/setListControl?type=select&index={}'.format(ip_addr, idx)
    response = requests.get(url).json()    

    error_handler(response['response_code'])
    
    return response

##
# @brief Goes up to the root level of the server input.
#
# @param ip_addr IP address of the device    
def go_to_root_level(ip_addr):
    # setup get:
    url = 'http://{}/YamahaExtendedControl/v1/main/prepareInputChange?input=server&lang=en'.format(ip_addr)
    response = requests.get(url).json()

    error_handler(response['response_code'])
    
    entries, last_response = get_list(ip_addr)
    menu_layer_start = last_response['menu_layer']
    #print 'menu_layer start: ', menu_layer_start 
    
    if menu_layer_start > 0:    
        # go up until root level:
        for k in range(menu_layer_start):
            url = 'http://{}/YamahaExtendedControl/v1/netusb/setListControl?type=return'.format(ip_addr)
            response = requests.get(url).json()
            # TODO check response code
    
    entries, last_response = get_list(ip_addr)
    #print 'menu_layer end: ', last_response['menu_layer']
    
    # show list:
    return

##
# @brief Delves down the directory hierarchy to a specific path. 
#
# @param ip_addr IP address of the device
# @param path_entries Target path as list
def browse_to_path(ip_addr, path_entries):
    print 'going to root folder...'
    go_to_root_level(ip_addr)
    
    for path_entry in path_entries:
        # change directory
        print 'going to {}...'.format(path_entry)
        select_item(ip_addr, path_entry)
        dict = get_list(ip_addr)
        
    return dict


##
# @brief Plays a specific file in the current directory for the server input. 
#
# @param ip_addr IP address of the device
# @param file File to play
def play(ip_addr, file):
    # get list:
    entries, last_dict = get_list(ip_addr)

    # get index for file:
    found = False
    for idx, server in enumerate(entries):
        if server == file:
            print 'found index: {} for file {}'.format(idx, file)
            found = True
            break
    
    if found == False:
        raise RuntimeError('file {} not found in dict {}'.format(file, dict))

    # play this file:
    url = 'http://{}/YamahaExtendedControl/v1/netusb/setListControl?type=play&index={}'.format(ip_addr, idx)
    response = requests.get(url).json()    
    error_handler(response['response_code'])

# Main

# setup and parse command line arguments:
parser = argparse.ArgumentParser()
parser.add_argument("-d", "--device", help="musiccast device", type=str, required=True)
parser.add_argument("-p", "--path", help="path to file to play", type=str, required=True)
parser.add_argument("-v", "--volume", help="volume", type=str, required=True)
args = parser.parse_args()

print 'mc-play-file start: selected device: {}, path of file to be played: {}'.format(args.device, args.path)

# turn on musiccast device
turn_on(args.device)

# set volume
set_volume(args.device, args.volume)

# set repeat to off:
set_repeat(args.device, 'off')

# turns the path provided via -p parameter into a list, splitting at slash characters:
path_as_list = args.path.split('/')

# set current directort to directory containing the file (list content but the last item):
browse_to_path(args.device, path_as_list[0:len(path_as_list) - 1])

# play file (last entry in provided path):
play(args.device, path_as_list[-1])

print 'mc-play-file done.'

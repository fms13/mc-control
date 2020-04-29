#!/usr/bin/env python3

# full path and file name:
file_name = '/home/homeassistant/.homeassistant/OZW_Log.txt'

# open file
f = open(file_name, 'r')

# go to the end of the file:
f.seek(0, 2)

f.close()
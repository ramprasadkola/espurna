#!/usr/bin/env python
# coding=utf-8
# -------------------------------------------------------------------------------
# ESPurna OTA manager
# xose.perez@gmail.com
#
# Requires PlatformIO Core
# -------------------------------------------------------------------------------
from __future__ import print_function

import argparse
import re
import socket
import subprocess
import sys
from time import sleep

from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf

try:
    # noinspection PyUnresolvedReferences
    input = raw_input  # Python2    *!! redefining build-in input.
except NameError:
    pass  # Python3

# -------------------------------------------------------------------------------

devices = []
description = "ESPurna OTA Manager v0.1"


# -------------------------------------------------------------------------------

def on_service_state_change(zeroconf, service_type, name, state_change):
    """
    Callback that adds discovered devices to "devices" list
    """

    if state_change is ServiceStateChange.Added:
        info = zeroconf.get_service_info(service_type, name)
        if info:
            hostname = info.server.split(".")[0]
            device = {
                'hostname': hostname.upper(),
                'ip': socket.inet_ntoa(info.address)
            }
            device['app'] = info.properties.get('app_name', '')
            device['version'] = info.properties.get('app_version', '')
            device['device'] = info.properties.get('target_board', '')
            if 'mem_size' in info.properties:
                device['mem_size'] = info.properties.get('mem_size')
            if 'sdk_size' in info.properties:
                device['sdk_size'] = info.properties.get('sdk_size')
            if 'free_space' in info.properties:
                device['free_space'] = info.properties.get('free_space')
            devices.append(device)


def list_devices():
    """
    Shows the list of discovered devices
    """
    output_format="{:>3}  {:<25}{:<25}{:<15}{:<15}{:<30}{:<10}{:<10}{:<10}"
    print(output_format.format(
        "#",
        "HOSTNAME",
        "IP",
        "APP",
        "VERSION",
        "DEVICE",
        "MEM_SIZE",
        "SDK_SIZE",
        "FREE_SPACE"
    ))
    print("-" * 146)

    index = 0
    for device in devices:
        index = index + 1
        print(output_format.format(
            index,
            device.get('hostname', ''),
            device.get('ip', ''),
            device.get('app', ''),
            device.get('version', ''),
            device.get('device', ''),
            device.get('mem_size', ''),
            device.get('sdk_size', ''),
            device.get('free_space', ''),
        ))

    print()


def get_boards():
    """
    Grabs board types fro hardware.h file
    """
    boards = []
    for line in open("espurna/config/hardware.h"):
        m = re.search(r'defined\((\w*)\)', line)
        if m:
            boards.append(m.group(1))
    return sorted(boards)

def get_empty_board():
    """
    Returns the empty structure of a board to flash
    """
    board = {'board': '', 'ip': '', 'size': 0, 'auth': '', 'flags': ''}
    return board

def get_board_by_index(index):
    """
    Returns the required data to flash a given board
    """
    board = {}
    if 1 <= index and index <= len(devices):
        device = devices[index - 1]
        board['hostname'] = device.get('hostname')
        board['board'] = device.get('device', '')
        board['ip'] = device.get('ip', '')
        board['size'] = int(device.get('mem_size', 0) if device.get('mem_size', 0) == device.get('sdk_size', 0) else 0) / 1024
    return board

def get_board_by_hostname(hostname):
    """
    Returns the required data to flash a given board
    """
    hostname = hostname.lower()
    for device in devices:
        if device.get('hostname', '').lower() == hostname:
            board = {}
            board['hostname'] = device.get('hostname')
            board['board'] = device.get('device')
            if not board['board']:
                return None
            board['ip'] = device.get('ip')
            if not board['ip']:
                return None
            board['size'] = int(device.get('sdk_size', 0)) / 1024
            if board['size'] == 0:
                return None
            return board
    return None

def input_board():
    """
    Grabs info from the user about what device to flash
    """

    # Choose the board
    try:
        index = int(input("Choose the board you want to flash (empty if none of these): "))
    except:
        index = 0
    if index < 0 or len(devices) < index:
        print("Board number must be between 1 and %s\n" % str(len(devices)))
        return None

    board = get_board_by_index(index);

    # Choose board type if none before
    if len(board.get('board', '')) == 0:

        print()
        count = 1
        boards = get_boards()
        for name in boards:
            print("%3d\t%s" % (count, name))
            count = count + 1
        print()
        try:
            index = int(input("Choose the board type you want to flash: "))
        except:
            index = 0
        if index < 1 or len(boards) < index:
            print("Board number must be between 1 and %s\n" % str(len(boards)))
            return None
        board['board'] = boards[index - 1]

    # Choose board size of none before
    if board.get('size', 0) == 0:
        try:
            board['size'] = int(input("Board memory size (1 for 1M, 4 for 4M): "))
        except:
            print("Wrong memory size")
            return None

    # Choose IP of none before
    if len(board.get('ip', '')) == 0:
        try:
            board['ip'] = input("IP of the device to flash (empty for 192.168.4.1): ") or "192.168.4.1"
        except:
            print("Wrong IP")
            return None

    return board


def run(device, env):
    print("Building and flashing image over-the-air...")
    command = "export ESPURNA_IP=\"%s\"; export ESPURNA_BOARD=\"%s\"; export ESPURNA_AUTH=\"%s\"; export ESPURNA_FLAGS=\"%s\"; platformio run --silent --environment %s -t upload"
    command = command % (device['ip'], device['board'], device['auth'], device['flags'], env)
    subprocess.check_call(command, shell=True)


# -------------------------------------------------------------------------------

if __name__ == '__main__':

    # Parse command line options
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("-c", "--core", help="flash ESPurna core", default=0, action='count')
    parser.add_argument("-f", "--flash", help="flash device", default=0, action='count')
    parser.add_argument("-o", "--flags", help="extra flags", default='')
    parser.add_argument("-p", "--password", help="auth password", default='')
    parser.add_argument("-s", "--sort", help="sort devices list by field", default='hostname')
    parser.add_argument("hostnames", nargs='*', help="Hostnames to update")
    args = parser.parse_args()

    print()
    print(description)
    print()

    # Look for sevices
    zeroconf = Zeroconf()
    browser = ServiceBrowser(zeroconf, "_arduino._tcp.local.", handlers=[on_service_state_change])
    sleep(5)
    zeroconf.close()

    if len(devices) == 0:
        print("Nothing found!\n")
        sys.exit(0)

    # Sort list
    field = args.sort.lower()
    if field not in devices[0]:
        print("Unknown field '%s'\n" % field)
        sys.exit(1)
    devices = sorted(devices, key=lambda device: device.get(field, ''))

    # List devices
    list_devices()

    # Flash device
    if args.flash > 0:

        # Board(s) to flash
        queue = []

        # Check if hostnames
        for hostname in args.hostnames:
            board = get_board_by_hostname(hostname)
            if board:
                board['auth'] = args.password
                board['flags'] = args.flags
                queue.append(board)

        # If no boards ask the user
        if len(queue) == 0:
            board = input_board()
            if board:
                board['auth'] = args.password or input("Authorization key of the device to flash: ")
                board['flags'] = args.flags or input("Extra flags for the build: ")
                queue.append(board)

        # If still no boards quit
        if len(queue) == 0:
            sys.exit(0)

        # Flash eash board
        for board in queue:

            # Flash core version?
            if args.core > 0:
                board['flags'] = "-DESPURNA_CORE " + board['flags']

            env = "esp8266-%sm-ota" % board['size']

            # Summary
            print()
            print("HOST  = %s" % board.get('hostname', board['ip']))
            print("IP    = %s" % board['ip'])
            print("BOARD = %s" % board['board'])
            print("AUTH  = %s" % board['auth'])
            print("FLAGS = %s" % board['flags'])
            print("ENV   = %s" % env)

            response = input("\nAre these values right [y/N]: ")
            print()
            if response == "y":
                run(board, env)

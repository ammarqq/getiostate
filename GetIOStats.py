#!/usr/bin/python

# get_io_stats.py # iostat like with configurable interval collection
# Beta version provided "as is", no support guaranteed
# guillaume.ducroix@microsoft.com 

# https://www.kernel.org/doc/Documentation/ABI/testing/procfs-diskstats
# https://www.kernel.org/doc/Documentation/iostats.txt

import os
import sys
import getopt
import time
from datetime import datetime
import platform

SCRIPT_VERSION = "0.5"
HARDLIMIT_TIMETORUN = 120
DEFAULT_TIMETORUN = 2
DEFAULT_COLLECTIONINTERVAL = 0.025
ENHANCED_KERNELVERSION = 2.6
EXCLUDED_DEVICES = []

kernel_version = 2.5


def parse_script_arguments(arg_args):

    _device = None
    _partition = None
    _timeToRun = 0
    _collectionInterval = 0
    _collectionIntervalUnit = "ms"

    try:
        _options, arg_args = getopt.getopt(arg_args,"hd:p:t:i:",["device=","partition=","timetorun=","interval="])
    except getopt.GetoptError:
        show_help()
        sys.exit(2)

    if len(_options) > 1:
        for _option, _argument in _options:
            if _option == '-h':
                show_help()
                sys.exit(2)
            elif _option in ("-d", "--device"):
                _device = _argument.lower()
            elif _option in ("-p", "--partition"):
                # not used yet
                _partition = _argument.lower()
                print("")
                print("Argument not yet implemented.")
                show_help()
                sys.exit(2)
            elif _option in ("-t", "--timetorun"):
                _timeToRun = _argument
                if _timeToRun[len(_timeToRun)-1:len(_timeToRun)].upper() == "H":
                    _timeToRun = int(_timeToRun[0:(len(_timeToRun) - 1)]) * 60
                if _timeToRun[len(_timeToRun)-1:len(_timeToRun)].upper() == "M":
                    _timeToRun = int(_timeToRun[0:(len(_timeToRun) - 1)])
                else:
                    print("")
                    print("Please specify a valid time to run value in hour(s) (H) or minutes (M) with -t/--timetorun.")
                    show_help()
                    sys.exit(2)
            elif _option in ("-i", "--interval"):
                _collectionInterval = _argument
                if _collectionInterval < 1:
                    _collectionIntervalUnit = "milliseconds"
                elif _collectionInterval > 1:
                    _collectionIntervalUnit = "seconds"
                else:
                    _collectionIntervalUnit = "second"
    else:
        show_help()
        sys.exit(2)

    if _device is not None or _partition is not None:
        if _timeToRun == 0:
            _timeToRun = DEFAULT_TIMETORUN
        elif _timeToRun > HARDLIMIT_TIMETORUN:
            print ("")  
            print ("Please specify a time to run less than 2 hours (120 minutes).")
            show_help()
            sys.exit(2)
        if _collectionInterval == 0:
            _collectionInterval = DEFAULT_COLLECTIONINTERVAL
    else:
        print ("")
        print ("Please specify an existing device with -d/--device or an existing partition with -/--partition.")
        show_help()
        sys.exit(2)

    return [_device, _timeToRun, _collectionInterval, _collectionIntervalUnit]


def verify_device_exists(_device):

    if len(_device.split(",")) > 1:
        _devices = []
        if len(_device.split(",")) > 1:
            for _item in _device.split(","):
                _devices.append(_item)

    if len(_devices) == 0:
        print ("No device found matching criteria.")
        print ("Exiting...")
        sys.exit()

    if _device == "all":
        print ("All disks statistics will be collected")


def show_help():
    print ("")
    print ("get_io_stats.py -d <device(s)|all> -t <time to run (H|M)> -i <interval (seconds)>")
    print ("Version: " + SCRIPT_VERSION)
    print ("")
    print ("Collect I/O statistics from devices or partitions on Linux systems.")
    print ("")
    print ("Examples:")
    print (" -> Collect I/O statistics for device sdc during 10 minutes at a 25ms interval")
    print ("get_io_stats.py -d sdc -t 10M -i 0.025")
    print (" -> Collect I/O statistics for all devices during 1 hour at a 1 second interval")
    print ("get_io_stats.py -d all -t 1H -i 1")
    print (" -> Collect I/O statistics for sdc and sdb devices during 15 minutes with default interval (1 second)")
    print ("get_io_stats.py -d sdc,sdb -t 15M")
    print ("")


def init():

    EXCLUDED_DEVICES.append('fd0')
    EXCLUDED_DEVICES.append('sr0')
    EXCLUDED_DEVICES.append('loop0')
    EXCLUDED_DEVICES.append('loop1')
    EXCLUDED_DEVICES.append('loop2')
    EXCLUDED_DEVICES.append('loop3')
    EXCLUDED_DEVICES.append('loop4')
    EXCLUDED_DEVICES.append('loop5')
    EXCLUDED_DEVICES.append('loop6')
    EXCLUDED_DEVICES.append('loop7')
    EXCLUDED_DEVICES.append('loop8')
    EXCLUDED_DEVICES.append('loop9')

    kernel_version_temp = platform.release().replace('"', '')
    return float(kernel_version_temp.split('.')[0] + '.' + kernel_version_temp.split('.')[1])


def update_progressbar(arg_title, arg_iteration, arg_total):
    
    _length = 20
    _fill = "#"

    _percent = ("{0:." + str(2) + "f}").format(100 * (arg_iteration / float(arg_total)))
    _filledLength = int(_length * arg_iteration / arg_total)
    _bar = _fill * _filledLength + '-' * (_length - _filledLength)

    sys.stdout.write('%s |%s| %s%%\r' % (arg_title,_bar, _percent))
    sys.stdout.flush()


def get_device_sector_size(_device):
    
    _sectorSize = 512
    
    try:
        with open("/sys/block/%s/queue/hw_sector_size" % _device, "rt") as f:
            return int(f.read())
    except (IOError, ValueError):
        # Defaukt is 512 bytes since 2.4 kernels
        return _sectorSize


def get_io_stats(_device, _interval, _captureTimeMin):

    _timeToRun = _captureTimeMin * 60 * float(1/_interval)
    _stats = []
    _timeRunning = 0

    if len(_device.split(",")) > 1:
        print (" Capturing I/O usage for multiple disks...")
        _devices = []
        if len(_device.split(",")) > 1:
            for _item in _device.split(","):
                # Create device dict
                _devices.append(_item)
        while _timeRunning <= int(_timeToRun):
            _diskStatsfile = open("/proc/diskstats", "r")
            for line in _diskStatsfile:
                if any(x in line.split() for x in _devices):
                    if line.split()[2] not in EXCLUDED_DEVICES and line.split()[3] not in EXCLUDED_DEVICES:
                        # Do not capture excuded devices
                        _stats.append(datetime.utcnow().strftime('%Y-%m-%d') + " " + datetime.utcnow().strftime('%H:%M:%S.%f')[:-3] + " " + line)
                    continue
            _timeRunning += 1
            _diskStatsfile.close()
            time.sleep(_interval)

    if _device == "all":
        print (" Capturing I/O usage for all disks...")
        while _timeRunning <= int(_timeToRun):
            _diskStatsfile = open("/proc/diskstats", "r")
            for line in _diskStatsfile:
                if line.split()[2] not in EXCLUDED_DEVICES and line.split()[3] not in EXCLUDED_DEVICES:
                    # Do not capture excuded devices
                    _stats.append(datetime.utcnow().strftime('%Y-%m-%d') + " " + datetime.utcnow().strftime('%H:%M:%S.%f')[:-3] + " " + line)
            _timeRunning += 1
            _diskStatsfile.close()
            time.sleep(_interval)
    else:
        print (" Capturing I/O usage for a single disk...")
        # if partition: /sys/block/[device]/[partion]/stat

        if kernel_version >= ENHANCED_KERNELVERSION:
            print (" Capturing from /sys/block")
            while _timeRunning <= int(_timeToRun):
                _diskStatsfile = open('/sys/block/' + _device + '/stat', "r")
                for line in _diskStatsfile:
                    _stats.append(datetime.utcnow().strftime('%Y-%m-%d') + " " + datetime.utcnow().strftime('%H:%M:%S.%f')[:-3] + " " + line)
                _timeRunning += 1
                time.sleep(_interval)
                _diskStatsfile.close()
        else:
            print (" Capturing from /proc/diskstats")
            while _timeRunning <= int(_timeToRun):
                _diskStatsfile = open("/proc/diskstats", "r")
                for line in _diskStatsfile:
                    if _device in line.split():
                        _stats.append(datetime.utcnow().strftime('%Y-%m-%d') + " " + datetime.utcnow().strftime('%H:%M:%S.%f')[:-3] + " " + line)
                        continue
                _timeRunning += 1
                time.sleep(_interval)
                _diskStatsfile.close()

    return _stats


def compute_io_stats(_iostats, _device):

    _deltaTime = 0
    _deltaReads = 0
    _deltaWrites = 0
    _deltaReadSectors = 0
    _deltaWriteSectors = 0
    _rBytes = 0
    _wBytes = 0
    _rMBytes = 0
    _wMBytes = 0
    _previousTime = 0
    _previousReads = 0
    _previousWrites = 0
    _previousRsectors = 0
    _previousWsectors = 0

    _dateTime = datetime.utcnow().strftime('%Y-%m-%d_%H:%M:%S').replace(":","-")

    if _device == "all" or len(_device.split(",")) > 1:
        compute_io_stats_all_disks(_iostats, _device)
    else:
        compute_io_stats_single_disk(_iostats, _device)

    update_progressbar(" Completion", len(_iostats), len(_iostats))


def compute_io_stats_all_disks(_iostats, _device):
    _deltaTime = 0
    _deltaReads = 0
    _deltaWrites = 0
    _deltaReadSectors = 0
    _deltaWriteSectors = 0
    _rBytes = 0
    _wBytes = 0
    _rMBytes = 0
    _wMBytes = 0
    _previousTime = 0
    _previousReads = 0
    _previousWrites = 0
    _previousRsectors = 0
    _previousWsectors = 0

    _dateTime = datetime.utcnow().strftime('%Y-%m-%d_%H:%M:%S').replace(":","-")

    print (" Compute all disks metrics...")

    _uniqueItems = []
    if len(_device.split(",")) > 1:
        for _item in _device.split(","):
            if _item not in EXCLUDED_DEVICES:
                _uniqueItems.append(_item)
    else:
        for _value in _iostats: 
            if (_value.split()[4] not in EXCLUDED_DEVICES) and (_value.split()[4] not in _uniqueItems):
                _uniqueItems.append(_value.split()[4])

    _outputAllfile = "./" + os.uname()[1] + "_all_" + _dateTime + ".log"
    _outputAllfile = open(_outputAllfile, "w")
    _outputAllfile.write("date;time UTC;device;time (ms);delta time (ms);delta reads;delta writes;delta IOPS;delta Bytes read;delta Bytes written;delta Bytes;delta MBytes read;delta MBytes written;total MBytes;reads;writes;reads merged;writes merged;sector read;sector written;read time (ms);write time (ms);i/o in progress;time spent doing i/o (ms);weighted time spent doing i/o (ms);sector size\n")

    _iCountStats = 0
    for _item in _uniqueItems:
        _sectorSize = get_device_sector_size(_item)
        _outputfile = "./" + os.uname()[1] + "_" + _item + "_" + _dateTime + "_" + str(int(_sectorSize)) + ".log"

        _outputfile = open(_outputfile, "w") 
        _outputfile.write("date;time UTC;device;time (ms);delta time (ms);delta reads;delta writes;delta IOPS;delta Bytes read;delta Bytes written;delta Bytes;delta MBytes read;delta MBytes written;total MBytes;reads;writes;reads merged;writes merged;sector read;sector written;read time (ms);write time (ms);i/o in progress;time spent doing i/o (ms);weighted time spent doing i/o (ms)\n")

        for _stat in _iostats:
            update_progressbar(" Completion", _iCountStats, len(_iostats))

            if _item == _stat.split()[4]:
                _totalTime = (int(_stat.split()[1][:2])*3600000) + (int(_stat.split()[1][3:5])*60000) + (int(_stat.split()[1][6:8])*1000) + int(_stat.split()[1][9:13])
                _deltaTime = _totalTime - _previousTime
                _previousTime = _totalTime

                if _iCountStats == 0:
                    _deltaTime = 0
                    _deltaReads = 0
                    _deltaWrites = 0
                    _deltaReadSectors = 0
                    _deltaWriteSectors = 0
                    _rBytes = 0
                    _wBytes = 0
                    _rMBytes = 0
                    _wMBytes = 0
                else:
                    if len(_stat.split()) == 17:
                        # Linux 2.4
                        print ("  Looks like kernel version is lower than 2.6 (" + _item + ")")
                    elif len(_stat.split()) == 16 or len(_stat.split()) == 20:
                        # Linux 2.6+ for a device or partition (using /proc/disktats)
                        # [5] reads [6] reads merged [7] sectors read [8] ms spent reading [9] writes [10] writes merged [11] sectors written [12] ms spent writing [13] I/O in progress [14] ms doing I/O [15] weighted ms doing I/Os
                        _deltaReads = int(_stat.split()[5]) - _previousReads
                        _deltaWrites = int(_stat.split()[9]) - _previousWrites
                        _deltaReadSectors = int(_stat.split()[7]) - _previousRsectors
                        _deltaWriteSectors = int(_stat.split()[11]) - _previousWsectors
                    elif len(_stat.split()) == 9:
                        # Linux 2.6+ for a partition
                        # [3] reads [4] sectors read [5] writes [6] sectors written
                        print ("  Looks like partition data (" + _item + ")")

                    _rBytes = _deltaReadSectors * int(_sectorSize)
                    _wBytes = _deltaWriteSectors * int(_sectorSize)
                    _rMBytes = round(float(_rBytes) / (1024 ** 2), 2)
                    _wMBytes = round(float(_wBytes) / (1024 ** 2), 2)

                    _outputLine = ''
                    if len(_stat.split()) == 17:
                        # Linux 2.4
                        print ("  Looks like kernel version is lower than 2.6 (" + _item + ")")
                    if len(_stat.split()) == 16 or len(_stat.split()) == 20:
                        # Linux 2.6+ for a device
                        _previousReads = int(_stat.split()[5])
                        _previousWrites = int(_stat.split()[9])
                        _previousRsectors = int(_stat.split()[7])
                        _previousWsectors = int(_stat.split()[11])
                        if int(_deltaReadSectors + _deltaWriteSectors) >= 0 and _deltaTime >= 0:
                            # Exclude initial data that will bring inaccuracy
                            _outputLine = _stat.split()[0] + ";" + "'" + _stat.split()[1] + ";" + _item + ";" \
                                + str(_totalTime) + ";" + str(_deltaTime) + ";" \
                                + str(_deltaReads) + ";" + str(_deltaWrites) + ";" + str(_deltaReads + _deltaWrites) + ";" \
                                + str(_rBytes) + ";" + str(_wBytes) + ";" + str(_rBytes + _wBytes) + ";" \
                                + str(_rMBytes) + ";" + str(_wMBytes) + ";" + str(_rMBytes + _wMBytes) + ";" \
                                + _stat.split()[5] + ";" + _stat.split()[9] + ";" \
                                + _stat.split()[6] + ";" + _stat.split()[10] + ";" \
                                + _stat.split()[7] + ";" + _stat.split()[11] + ";" \
                                + _stat.split()[5] + ";" + _stat.split()[9] + ";" \
                                + _stat.split()[8] + ";" + _stat.split()[12] + ";" \
                                + _stat.split()[13] + ";" + _stat.split()[14] + ";" \
                                + _stat.split()[15]
                    if len(_stat.split()) == 7:
                        # Linux 2.6+ for a partition
                        print ("  Looks like partition data (" + _item + ")")

                    if int(_deltaReadSectors + _deltaWriteSectors) >= 0 and _deltaTime >= 0:
                        # Exclude initial data that will bring inaccuracy
                        _outputfile.write(_outputLine + '\n')
                        _outputAllfile.write(_outputLine + ";" + str(_sectorSize) + '\n')
                _iCountStats = _iCountStats + 1
        _outputfile.close()
    _outputAllfile.close()


def compute_io_stats_single_disk(_iostats, _device):
    _deltaTime = 0
    _deltaReads = 0
    _deltaWrites = 0
    _deltaReadSectors = 0
    _deltaWriteSectors = 0
    _rBytes = 0
    _wBytes = 0
    _rMBytes = 0
    _wMBytes = 0
    _previousTime = 0
    _previousReads = 0
    _previousWrites = 0
    _previousRsectors = 0
    _previousWsectors = 0

    _dateTime = datetime.utcnow().strftime('%Y-%m-%d_%H:%M:%S').replace(":","-")

    print (" Compute disk" + _device + " metrics...")

    _sectorSize = get_device_sector_size(_device)
    _outputfile = "./" + os.uname()[1] + "_" + _device + "_" + _dateTime + "_" + str(int(_sectorSize)) + ".log"
    _outputfile = open(_outputfile, "w")

    _outputfile.write("date;time UTC;device;time (ms);delta time (ms);delta reads;delta writes;delta IOPS;delta Bytes read;delta Bytes written;delta Bytes;delta MBytes read;delta MBytes written;total MBytes;reads;writes;reads merged;writes merged;sector read;sector written;read time (ms);write time (ms);i/o in progress;time spent doing i/o (ms);weighted time spent doing i/o (ms)\n")

    _iCountStats = 0
    while _iCountStats < len(_iostats):
        _stat = _iostats[_iCountStats]
        update_progressbar(" Completion", _iCountStats, len(_iostats))

        _totalTime = (int(_stat.split()[1][:2])*3600000) + (int(_stat.split()[1][3:5])*60000) + (int(_stat.split()[1][6:8])*1000) + int(_stat.split()[1][9:13])
        _deltaTime = _totalTime - _previousTime
        _previousTime = _totalTime

        # Get data
        if _iCountStats == 0:
            _deltaTime = 0
            _deltaReads = 0
            _deltaWrites = 0
            _deltaReadSectors = 0
            _deltaWriteSectors = 0
            _rBytes = 0
            _wBytes = 0
            _rMBytes = 0
            _wMBytes = 0
        else:
            if len(_stat.split()) == 15:
                # Linux 2.4
                _deltaReads = int(_stat.split()[5]) - _previousReads
                _deltaWrites = int(_stat.split()[9]) - _previousWrites
                _deltaReadSectors = int(_stat.split()[7]) - _previousRsectors
                _deltaWriteSectors = int(_stat.split()[11]) - _previousWsectors
            elif len(_stat.split()) == 14 or len(_stat.split()) == 17:
                # Linux 2.6+ for a device (using /proc/disktats)
                _deltaReads = int(_stat.split()[5]) - _previousReads
                _deltaWrites = int(_stat.split()[9]) - _previousWrites
                _deltaReadSectors = int(_stat.split()[7]) - _previousRsectors
                _deltaWriteSectors = int(_stat.split()[11]) - _previousWsectors
            elif len(_stat.split()) == 13:
                # Linux 2.6+ for a device or a partition (using /sys/block/*/stat)
                # [2] reads [3] reads merged [4] sectors read [5] ms spent reading [6] writes [7] writes merged [8] sectors written [9] ms spent writing [10] I/O in progress [11] ms doing I/O [12] weighted ms doing I/Os
                _deltaReads = int(_stat.split()[2]) - _previousReads
                _deltaWrites = int(_stat.split()[6]) - _previousWrites
                _deltaReadSectors = int(_stat.split()[4]) - _previousRsectors
                _deltaWriteSectors = int(_stat.split()[8]) - _previousWsectors
            elif len(_stat.split()) == 7:
                # Linux 2.6+ for a partition
                _deltaReads = int(_stat.split()[5]) - _previousReads
                _deltaWrites = int(_stat.split()[9]) - _previousWrites
                _deltaReadSectors = int(_stat.split()[7]) - _previousRsectors
                _deltaWriteSectors = int(_stat.split()[11]) - _previousWsectors

        if int(_deltaReadSectors + _deltaWriteSectors) >= 0 and _deltaTime >= 0:
            _rBytes = _deltaReadSectors * int(_sectorSize)
            _wBytes = _deltaWriteSectors * int(_sectorSize)
            _rMBytes = round(float(_rBytes) / (1024 ** 2), 2)
            _wMBytes = round(float(_wBytes) / (1024 ** 2), 2)

            # Append context data with actual data
            _outputLine = ''
            if len(_stat.split()) == 15:
                # Linux 2.4
                _previousReads = int(_stat.split()[5])
                _previousWrites = int(_stat.split()[9])
                _previousRsectors = int(_stat.split()[7])
                _previousWsectors = int(_stat.split()[11])

                _outputLine = _stat.split()[0] + ";" + "'" + _stat.split()[1] + ";" \
                    + _device + ";" \
                    + str(_totalTime) + ";" + str(_deltaTime) + ";" \
                    + str(_deltaReads) + ";" + str(_deltaWrites) + ";" + str(_deltaReads + _deltaWrites) + ";" \
                    + str(_rBytes) + ";" + str(_wBytes) + ";" + str(_rBytes + _wBytes) + ";" \
                    + str(_rMBytes) + ";" + str(_wMBytes) + ";" + str(_rMBytes + _wMBytes) + ";" \
                    + _stat.split()[2] + ";" + _stat.split()[6] + ";" \
                    + _stat.split()[3] + ";" + _stat.split()[7] + ";" \
                    + _stat.split()[4] + ";" + _stat.split()[8] + ";" \
                    + _stat.split()[5] + ";" + _stat.split()[9] + ";" \
                    + _stat.split()[10] + ";" + _stat.split()[11] + ";" \
                    + _stat.split()[12] + '\n'
            if len(_stat.split()) == 14 or len(_stat.split()) == 17:
                # Linux 2.6+ for a device
                _previousReads = int(_stat.split()[5])
                _previousWrites = int(_stat.split()[9])
                _previousRsectors = int(_stat.split()[7])
                _previousWsectors = int(_stat.split()[11])

                _outputLine = _stat.split()[0] + ";" + "'" + _stat.split()[1] + ";" \
                    + _device + ";" \
                    + str(_totalTime) + ";" + str(_deltaTime) + ";" \
                    + str(_deltaReads) + ";" + str(_deltaWrites) + ";" + str(_deltaReads + _deltaWrites) + ";" \
                    + str(_rBytes) + ";" + str(_wBytes) + ";" + str(_rBytes + _wBytes) + ";" \
                    + str(_rMBytes) + ";" + str(_wMBytes) + ";" + str(_rMBytes + _wMBytes) + ";" \
                    + _stat.split()[2] + ";" + _stat.split()[6] + ";" \
                    + _stat.split()[3] + ";" + _stat.split()[7] + ";" \
                    + _stat.split()[4] + ";" + _stat.split()[8] + ";" \
                    + _stat.split()[5] + ";" + _stat.split()[9] + ";" \
                    + _stat.split()[10] + ";" + _stat.split()[11] + ";" \
                    + _stat.split()[12] + '\n'
            elif len(_stat.split()) == 13:
                # Linux 2.6+ for a device or a partition (using /sys/block/*/stat)
                _previousReads = int(_stat.split()[2])
                _previousWrites = int(_stat.split()[6])
                _previousRsectors = int(_stat.split()[4])
                _previousWsectors = int(_stat.split()[8])
                #"reads;writes;reads merged;writes merged;sector read;sector written;read time (ms);write time (ms);i/o in progress;time spent doing i/o (ms);weighted time spent doing i/o (ms)\n")
                _outputLine = _stat.split()[0] + ";" + "'" + _stat.split()[1] + ";" \
                    + _device + ";" \
                    + str(_totalTime) + ";" + str(_deltaTime) + ";" \
                    + str(_deltaReads) + ";" + str(_deltaWrites) + ";" + str(_deltaReads + _deltaWrites) + ";" \
                    + str(_rBytes) + ";" + str(_wBytes) + ";" + str(_rBytes + _wBytes) + ";" \
                    + str(_rMBytes) + ";" + str(_wMBytes) + ";" + str(_rMBytes + _wMBytes) + ";" \
                    + _stat.split()[2] + ";" + _stat.split()[6] + ";" \
                    + _stat.split()[3] + ";" + _stat.split()[7] + ";" \
                    + _stat.split()[4] + ";" + _stat.split()[8] + ";" \
                    + _stat.split()[5] + ";" + _stat.split()[9] + ";" \
                    + _stat.split()[10] + ";" + _stat.split()[11] + ";" \
                    + _stat.split()[12] + '\n'
            if len(_stat.split()) == 7:
                # Linux 2.6+ for a partition
                _previousReads = int(_stat.split()[5])
                _previousWrites = int(_stat.split()[9])
                _previousRsectors = int(_stat.split()[7])
                _previousWsectors = int(_stat.split()[11])

                _outputLine = _stat.split()[0] + ";" + "'" + _stat.split()[1] + ";" \
                    + _device + ";" \
                    + str(_totalTime) + ";" + str(_deltaTime) + ";" \
                    + str(_deltaReads) + ";" + str(_deltaWrites) + ";" + str(_deltaReads + _deltaWrites) + ";" \
                    + str(_rBytes) + ";" + str(_wBytes) + ";" + str(_rBytes + _wBytes) + ";" \
                    + str(_rMBytes) + ";" + str(_wMBytes) + ";" + str(_rMBytes + _wMBytes) + ";" \
                    + _stat.split()[2] + ";" + _stat.split()[6] + ";" \
                    + _stat.split()[3] + ";" + _stat.split()[7] + ";" \
                    + _stat.split()[4] + ";" + _stat.split()[8] + ";" \
                    + _stat.split()[5] + ";" + _stat.split()[9] + ";" \
                    + _stat.split()[10] + ";" + _stat.split()[11] + ";" \
                    + _stat.split()[12] + '\n'

            _outputfile.write(_outputLine)
        _iCountStats = _iCountStats + 1
    _outputfile.close()

if __name__ == '__main__':

    os.system('clear')

    scriptArguments = parse_script_arguments(sys.argv[1:])

    kernel_version = init()

    print ("")
    print ("GetIOStats.py - Script version: " + SCRIPT_VERSION)
    print ("- Collect high resolution IO stats from disk devices on Linux -")
    print ("Kernel version: " + str(kernel_version))
    if kernel_version < 2.6:
        print ("This Linux kernel version (" + str(kernel_version) + ") is not supported.")
        print ("Exiting...")
        sys.exit()

    print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + " - Capturing I/Os metrics for device(s): " + scriptArguments[0] + ". Estimated duration: " + str(scriptArguments[1]) + " minute(s), interval: " + str(scriptArguments[2]) + " " + scriptArguments[3] + ". No output during capture.")
    print (" Data is kept in memory so if this script is interrupted, no data will be collected.")
    ioStats = get_io_stats(scriptArguments[0], float(scriptArguments[2]), int(scriptArguments[1]))

    # Process collected data and flush to output files
    print ("")
    print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + " - Processing I/O statistics and flushing to file: " + str(len(ioStats)) + " samples.")
    compute_io_stats(ioStats, scriptArguments[0])

    print ("")
    print (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + " - Process Completed. Please send the log file(s) to the Microsoft support engineer.")
    print ("")

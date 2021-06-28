#!/usr/bin/python3

#cat /var/log/deepthought-worker.log |grep SIGKILL >/dev/null; echo $?; if [ echo$? ]; then pkgutil --forget deepthought-worker;  /usr/local/munki/managedsoftwareupdate; /usr/local/munki/managedsoftwareupdate --installonly; /var/root/venv/bin/deepthought-worker-restart;fi

import re
import sys
import os

logfile="/var/log/deepthought-worker.log"
stringToFind="deep"

file = open(logfile, "r")

for line in file:
     if re.search(stringToFind, line):
        output = os.system("pkgutil --forget deepthought-worker")
        print(output)
        output = os.system("/usr/local/munki/managedsoftwareupdate")
        print(output)
        output = os.system("/usr/local/munki/managedsoftwareupdate --installonly")
        print(output)
        output = os.system("/var/root/venv/bin/deepthought-worker-restart")
        print(output)
        exit(0)

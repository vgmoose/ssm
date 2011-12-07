#!/usr/bin/env python
#
# (C)2011 Red Hat, Inc., Lukas Czerner <lczerner@redhat.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# crypt module for System Storage Manager

import re
import os
from ssmlib import misc

__all__ = ["DmCryptVolume"]

try:
    DM_DEV_DIR = os.environ['DM_DEV_DIR']
except KeyError:
    DM_DEV_DIR = "/dev"


class DmCryptVolume(object):

    def __init__(self, data=None, force=False, verbose=False, yes=False):
        self.data = data or {}
        self.output = None
        self.force = force
        self.verbose = verbose
        self.yes = yes
        self.mounts = misc.get_mounts('^{0}/mapper'.format(DM_DEV_DIR))

        if not misc.check_binary('dmsetup') or \
           not misc.check_binary('cryptsetup'):
            return
        command = ['dmsetup', 'table']
        self.output = misc.run(command, stderr=False)[1]
        for line in self.output.split("\n"):
            if not line or line == "No devices found":
                break
            dm = {}
            array = line.split()
            dm['type'] = array[3]
            if dm['type'] != 'crypt':
                continue
            dm['vol_size'] = str(int(array[2]) / 2.0)
            devname = re.sub(":$", "",
                    "{0}/mapper/{1}".format(DM_DEV_DIR, array[0]))
            dm['dm_name'] = devname
            dm['pool_name'] = 'dm-crypt'
            dm['dev_name'] = misc.get_real_device(devname)
            if dm['dm_name'] in self.mounts:
                dm['mount'] = self.mounts[dm['dm_name']]

            # Check if the device really exists in the system. In some cases
            # (tests) DM_DEV_DIR can lie to us, if that is the case, simple
            # ignore the device.
            if not os.path.exists(devname):
                continue
            command = ['cryptsetup', 'status', devname]
            self._parse_cryptsetup(command, dm)
            self.data[dm['dev_name']] = dm

    def _parse_cryptsetup(self, cmd, dm):
        self.output = misc.run(cmd, stderr=False)[1]
        for line in self.output.split("\n"):
            if not line:
                break
            array = line.split()
            if array[0].strip() == 'cipher:':
                dm['cipher'] = array[1]
            elif array[0].strip() == 'keysize:':
                dm['keysize'] = array[1]
            elif array[0].strip() == 'device:':
                dm['crypt_device'] = array[1]

    def remove(self, dm):
        print "Removing crypt {0}".format(dm)
        command = ['cryptsetup', 'remove', dm]
        misc.run(command, stdout=True)

    def resize(self, dm, size, resize_fs=True):
        print "resize dm {0}".format(dm)
        size = str(int(size) * 2)
        command = ['cryptsetup', 'resize', '--size', size, dm]
        misc.run(command, stdout=True)

    def __iter__(self):
        for item in sorted(self.data.iterkeys()):
            yield item

    def __getitem__(self, key):
        if key in self.data.iterkeys():
            return self.data[key]
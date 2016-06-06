# -*- coding: utf-8 -*-
'''
Module to manage filesystem snapshots with snapper
:depends: - ``dbus`` Python module.
:depends: - ``snapper`` http://snapper.io, available in most distros
'''

import salt.utils
from salt.exceptions import CommandExecutionError
import logging
import os
import time
import difflib
from pwd import getpwuid

try:
    import dbus
    HAS_DBUS = True
except ImportError:
    HAS_DBUS = False


def __virtual__():
    if not HAS_DBUS:
        return (False, 'The snapper module cannot be loaded:'
                ' missing python dbus module')
    if not salt.utils.which('snapper'):
        return (False, 'The snapper module cannot be loaded:'
                ' missing snapper')
    return 'snapper'


bus = dbus.SystemBus()
log = logging.getLogger(__name__)
snapper = dbus.Interface(bus.get_object('org.opensuse.Snapper',
                                        '/org/opensuse/Snapper'),
                         dbus_interface='org.opensuse.Snapper')


def _snapshot_to_data(snapshot):
    data = {}

    data['id'] = snapshot[0]
    data['type'] = ['single', 'pre', 'post'][snapshot[1]]
    data['pre'] = snapshot[2]

    if snapshot[3] != -1:
        data['timestamp'] = snapshot[3]
    else:
        data['timestamp'] = time.time()

    data['user'] = getpwuid(snapshot[4])[0]
    data['description'] = snapshot[5]
    data['cleanup'] = snapshot[6]

    data['userdata'] = {}
    for k, v in snapshot[7].items():
        data['userdata'][k] = v

    return data


def _dbus_exception_to_reason(exc):
    '''
    Returns a error message from a snapper DBusException
    '''
    error = exc.get_dbus_name()
    if error == 'error.unknown_config':
        return 'Unknown configuration'
    elif error == 'error.illegal_snapshot':
        return 'Invalid snapshot'
    else:
        return exc.get_dbus_name()


def list_snapshots(config='root'):
    try:
        snapshots = snapper.ListSnapshots(config)
        return [_snapshot_to_data(s) for s in snapshots]
    except dbus.DBusException as exc:
        raise CommandExecutionError(
            'Error encountered while listing snapshots: {0}'
            .format(_dbus_exception_to_reason(exc))
        )


def get_snapshot(number=0, config='root'):
    try:
        snapshot = snapper.GetSnapshot(config, int(number))
        return _snapshot_to_data(snapshot)
    except dbus.DBusException as exc:
        raise CommandExecutionError(
            'Error encountered while retrieving snapshot: {0}'
            .format(_dbus_exception_to_reason(exc))
        )


def list_configs():
    try:
        configs = snapper.ListConfigs()
        return dict((config[0], config[2]) for config in configs)
    except dbus.DBusException as exc:
        raise CommandExecutionError(
            'Error encountered while listing configurations: {0}'
            .format(_dbus_exception_to_reason(exc))
        )


def _config_filter(x):
    if isinstance(x, bool):
        return 'yes' if x else 'no'
    return x


def set_config(name='root', **kwargs):
    try:
        data = dict((k.upper(), _config_filter(v)) for k, v in
                    kwargs.iteritems() if not k.startswith('__'))
        snapper.SetConfig(name, data)
    except dbus.DBusException as exc:
        raise CommandExecutionError(
            'Error encountered while setting configuration {0}: {1}'
            .format(name, _dbus_exception_to_reason(exc))
        )


def _get_last_snapshot(config='root'):
    snapshot_list = sorted(list_snapshots(config), key=lambda x: x['id'])
    return snapshot_list[-1]


def get_config(name='root'):
    try:
        config = snapper.GetConfig(name)
        return config
    except dbus.DBusException as exc:
        raise CommandExecutionError(
            'Error encountered while retrieving configuration: {0}'
            .format(_dbus_exception_to_reason(exc))
        )


def changed_files(config='root', num_pre=None, num_post=None):
    try:
        num_post = num_post if num_post else _get_last_snapshot(config)['id']
        num_pre = num_pre if num_pre else int(num_post)-1

        snapper.CreateComparison(config, int(num_pre), int(num_post))
        files = snapper.GetFiles(config, int(num_pre), int(num_post))
        return [file[0] for file in files]
    except dbus.DBusException as exc:
        raise CommandExecutionError(
            'Error encountered while listing changed files: {0}'
            .format(_dbus_exception_to_reason(exc))
        )


def _is_text_file(filename):
    type_of_file = os.popen('file -bi {0}'.format(filename), 'r').read()
    return type_of_file.startswith('text')


def diff(config='root', filename=None, num_pre=None, num_post=None):
    '''
    Returns the differences between two snapshots

    filename
        if not provided the showing differences between snapshots for
        all "text" files

    num_pre
        first snapshot ID to compare. Default is last snapshot ID-1

    num_post
        last snapshot ID to compare. Default is last snapshot ID

    CLI example:

    .. code-block:: bash

        salt '*' snapper.diff
        salt '*' snapper.diff filename=/var/log/snapper.log num_pre=19 num_post=20
    '''
    try:
        num_post = num_post if num_post else _get_last_snapshot(config)['id']
        num_pre = num_pre if num_pre else int(num_post)-1

        files = changed_files(config, num_pre, num_post) if not filename else [filename]
        pre_mount = snapper.MountSnapshot(config, num_pre, False)
        post_mount = snapper.MountSnapshot(config, num_post, False)

        files_diff = dict()
        for f in files:
            pre_file = pre_mount + f
            post_file = post_mount + f

            #FIXME: What happends it pre_file or post_file did not exist??? ARGHHH
            if os.path.isfile(pre_file) and _is_text_file(pre_file):
                files_diff[f] = ''.join(difflib.unified_diff(open(pre_file).readlines(),
                                                             open(post_file).readlines(),
                                                             fromfile=pre_file,
                                                             tofile=post_file))

        snapper.UmountSnapshot(config, num_pre, False)
        snapper.UmountSnapshot(config, num_post, False)
        return files_diff
    except dbus.DBusException as exc:
        raise CommandExecutionError(
            'Error encountered while showing differences between snapshots: {0}'
            .format(_dbus_exception_to_reason(exc))
        )

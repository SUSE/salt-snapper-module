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
    '''
    List available snapshots

    CLI example:

    .. code-block:: bash

        salt '*' snapper.list_snapshots config=myconfig
    '''
    try:
        snapshots = snapper.ListSnapshots(config)
        return [_snapshot_to_data(s) for s in snapshots]
    except dbus.DBusException as exc:
        raise CommandExecutionError(
            'Error encountered while listing snapshots: {0}'
            .format(_dbus_exception_to_reason(exc))
        )


def get_snapshot(number=0, config='root'):
    '''
    Get detailed information about a given snapshot

    CLI example:

    .. code-block:: bash

        salt '*' snapper.get_snapshot 1
    '''
    try:
        snapshot = snapper.GetSnapshot(config, int(number))
        return _snapshot_to_data(snapshot)
    except dbus.DBusException as exc:
        raise CommandExecutionError(
            'Error encountered while retrieving snapshot: {0}'
            .format(_dbus_exception_to_reason(exc))
        )


def list_configs():
    '''
    List all available configs

    CLI example:

    .. code-block:: bash

        salt '*' snapper.list_configs
    '''
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
    '''
    Set configuration values

    CLI example:

    .. code-block:: bash

        salt '*' snapper.set_config SYNC_ACL=True

    Keys are case insensitive as they will be always uppercased to
    snapper convention. The above example is equivalent to:

    .. code-block:: bash
        salt '*' snapper.set_config sync_acl=True
    '''
    try:
        data = dict((k.upper(), _config_filter(v)) for k, v in
                    kwargs.iteritems() if not k.startswith('__'))
        snapper.SetConfig(name, data)
    except dbus.DBusException as exc:
        raise CommandExecutionError(
            'Error encountered while setting configuration {0}: {1}'
            .format(name, _dbus_exception_to_reason(exc))
        )
    return True


def _get_last_snapshot(config='root'):
    snapshot_list = sorted(list_snapshots(config), key=lambda x: x['id'])
    return snapshot_list[-1]


def get_config(name='root'):
    '''
    Retrieves all values from a given configuration

    CLI example:

    .. code-block:: bash

      salt '*' snapper.get_config
    '''
    try:
        config = snapper.GetConfig(name)
        return config
    except dbus.DBusException as exc:
        raise CommandExecutionError(
            'Error encountered while retrieving configuration: {0}'
            .format(_dbus_exception_to_reason(exc))
        )


def create_snapshot(config='root', type='single', pre_number=None,
                    description='', cleanup_algorithm='number', userdata={}):
    '''
    Creates an snapshot

    config
        Configuration name.
    type
        Specifies the type of the new snapshot. Possible values are
        single, pre and post.
    pre_number
        For post snapshots the number of the pre snapshot must be
        provided.
    description
        Description for the snapshot. If not given, the salt job will be used.
    cleanup_algorithm
        Set the cleanup algorithm for the snapshot.

        number
            Deletes old snapshots when a certain number of snapshots
            is reached.
        timeline
            Deletes old snapshots but keeps a number of hourly,
            daily, weekly, monthly and yearly snapshots.
        empty-pre-post
            Deletes pre/post snapshot pairs with empty diffs.
    userdata
        Set userdata for the snapshot (key-value pairs).

    Returns the number of the created snapshot.

    .. code-block:: bash
        salt '*' snapper.create_snapshot
    '''
    nr = None
    try:
        if type == 'single':
            nr = snapper.CreateSingleSnapshot(config, description,
                                              cleanup_algorithm, userdata)
        elif type == 'pre':
            nr = snapper.CreatePreSnapshot(config, description,
                                           cleanup_algorithm, userdata)
        elif type == 'post':
            if pre_number is None:
                raise CommandExecutionError(
                    "pre snapshot number 'pre_number' needs to be"
                    "specified for snapshots of the 'post' type")
            nr = snapper.CreatePostSnapshot(config, pre_number, description,
                                            cleanup_algorithm, userdata)
        else:
            raise CommandExecutionError(
                "Invalid snapshot type '{0}'", format(type))
    except dbus.DBusException as exc:
        raise CommandExecutionError(
            'Error encountered while listing changed files: {0}'
            .format(_dbus_exception_to_reason(exc))
        )
    return nr


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
        for f in filter(lambda x: os.path.isfile(x), files):
            pre_file = pre_mount + f
            post_file = post_mount + f

            pre_file_content = open(pre_file).readlines() if os.path.isfile(pre_file) else []
            post_file_content = open(post_file).readlines() if os.path.isfile(post_file) else []

            if _is_text_file(post_file) or not post_file_content:
                files_diff[f] = ''.join(difflib.unified_diff(pre_file_content,
                                                             post_file_content,
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

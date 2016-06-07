import salt.loader
import logging
import os

log = logging.getLogger(__name__)


def __virtual__():
    return True


def snapshot(name, number=None, config='root', ignore=[], commit=False):
    '''
    Enforces that no file is modified comparing against a previously
    defined snapshot identified by number.

    ignore
        List of files to ignore
    '''

    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    if number is None:
        ret.update({'result': False,
                    'comment': 'Snapshot number needs to be specified'})
        return ret

    status = __salt__['snapper.status'](
        config, num_pre=number, num_post=0)

    for f in ignore:
        if os.path.isfile(f):
            status.pop(f, None)
        elif os.path.isdir(f):
            [status.pop(x, None) for x in status.keys() if x.startswith(f)]

    if commit:
        status = __salt__['snapper.undo'](config, num_pre=number, num_post=0)

    ret['changes']['files'] = status
    return ret
         

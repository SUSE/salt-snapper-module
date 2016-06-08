import salt.loader
import logging
import os

log = logging.getLogger(__name__)


def __virtual__():
    return True


def baseline_snapshot(name, number=None, config='root', ignore=[]):
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


    # Only include changes for modified files
    for f in status:
        status[f]['action'] = status[f].pop("status")
        if "modified" in status[f]['action']:
            status[f]['diff'] = __salt__['snapper.diff'](config,
                                                         num_pre=0,
                                                         num_post=number, filename=f)

    if status:
        ret['changes']['files'] = status
    else:
        ret['comment'] = "No changes were done"

    if not __opts__['test'] and status.keys():
        undo = __salt__['snapper.undo'](config, num_pre=number, num_post=0,
                                        files=status.keys())
        ret['changes']['sumary'] = undo

    if __opts__['test'] and status:
        ret['pchanges'] = ret["changes"]
        ret['changes'] = {}
        ret['comment'] = "{0} files changes are set to be undone".format(len(status.keys()))
    elif __opts__['test'] and not status:
        ret['result'] = None if not status else True
        ret['changes'] = {}
        ret['comment'] = "Nothing to be done"

    return ret

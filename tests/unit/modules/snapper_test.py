import sys
import os

from salttesting import TestCase
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salt.exceptions import CommandExecutionError
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

from salt.modules import snapper

# Globals
snapper.__salt__ = dict()

DBUS_RET = {
    'ListSnapshots': [
        [42, 1, 0, 1457006571,
         0, 'Some description', '', {'userdata1': 'userval1'}],
        [43, 2, 42, 1457006572,
         0, 'Blah Blah', '', {'userdata2': 'userval2'}]
    ],
    'ListConfigs': [
        [u'root', u'/', {
            u'SUBVOLUME': u'/', u'NUMBER_MIN_AGE': u'1800',
            u'TIMELINE_LIMIT_YEARLY': u'4-10', u'NUMBER_LIMIT_IMPORTANT': u'10',
            u'FSTYPE': u'btrfs', u'TIMELINE_LIMIT_MONTHLY': u'4-10',
            u'ALLOW_GROUPS': u'', u'EMPTY_PRE_POST_MIN_AGE': u'1800',
            u'EMPTY_PRE_POST_CLEANUP': u'yes', u'BACKGROUND_COMPARISON': u'yes',
            u'TIMELINE_LIMIT_HOURLY': u'4-10', u'ALLOW_USERS': u'',
            u'TIMELINE_LIMIT_WEEKLY': u'0', u'TIMELINE_CREATE': u'no',
            u'NUMBER_CLEANUP': u'yes', u'TIMELINE_CLEANUP': u'yes',
            u'SPACE_LIMIT': u'0.5', u'NUMBER_LIMIT': u'10',
            u'TIMELINE_MIN_AGE': u'1800', u'TIMELINE_LIMIT_DAILY': u'4-10',
            u'SYNC_ACL': u'no', u'QGROUP': u'1/0'}
        ]
    ]
}

MODULE_RET = {
    'SNAPSHOTS': [
        {
            'userdata': {'userdata1': 'userval1'},
            'description': 'Some description', 'timestamp': 1457006571,
            'cleanup': '', 'user': 'root', 'type': 'pre', 'id': 42
        },
        {
            'pre': 42,
            'userdata': {'userdata2': 'userval2'},
            'description': 'Blah Blah', 'timestamp': 1457006572,
            'cleanup': '', 'user': 'root', 'type': 'post', 'id': 43
        }
    ],
    'LISTCONFIGS': {
        u'root': {
            u'SUBVOLUME': u'/', u'NUMBER_MIN_AGE': u'1800',
            u'TIMELINE_LIMIT_YEARLY': u'4-10', u'NUMBER_LIMIT_IMPORTANT': u'10',
            u'FSTYPE': u'btrfs', u'TIMELINE_LIMIT_MONTHLY': u'4-10',
            u'ALLOW_GROUPS': u'', u'EMPTY_PRE_POST_MIN_AGE': u'1800',
            u'EMPTY_PRE_POST_CLEANUP': u'yes', u'BACKGROUND_COMPARISON': u'yes',
            u'TIMELINE_LIMIT_HOURLY': u'4-10', u'ALLOW_USERS': u'',
            u'TIMELINE_LIMIT_WEEKLY': u'0', u'TIMELINE_CREATE': u'no',
            u'NUMBER_CLEANUP': u'yes', u'TIMELINE_CLEANUP': u'yes',
            u'SPACE_LIMIT': u'0.5', u'NUMBER_LIMIT': u'10',
            u'TIMELINE_MIN_AGE': u'1800', u'TIMELINE_LIMIT_DAILY': u'4-10',
            u'SYNC_ACL': u'no', u'QGROUP': u'1/0'
        }
    },
}

class SnapperTestCase(TestCase):
    def setUp(self):
        self.dbus_mock = MagicMock()
        self.DBusExceptionMock = MagicMock()
        self.dbus_mock.configure_mock(DBusException=self.DBusExceptionMock)
        snapper.dbus = self.dbus_mock
        snapper.snapper = MagicMock()

    def test__snapshot_to_data(self):
        data = snapper._snapshot_to_data(DBUS_RET['ListSnapshots'][0])
        self.assertEqual(data['id'], 42)
        self.assertNotIn('pre', data)
        self.assertEqual(data['type'], 'pre')
        self.assertEqual(data['user'], 'root')
        self.assertEqual(data['timestamp'], 1457006571)
        self.assertEqual(data['description'], 'Some description')
        self.assertEqual(data['cleanup'], '')
        self.assertEqual(data['userdata']['userdata1'], 'userval1')

    @patch('salt.modules.snapper.snapper.ListSnapshots', MagicMock(return_value=DBUS_RET['ListSnapshots']))
    def test_list_snapshots(self):
        self.assertEqual(snapper.list_snapshots(), MODULE_RET["SNAPSHOTS"])

    @patch('salt.modules.snapper.snapper.GetSnapshot', MagicMock(return_value=DBUS_RET['ListSnapshots'][0]))
    def test_get_snapshot(self):
        self.assertEqual(snapper.get_snapshot(), MODULE_RET["SNAPSHOTS"][0])
        self.assertEqual(snapper.get_snapshot(number=42), MODULE_RET["SNAPSHOTS"][0])
        self.assertNotEqual(snapper.get_snapshot(number=42), MODULE_RET["SNAPSHOTS"][1])

    @patch('salt.modules.snapper.snapper.ListConfigs', MagicMock(return_value=DBUS_RET['ListConfigs']))
    def test_list_configs(self):
        self.assertEqual(snapper.list_configs(), MODULE_RET["LISTCONFIGS"])

    @patch('salt.modules.snapper.snapper.GetConfig', MagicMock(return_value=DBUS_RET['ListConfigs'][0]))
    def test_get_config(self):
        self.assertEqual(snapper.get_config(), DBUS_RET["ListConfigs"][0])

    @patch('salt.modules.snapper.snapper.SetConfig', MagicMock())
    def test_set_config(self):
        opts = {'sync_acl': True, 'dummy': False, 'foobar': 1234}
        self.assertEqual(snapper.set_config(opts), True)

    def test_status_to_string(self):
        self.assertEqual(snapper.status_to_string(1), ["created"])
        self.assertEqual(snapper.status_to_string(2), ["deleted"])
        self.assertEqual(snapper.status_to_string(4), ["modified"])
        self.assertEqual(snapper.status_to_string(8), ["type changed"])
        self.assertEqual(snapper.status_to_string(16), ["permission changed"])
        self.assertListEqual(snapper.status_to_string(24), ["type changed", "permission changed"])
        self.assertEqual(snapper.status_to_string(32), ["owner changed"])
        self.assertEqual(snapper.status_to_string(64), ["group changed"])
        self.assertListEqual(snapper.status_to_string(97), ["created", "owner changed", "group changed"])
        self.assertEqual(snapper.status_to_string(128), ["extended attributes changed"])
        self.assertEqual(snapper.status_to_string(256), ["ACL info changed"])

    @patch('salt.modules.snapper.snapper.CreateSingleSnapshot', MagicMock(return_value=1234))
    @patch('salt.modules.snapper.snapper.CreatePreSnapshot', MagicMock(return_value=1234))
    @patch('salt.modules.snapper.snapper.CreatePostSnapshot', MagicMock(return_value=1234))
    def test_create_snapshot(self):
        for snapshot_type in ['pre', 'post', 'single']:
            opts = {
                '__pub_jid': 20160607130930720112,
                'type': snapshot_type,
                'description': 'Test description',
                'cleanup_algorithm': 'number',
                'pre_number': 23,
            }
            self.assertEqual(snapper.create_snapshot(**opts), 1234)

    @patch('salt.modules.snapper._get_last_snapshot', MagicMock(return_value={'id':42}))
    def test__get_num_interval(self):
        self.assertEqual(snapper._get_num_interval(config=None, num_pre=None, num_post=None), (42, 0))
        self.assertEqual(snapper._get_num_interval(config=None, num_pre=None, num_post=50), (42, 50))
        self.assertEqual(snapper._get_num_interval(config=None, num_pre=42, num_post=50), (42, 50))

    def test_run(self):
        patch_dict = {
            'snapper.create_snapshot': MagicMock(return_value=43),
            'test.ping': MagicMock(return_value=True),
        }
        with patch.dict(snapper.__salt__, patch_dict):
            self.assertEqual(snapper.run("test.ping"), True)
            self.assertRaises(CommandExecutionError, snapper.run, "unknown.func")


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SnapperTestCase, needs_daemon=False)

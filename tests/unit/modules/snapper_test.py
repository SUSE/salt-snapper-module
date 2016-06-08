import sys
import os
import unittest

from salttesting import TestCase
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

sys.path.append(
    os.path.join(
        os.path.dirname(
            os.path.abspath(__file__)),
        '..', '..', '..', 'srv', 'salt', '_modules'))
import snapper


DBUS_RET = {
    'ListSnapshots': [
        [42, 1, 0, 1457006571,
         0, 'Some description', '', {'userdata1': 'userval1'}],
        [43, 2, 42, 1457006572,
         0, 'Blah Blah', '', {'userdata2': 'userval2'}]],
}

MODULE_RET = [
    {'userdata': {'userdata1': 'userval1'},
     'description':
     'Some description', 'timestamp': 1457006571,
     'cleanup': '', 'user': 'root', 'type': 'pre', 'id': 42},
    {'pre': 42, 'userdata': {'userdata2': 'userval2'},
     'description':
     'Blah Blah', 'timestamp': 1457006572,
     'cleanup': '', 'user': 'root', 'type': 'post', 'id': 43}
]


class SnapperTestCase(TestCase):

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

    def test_list_snapshots(self):
        snapper.snapper.ListSnapshots = MagicMock(
            return_value=DBUS_RET['ListSnapshots'])
        self.assertEqual(
            snapper.list_snapshots(),
            MODULE_RET
        )

    def test_get_snapshot(self):
        snapper.snapper.GetSnapshot = MagicMock(
            return_value=DBUS_RET['ListSnapshots'][0])

        self.assertEqual(
            snapper.get_snapshot(),
            MODULE_RET[0])


if __name__ == '__main__':
    unittest.main()

# -*- coding: utf-8 -*-

import io
import os
import shutil
import tempfile

from s3backup.clients import local, SyncObject
import utils


class TestTraverse(object):
    def setup_method(self):
        self.target_folder = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.target_folder)

    def test_non_existent_folder(self):
        assert list(local.traverse('/i/definetely/do/not/exist')) == []

    def test_empty_folder(self):
        assert list(local.traverse(self.target_folder)) == []

    def test_correct_output(self):
        for item in ['baz/zoo', 'foo', 'bar.md', 'baz/bar', '.index', 'garbage~', 'saw/.index']:
            utils.write_local(os.path.join(self.target_folder, item))

        actual_output = list(local.traverse(
            self.target_folder,
            ignore_files={'.index', '.idontexist', '*~'}
        ))

        expected_output = ['bar.md', 'baz/bar', 'baz/zoo', 'foo']
        assert sorted(actual_output) == sorted(expected_output)


class TestLocalSyncClient(object):
    def test_put_new(self, local_client):
        data = b'hi'
        local_client.put(
            key='hello_world.txt',
            sync_object=SyncObject(io.BytesIO(data), len(data), 20000)
        )

        assert local_client.index['hello_world.txt']['remote_timestamp'] == 20000
        assert utils.get_local_contents(local_client, 'hello_world.txt') == data

    def test_put_existing(self, local_client):
        utils.set_local_index(local_client, {
            'doge.txt': {'local_timestamp': 1111111}
        })

        data = b'canis lupus familiaris'
        local_client.put(
            key='doge.txt',
            sync_object=SyncObject(io.BytesIO(data), len(data), 20000)
        )

        assert local_client.index['doge.txt']['remote_timestamp'] == 20000
        assert local_client.index['doge.txt']['local_timestamp'] == 1111111

        assert utils.get_local_contents(local_client, 'doge.txt') == data

    def test_get_existing(self, local_client):
        data = b'blue green yellow'
        utils.set_local_contents(local_client, 'whatup.md', data=data.decode('utf8'))
        sync_object = local_client.get('whatup.md')
        assert sync_object.fp.read() == data
        assert sync_object.total_size == len(data)

    def test_get_non_existant(self, local_client):
        assert local_client.get('idontexist.md') is None

    def test_delete_existing(self, local_client):
        target_file = os.path.join(local_client.path, 'foo')
        utils.set_local_contents(local_client, 'foo', 222222)

        assert os.path.exists(target_file) is True
        assert local_client.delete('foo') is True
        assert os.path.exists(target_file) is False

    def test_delete_non_existant(self, local_client):
        assert local_client.delete('idontexist.txt') is False

    def test_index_path(self):
        client = local.LocalSyncClient('/hello/from/the/magic/tavern')
        assert client.index_path() == '/hello/from/the/magic/tavern/.index'

    def test_load_index(self, local_client):
        data = {
            'foo': {
                'local_timestamp': 4000,
                'remote_timestamp': 4000,
            },
            'bar/baz.txt': {
                'local_timestamp': 5000,
                'remote_timestamp': 5000,
            },
        }
        utils.set_local_index(local_client, data)

        assert local_client.index == data

    def test_get_local_keys(self, local_client):
        utils.set_local_index(local_client, {})  # .index file should not come up in results
        utils.set_local_contents(local_client, '.bashrc')
        utils.set_local_contents(local_client, 'foo')
        utils.set_local_contents(local_client, 'bar')

        actual_output = local_client.get_local_keys()
        expected_output = ['foo', 'bar', '.bashrc']
        assert sorted(expected_output) == sorted(actual_output)

    def test_get_index_keys(self, local_client):
        data = {
            'foo': {
                'local_timestamp': 4000,
                'remote_timestamp': 4000,
            },
            'bar/baz.txt': {
                'local_timestamp': 5000,
                'remote_timestamp': 5000,
            },
        }
        utils.set_local_index(local_client, data)

        actual_output = local_client.get_index_keys()
        expected_output = ['foo', 'bar/baz.txt']
        assert sorted(list(actual_output)) == sorted(expected_output)

    def test_all_keys(self, local_client):
        utils.set_local_contents(local_client, '.index')
        utils.set_local_contents(local_client, 'foo')
        utils.set_local_contents(local_client, 'bar/boo.md')
        data = {
            'foo': {
                'local_timestamp': 4000,
                'remote_timestamp': 4000,
            },
            'bar/baz.txt': {
                'local_timestamp': 5000,
                'remote_timestamp': 5000,
            },
        }
        utils.set_local_index(local_client, data)

        actual_output = local_client.get_all_keys()
        expected_output = ['foo', 'bar/boo.md', 'bar/baz.txt']
        assert sorted(actual_output) == sorted(expected_output)

    def test_update_index_empty(self, local_client):
        utils.set_local_contents(local_client, 'foo', 13371337)
        utils.set_local_contents(local_client, 'bar', 50032003)

        local_client.update_index()
        # remote timestamp should not be included since it does not exist
        expected_output = {
            'foo': {
                'local_timestamp': 13371337,
                'remote_timestamp': None,
            },
            'bar': {
                'local_timestamp': 50032003,
                'remote_timestamp': None,
            },
        }
        assert local_client.index == expected_output

    def test_update_index_non_empty(self, local_client):
        utils.set_local_contents(local_client, 'foo', 13371337)
        utils.set_local_contents(local_client, 'bar', 50032003)

        utils.set_local_index(local_client, {
            'foo': {
                'local_timestamp': 4000,
                'remote_timestamp': 4000,
            },
            'bar': {
                'local_timestamp': 5000,
                'remote_timestamp': 5000,
            },
            'baz': {
                'local_timestamp': 5000,
                'remote_timestamp': 5000,
            }
        })

        local_client.update_index()
        expected_output = {
            'foo': {
                'local_timestamp': 13371337,
                'remote_timestamp': 4000,
            },
            'bar': {
                'local_timestamp': 50032003,
                'remote_timestamp': 5000,
            },
            'baz': {
                'local_timestamp': None,
                'remote_timestamp': 5000,
            },
        }
        assert local_client.index == expected_output

    def test_get_real_local_timestamp(self, local_client):
        utils.set_local_contents(local_client, 'atcg', 2323230)

        assert local_client.get_real_local_timestamp('atcg') == 2323230
        assert local_client.get_real_local_timestamp('dontexist') is None

    def test_get_all_real_local_timestamps(self, local_client):
        utils.set_local_contents(local_client, 'red', 2323230)
        utils.set_local_contents(local_client, 'blue', 80808008)

        expected_output = {
            'red': 2323230,
            'blue': 80808008,
        }
        actual_output = local_client.get_all_real_local_timestamps()
        assert actual_output == expected_output

    def test_get_index_timestamps(self, local_client):
        utils.set_local_index(local_client, {
            'foo': {
                'local_timestamp': 4000,
                'remote_timestamp': 32000,
            },
            'bar': {
                'local_timestamp': 9999999,
            }
        })
        assert local_client.get_index_local_timestamp('foo') == 4000
        assert local_client.get_index_local_timestamp('dontexist') is None
        assert local_client.get_index_local_timestamp('bar') == 9999999

        assert local_client.get_remote_timestamp('foo') == 32000
        assert local_client.get_remote_timestamp('dontexist') is None
        assert local_client.get_remote_timestamp('bar') is None

    def test_get_all_index_local_timestamps(self, local_client):
        utils.set_local_index(local_client, {
            'frap': {
                'local_timestamp': 4000,
            },
            'brap': {
                'local_timestamp': 9999999,
            }
        })

        expected_output = {
            'frap': 4000,
            'brap': 9999999,
        }
        actual_output = local_client.get_all_index_local_timestamps()
        assert actual_output == expected_output

    def test_get_all_remote_timestamps(self, local_client):
        utils.set_local_index(local_client, {
            'frap': {
                'remote_timestamp': 4000,
            },
            'brap': {
                'remote_timestamp': 9999999,
            }
        })

        expected_output = {
            'frap': 4000,
            'brap': 9999999,
        }
        actual_output = local_client.get_all_remote_timestamps()
        assert actual_output == expected_output

    def test_ignore_files(self, local_client):
        utils.set_local_contents(local_client, '.syncignore', timestamp=3200, data=(
            '*.zip\n'
            'foo*\n'
        ))
        local_client.reload_ignore_files()

        utils.set_local_index(local_client, {
            'pony.tar': {
                'local_timestamp': 4000,
                'remote_timestamp': 3000,
            }
        })

        utils.set_local_contents(local_client, 'test.zip')
        utils.set_local_contents(local_client, 'foobar')
        utils.set_local_contents(local_client, 'foo')
        utils.set_local_contents(local_client, 'pony.tar', timestamp=8000)

        local_client.update_index()

        expected_index = {
            '.syncignore': {
                'local_timestamp': 3200,
                'remote_timestamp': None,
            },
            'pony.tar': {
                'local_timestamp': 8000,
                'remote_timestamp': 3000,
            }
        }
        assert local_client.index == expected_index

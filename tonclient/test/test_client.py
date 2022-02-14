import unittest

from tonclient.client import TonClient, DEVNET_BASE_URLS
from tonclient.types import ClientConfig


LIB_VERSION = '1.30.0'


class TestTonClientAsyncCore(unittest.TestCase):
    def setUp(self) -> None:
        config = ClientConfig()
        config.network.endpoints = DEVNET_BASE_URLS
        self.client = TonClient(config=config)

    def test_version(self):
        result = self.client.version()
        self.assertEqual(LIB_VERSION, result.version)

    def test_get_api_reference(self):
        reference = self.client.get_api_reference()
        self.assertGreater(len(reference.api['modules']), 0)
        self.assertEqual(LIB_VERSION, reference.api['version'])

    def test_build_info(self):
        info = self.client.build_info()
        self.assertNotEqual(None, info.build_number)

    def test_destroy_context(self):
        self.client.destroy_context()


class TestTonClientSyncCore(unittest.TestCase):
    """Sync core is not recommended to use"""

    def setUp(self) -> None:
        config = ClientConfig()
        config.network.endpoints = DEVNET_BASE_URLS
        self.client = TonClient(config=config, is_core_async=False)

    def test_version(self):
        self.assertEqual(LIB_VERSION, self.client.version().version)

    def test_get_api_reference(self):
        reference = self.client.get_api_reference()
        self.assertGreater(len(reference.api['modules']), 0)

    def test_build_info(self):
        info = self.client.build_info()
        self.assertNotEqual(None, info.build_number)

    def test_destroy_context(self):
        self.client.destroy_context()

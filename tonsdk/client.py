import asyncio
from typing import Dict

from tonsdk.bindings.lib import tc_create_context, tc_destroy_context
from tonsdk.crypto import TonCrypto
from tonsdk.module import TonModule
from tonsdk.queries import TonQuery
from tonsdk.contracts import TonContract

DEVNET_BASE_URL = 'net.ton.dev'
MAINNET_BASE_URL = 'main.ton.dev'

TON_CLIENT_DEFAULT_SETUP = {
    'servers': ['http://localhost'],
    'messageRetriesCount': 1,
    'messageExpirationTimeout': 50000,
    'messageExpirationTimeoutGrowFactor': 1.5,
    'messageProcessingTimeout': 50000,
    'messageProcessingTimeoutGrowFactor': 1.5,
    'waitForTimeout': 30000,
    'accessKey': ''
}


class TonClientBase(TonModule):
    def setup(self, settings: Dict):
        self.request(method="setup", **settings)

    def version(self) -> str:
        return self.request(method="version")


class TonClient(object):
    """ Main client class to create object of """
    def __init__(self, **config):
        super(TonClient, self).__init__()

        self._ctx = tc_create_context()

        self.base = TonClientBase(ctx=self._ctx)
        self.crypto = TonCrypto(ctx=self._ctx)
        self.queries = TonQuery(ctx=self._ctx)
        self.contracts = TonContract(ctx=self._ctx)

        self.base.setup({**TON_CLIENT_DEFAULT_SETUP, **config})

    @property
    def setup(self):
        return self.base.setup

    @property
    def version(self):
        return self.base.version

    def destroy_context(self):
        tc_destroy_context(ctx=self._ctx)


async def main():
    t = TonClient(servers=[DEVNET_BASE_URL])
    print(await t.base.request_async('crypto.mnemonic.from.random', wordCount=12))


if __name__ == "__main__":
    asyncio.run(main())

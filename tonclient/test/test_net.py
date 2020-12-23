import base64
import os
import time
from datetime import datetime

import unittest

from tonclient.client import TonClient
from tonclient.errors import TonException
from tonclient.test.helpers import async_core_client, sync_core_client, \
    SAMPLES_DIR, send_grams, async_custom_client, CUSTOM_BASE_URL, \
    GIVER_ADDRESS
from tonclient.types import ParamsOfQueryCollection, OrderBy, SortDirection, \
    ParamsOfWaitForCollection, ParamsOfQuery, ParamsOfSubscribeCollection, \
    SubscriptionResponseType, ResultOfSubscription, ClientError, Abi, \
    ParamsOfEncodeMessage, Signer, DeploySet, CallSet, ParamsOfProcessMessage, \
    ClientConfig, ParamsOfFindLastShardBlock


class TestTonNetAsyncCore(unittest.TestCase):
    def test_query_collection(self):
        q_params = ParamsOfQueryCollection(
            collection='blocks_signatures', result='id', limit=1)
        result = async_core_client.net.query_collection(params=q_params)
        self.assertGreater(len(result.result), 0)

        q_params = ParamsOfQueryCollection(
            collection='accounts', result='id balance', limit=5)
        result = async_core_client.net.query_collection(params=q_params)
        self.assertEqual(5, len(result.result))

        q_params = ParamsOfQueryCollection(
            collection='messages', result='body created_at', limit=10,
            filter={'created_at': {'gt': 1562342740}},
            order=[OrderBy(path='created_at', direction=SortDirection.ASC)])
        result = async_core_client.net.query_collection(params=q_params)
        self.assertGreater(result.result[0]['created_at'], 1562342740)

        with self.assertRaises(TonException):
            q_params = ParamsOfQueryCollection(
                collection='messages', result='id balance')
            async_core_client.net.query_collection(params=q_params)

    def test_wait_for_collection(self):
        now = int(datetime.now().timestamp())
        q_params = ParamsOfWaitForCollection(
            collection='transactions', result='id now',
            filter={'now': {'gt': now}})
        result = async_core_client.net.wait_for_collection(params=q_params)
        self.assertGreater(result.result['now'], now)

        with self.assertRaises(TonException):
            q_params = ParamsOfWaitForCollection(
                collection='transactions', result='', timeout=1)
            async_core_client.net.wait_for_collection(params=q_params)

    def test_subscribe_collection(self):
        results = []

        def __callback(response_data, response_type, *args):
            if response_type == SubscriptionResponseType.OK:
                result = ResultOfSubscription(**response_data)
                results.append(result.result)
            if response_type == SubscriptionResponseType.ERROR:
                raise TonException(error=ClientError(**response_data))

        now = int(datetime.now().timestamp())
        q_params = ParamsOfSubscribeCollection(
            collection='messages', result='created_at',
            filter={'created_at': {'gt': now}})
        subscription = async_core_client.net.subscribe_collection(
            params=q_params, callback=__callback)

        while True:
            if len(results) > 0 or int(datetime.now().timestamp()) > now + 10:
                async_core_client.net.unsubscribe(params=subscription)
                break
            time.sleep(1)

        self.assertGreater(len(results), 0)

    def test_query(self):
        q_params = ParamsOfQuery(
            query='query($time: Float){messages(filter:{created_at:{ge:$time}}limit:5){id}}',
            variables={'time': int(datetime.now().timestamp()) - 60})
        result = async_core_client.net.query(params=q_params)
        self.assertGreater(len(result.result['data']['messages']), 0)

    def test_suspend_resume(self):
        # Data for contract deployment
        keypair = async_custom_client.crypto.generate_random_sign_keys()
        abi = Abi.from_path(path=os.path.join(SAMPLES_DIR, 'Hello.abi.json'))
        with open(os.path.join(SAMPLES_DIR, 'Hello.tvc'), 'rb') as fp:
            tvc = base64.b64encode(fp.read()).decode()
        signer = Signer.Keys(keys=keypair)
        deploy_set = DeploySet(tvc=tvc)
        call_set = CallSet(function_name='constructor')

        # Prepare deployment params
        encode_params = ParamsOfEncodeMessage(
            abi=abi, signer=signer, deploy_set=deploy_set, call_set=call_set)
        encode = async_custom_client.abi.encode_message(params=encode_params)

        # Subscribe for address deploy transaction status
        transactions = []

        def __callback(response_data, response_type, *args):
            if response_type == SubscriptionResponseType.OK:
                result = ResultOfSubscription(**response_data)
                transactions.append(result.result)
                self.assertEqual(encode.address, result.result['account_addr'])
            if response_type == SubscriptionResponseType.ERROR:
                raise TonException(error=ClientError(**response_data))

        subscribe_params = ParamsOfSubscribeCollection(
            collection='transactions', result='id account_addr',
            filter={'account_addr': {'eq': encode.address}, 'status_name': {'eq': 'Finalized'}})
        subscribe = async_custom_client.net.subscribe_collection(
            params=subscribe_params, callback=__callback)

        # Send grams to new account to create first transaction
        send_grams(address=encode.address)
        # Give some time for subscription to receive all data
        time.sleep(2)

        # Suspend subscription
        async_custom_client.net.suspend()
        time.sleep(2)  # Wait a bit for suspend

        # Deploy to create second transaction.
        # Use another client, because of error: Fetch first block failed:
        # Can not use network module since it is suspended
        second_config = ClientConfig()
        second_config.network.server_address = CUSTOM_BASE_URL
        second_client = TonClient(config=second_config)

        process_params = ParamsOfProcessMessage(
            message_encode_params=encode_params, send_events=False)
        second_client.processing.process_message(params=process_params)
        second_client.destroy_context()

        # Check that second transaction is not received when
        # subscription suspended
        self.assertEqual(1, len(transactions))

        # Resume subscription
        async_custom_client.net.resume()

        # Run contract function to create third transaction
        call_set = CallSet(function_name='touch')
        encode_params = ParamsOfEncodeMessage(
            abi=abi, signer=signer, address=encode.address, call_set=call_set)
        process_params = ParamsOfProcessMessage(
            message_encode_params=encode_params, send_events=False)
        async_custom_client.processing.process_message(params=process_params)

        # Give some time for subscription to receive all data
        time.sleep(2)

        # Check that third transaction is now received after resume
        self.assertEqual(2, len(transactions))
        self.assertNotEqual(transactions[0]['id'], transactions[1]['id'])

        # Unsubscribe
        async_custom_client.net.unsubscribe(params=subscribe)

    def test_find_last_shard_block(self):
        find_params = ParamsOfFindLastShardBlock(address=GIVER_ADDRESS)
        result = async_core_client.net.find_last_shard_block(
            params=find_params)
        self.assertIsInstance(result.block_id, str)


class TestTonNetSyncCore(unittest.TestCase):
    """ Sync core is not recommended to use, so make just a couple of tests """
    def test_query_collection(self):
        q_params = ParamsOfQueryCollection(
            collection='blocks_signatures', result='id', limit=1)
        result = sync_core_client.net.query_collection(params=q_params)
        self.assertGreater(len(result.result), 0)

        q_params = ParamsOfQueryCollection(
            collection='accounts', result='id balance', limit=5)
        result = sync_core_client.net.query_collection(params=q_params)
        self.assertEqual(5, len(result.result))

        q_params = ParamsOfQueryCollection(
            collection='messages', filter={'created_at': {'gt': 1562342740}},
            result='body created_at', limit=10,
            order=[OrderBy(path='created_at', direction=SortDirection.ASC)])
        result = sync_core_client.net.query_collection(params=q_params)
        self.assertGreater(result.result[0]['created_at'], 1562342740)

        with self.assertRaises(TonException):
            q_params = ParamsOfQueryCollection(
                collection='messages', result='')
            sync_core_client.net.query_collection(params=q_params)

    def test_wait_for_collection(self):
        now = int(datetime.now().timestamp())
        q_params = ParamsOfWaitForCollection(
            collection='transactions', filter={'now': {'gt': now}},
            result='id now')
        result = sync_core_client.net.wait_for_collection(params=q_params)
        self.assertGreater(result.result['now'], now)

        with self.assertRaises(TonException):
            q_params = ParamsOfWaitForCollection(
                collection='transactions', filter={'now': {'gt': now}},
                result='id now', timeout=1)
            sync_core_client.net.wait_for_collection(params=q_params)

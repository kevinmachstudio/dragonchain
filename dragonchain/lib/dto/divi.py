# Copyright 2020 Dragonchain, Inc.
# Licensed under the Apache License, Version 2.0 (the "Apache License")
# with the following modification; you may not use this file except in
# compliance with the Apache License and the following modification to it:
# Section 6. Trademarks. is deleted and replaced with:
#      6. Trademarks. This License does not grant permission to use the trade
#         names, trademarks, service marks, or product names of the Licensor
#         and its affiliates, except as required to comply with Section 4(c) of
#         the License and to reproduce the content of the NOTICE file.
# You may obtain a copy of the Apache License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the Apache License with the above modification is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied. See the Apache License for the specific
# language governing permissions and limitations under the Apache License.

import math
import base64
from typing import Optional, Any, Dict

import secp256k1
import requests
import bit

from dragonchain.lib.dto import model
from dragonchain import exceptions
from dragonchain import logger


AVERAGE_BLOCK_TIME = 600  # in seconds (10 minutes)
CONFIRMATIONS_CONSIDERED_FINAL = 6
BLOCK_THRESHOLD = 10  # The number of blocks that can pass by before trying to send another transaction
MINIMUM_SATOSHI_PER_BYTE = 10

_log = logger.get_logger()


class DiviNetwork(model.InterchainModel):
    def __init__(self, name: str, rpc_address: str, testnet: bool, b64_private_key: str, authorization: Optional[str] = None):
        self.blockchain = "divi"
        self.name = name
        self.rpc_address = rpc_address
        self.authorization = authorization
        self.testnet = testnet
        if testnet:
            self.priv_key = bit.PrivateKeyTestnet.from_bytes(base64.b64decode(b64_private_key))
        else:
            self.priv_key = bit.Key.from_bytes(base64.b64decode(b64_private_key))
        self.address = self.priv_key.address

    def _calculate_transaction_fee(self) -> int:
        """Get the current satoshi/byte fee estimate
        Returns:
            satoshi/byte fee estimate
        """
        resp = self._call("estimateFee", 2)
        satoshi_per_byte = math.ceil(
            btc_to_satoshi(resp["feerate"]) / 1024
        )  # feerate is in BTC/kB; divide by 1024 to convert to BTC/byte, then convert to satoshi/byte
        _log.info(f"[BTC] Satoshis/Byte: {satoshi_per_byte}")
        return MINIMUM_SATOSHI_PER_BYTE if satoshi_per_byte < MINIMUM_SATOSHI_PER_BYTE else satoshi_per_byte

    def get_current_block(self) -> int:
        """Get the current latest block number of the network
        Returns:
            The latest known mined block number on the network
        """
        return self._call("getBlockCount")

    def ping(self) -> None:
        """Ping this network to check if the given node is reachable and authorization is correct (raises exception if not)"""
        if self.get_current_block() == 0:
            raise exceptions.InterchainConnectionError("The RPC ping call failed")

    def _call(self, method: str, *args: Any) -> Any:
        """Call the remote divi node RPC with a method and parameters
        Args:
            method: The divi json rpc method to call
            args: The arbitrary arguments for the method (in order)
        Returns:
            The result from the rpc call
        Raises:
            exceptions.InterchainConnectionError: If the remote call returned an error
        """
        r = requests.post(
            self.rpc_address,
            json={"method": method, "params": list(args), "id": "REPLACE ME WITH RANDOM NUMBER", "jsonrpc": "2.0"},
            headers={"Authorization": f"Basic ${self.authorization}", "Content-Type": "application/json"},
            timeout=20,
        )
        if r.status_code != 200:
            raise exceptions.InterchainConnectionError(f"Error from bitcoin node with http status code {r.status_code} | {r.text}")
        response = r.json()
        if response.get("error") or response.get("errors"):
            raise exceptions.InterchainConnectionError(f"The RPC call got an error response: {response}")
        return response["result"]

    def export_as_at_rest(self) -> Dict[str, Any]:
        """Export this network to be saved in storage
        Returns:
            DTO as a dictionary to be saved
        """
        return {
            "version": "1",
            "blockchain": self.blockchain,
            "name": self.name,
            "rpc_address": self.rpc_address,
            "authorization": self.authorization,
            "testnet": self.testnet,
            "private_key": self.get_private_key(),
        }


def btc_to_satoshi(btc: float) -> int:
    """Convert a btc value to satoshis
    Args:
        btc: The amount of btc to convert
    Returns:
        The integer of satoshis for this conversion
    """
    return int(btc * 100000000)

import pytest
from sovtoken.constants import ADDRESS, AMOUNT, MINT_PUBLIC, OUTPUTS, XFER_PUBLIC, SEQNO

from indy_node.test.auth_rule.helper import sdk_send_and_check_auth_rule_request
from indy_common.authorize.auth_actions import ADD_PREFIX
from indy_common.authorize.auth_constraints import AuthConstraint
from sovtokenfees.sovtokenfees_auth_map import sovtokenfees_auth_map, add_xfer
from plenum.common.constants import STEWARD, TXN_TYPE
from plenum.common.exceptions import RequestRejectedException
from plenum.test.helper import sdk_sign_request_objects, sdk_send_and_check


def mint_tokens(helpers, addresses):
    outputs = [{ADDRESS: addresses[0], AMOUNT: 1000}]
    return helpers.general.do_mint(outputs)


def do_transfer(txnPoolNodeSet, sdk_pool_handle, helpers, looper, sdk_wallet, addresses, amount, adjust_change=0):
    [address_giver, address_receiver] = addresses

    utxos = helpers.general.get_utxo_addresses([address_giver])

    utxos = helpers.request.find_utxos_can_pay(utxos[0], amount)
    inputs = [{ADDRESS: utxo["address"], SEQNO: utxo["seqNo"]} for utxo in utxos]
    change = sum([utxo["amount"] for utxo in utxos]) - amount
    outputs = [
        {ADDRESS: address_receiver, AMOUNT: amount},
        {ADDRESS: address_giver, AMOUNT: change + adjust_change},
    ]

    request = helpers.request.transfer(inputs, outputs, identifier=sdk_wallet[1])
    signed_reqs = sdk_sign_request_objects(looper, sdk_wallet,
                                           [request])
    sdk_send_and_check(signed_reqs, looper, txnPoolNodeSet, sdk_pool_handle)


def test_auth_xfer(helpers,
                   addresses,
                   looper,
                   sdk_wallet_trustee,
                   sdk_pool_handle,
                   mint_tokens,
                   new_client_wallet, txnPoolNodeSet, sdk_wallet_steward):
    """
    1. Send a transfer txn XFER_PUBLIC from client
    2. Change the auth rule for adding XFER_PUBLIC to 1 STEWARD signature
    3. Send a transfer from client, check that auth validation failed.
    4. Send and check that a transfer request with STEWARD signature pass.
    5. Change the auth rule to a default value.
    6. Send and check a transfer txn from client.
    """
    transfer_count = 10
    client_wallet = (new_client_wallet[0], new_client_wallet[1])

    do_transfer(txnPoolNodeSet, sdk_pool_handle, helpers, looper, client_wallet, addresses[:2], transfer_count)

    sdk_send_and_check_auth_rule_request(looper,
                                         sdk_wallet_trustee,
                                         sdk_pool_handle,
                                         auth_action=ADD_PREFIX,
                                         auth_type=XFER_PUBLIC,
                                         field='*',
                                         new_value='*',
                                         constraint=AuthConstraint(role=STEWARD, sig_count=1,
                                                                   need_to_be_owner=False).as_dict)

    with pytest.raises(RequestRejectedException, match="Not enough STEWARD signatures"):
        do_transfer(txnPoolNodeSet, sdk_pool_handle, helpers, looper, client_wallet, addresses[:2], transfer_count)

    do_transfer(txnPoolNodeSet, sdk_pool_handle, helpers, looper, sdk_wallet_steward, addresses[:2], transfer_count)

    sdk_send_and_check_auth_rule_request(looper,
                                         sdk_wallet_trustee,
                                         sdk_pool_handle,
                                         auth_action=ADD_PREFIX,
                                         auth_type=XFER_PUBLIC,
                                         field='*',
                                         new_value='*',
                                         constraint=sovtokenfees_auth_map[add_xfer.get_action_id()].as_dict)

    do_transfer(txnPoolNodeSet, sdk_pool_handle, helpers, looper, client_wallet, addresses[:2], transfer_count)

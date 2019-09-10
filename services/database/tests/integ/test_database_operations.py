# coding: utf-8
# Copyright (c) 2016, 2019, Oracle and/or its affiliates. All rights reserved.

import json
import pytest

from tests import util
from tests import test_config_container
from common_test_database import invoke, networking_cleanup, networking, db_systems, db_systems_cleanup, match_on
from common_test_database import CASSETTE_LIBRARY_DIR, ADMIN_PASSWORD, DB_VERSION, DB_RECOVERY_WINDOW
from common_test_database import DB_PROVISIONING_TIME_SEC, DB_TERMINATING_TIME_SEC


@pytest.fixture(autouse=True, scope='module')
def vcr_fixture(request):
    with test_config_container.create_vcr(cassette_library_dir=CASSETTE_LIBRARY_DIR, match_on=match_on).use_cassette('database_test_database_operations.yml'):
        yield


@pytest.fixture(scope='module')
def networking_test_database_operations(runner, config_file, config_profile, network_client, request):
    subnet_ocid_1, subnet_ocid_2, default_route_table_ocid, ig_ocid, vcn_ocid, networking_dict = networking(network_client, "_database_operations")
    yield networking_dict
    networking_cleanup(runner, config_file, config_profile, network_client, subnet_ocid_1, subnet_ocid_2, default_route_table_ocid, ig_ocid, vcn_ocid)


@pytest.fixture(scope='module')
def db_systems_test_database_operations(runner, config_file, config_profile, networking_test_database_operations, network_client, request):
    db_system_id_1, db_system_id_2 = db_systems(runner, config_file, config_profile, networking_test_database_operations, network_client, request)
    yield [db_system_id_1, db_system_id_2]
    db_systems_cleanup(runner, config_file, config_profile, db_system_id_1, db_system_id_2)


@util.long_running
def test_database_operations(runner, config_file, config_profile, db_systems_test_database_operations):
    # create database
    params = [
        'database', 'create',
        '--db-system-id', db_systems_test_database_operations[0],
        '--db-version', DB_VERSION,
        '--admin-password', ADMIN_PASSWORD,
        '--recovery-window-in-days', DB_RECOVERY_WINDOW,
        '--db-name', 'clidbop'
    ]

    result = invoke(runner, config_file, config_profile, params)
    util.validate_response(result)

    json_result = json.loads(result.output)
    database_id = json_result['data']['id']

    # get database
    util.wait_until(['db', 'database', 'get', '--database-id', database_id], 'AVAILABLE', max_wait_seconds=DB_PROVISIONING_TIME_SEC)

    # list databases
    params = [
        'database', 'list',
        '--compartment-id', util.COMPARTMENT_ID,
        '--db-system-id', db_systems_test_database_operations[0]
    ]

    result = invoke(runner, config_file, config_profile, params)
    util.validate_response(result)

    # list databases with --limit 0
    params = [
        'database', 'list',
        '--compartment-id', util.COMPARTMENT_ID,
        '--db-system-id', db_systems_test_database_operations[0],
        '--limit', '0'
    ]

    result = invoke(runner, config_file, config_profile, params)
    util.validate_response(result)
    assert len(result.output) == 0

    # update database
    params = [
        'database', 'update',
        '--database-id', database_id,
        '--auto-backup-enabled', 'true',
        '--recovery-window-in-days', DB_RECOVERY_WINDOW,
        '--force'
    ]

    result = invoke(runner, config_file, config_profile, params)
    util.validate_response(result)

    json_result = json.loads(result.output)
    assert json_result['data']['db-backup-config']['auto-backup-enabled'] is True

    util.wait_until(['db', 'database', 'get', '--database-id', database_id], 'AVAILABLE', max_wait_seconds=DB_PROVISIONING_TIME_SEC)

    # delete database
    params = [
        'database', 'delete',
        '--database-id', database_id,
        '--force'
    ]

    result = invoke(runner, config_file, config_profile, params)
    util.validate_response(result)
    util.wait_until(['db', 'database', 'get', '--database-id', database_id], 'TERMINATED', max_wait_seconds=DB_TERMINATING_TIME_SEC, succeed_if_not_found=True)
    util.wait_until(['db', 'system', 'get', '--db-system-id', db_systems_test_database_operations[0]], 'AVAILABLE', max_wait_seconds=DB_TERMINATING_TIME_SEC)

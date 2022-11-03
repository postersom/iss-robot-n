import os
import re
import sys
import time
import json
import signal
import shutil
import psutil
import logging
import platform
import subprocess

from database import db_session, engine, Base
from model.test import Test
from model.status import Status
from model.testcaselist import TestCaseList
from model.alltestcaselist import AllTestCaseList
from connexion import NoContent, request
from datetime import datetime
from os.path import join, dirname
from sqlalchemy.ext.serializer import loads, dumps
from sqlalchemy import inspect
from sqlalchemy.orm import joinedload_all
from model.testView import test_schema
from robot.api import TestSuite
from robot.api.parsing import get_model
from logging.handlers import RotatingFileHandler
from model.swagger.testing import Testing
from model.swagger.managing import Managing

from controllers.status_controller import *
from controllers.setting_controller import *
from controllers.userinteraction_controller import *

# Global variables
WORKING = []
managing_model = Managing()

def remove_sync_point_internal(sn):
    global managing_model
    try:
        if sn in managing_model.all_sn_scaning:
            managing_model.all_sn_scaning.remove(sn)
    except Exception as e:
        print(e)
        return False
    return True


def get_tests(limit):
    q = db_session.query(Test).options(joinedload_all('statuses')).all()
    return [test_schema.dump(p).data for p in q][:limit]


def get_test_slots(total):
    test_slot = [{'slot': i, 'data': {}} for i in range(1, total+1)]
    for i in db_session.query(Test).options(joinedload_all('statuses')).all():
        location = test_schema.dump(i).data['location']
        item = test_schema.dump(i).data
        item['statuses'] = sorted(item['statuses'], key=lambda i: i['id'], reverse=True)
        item['test_info'] = dict()
        if len(item['statuses']) > 0:
            item['test_info']['created'] = item['statuses'][-1]['created']
            if ':' == item['test_info']['created'][-3:-2]:
                item['test_info']['created'] = item['test_info']['created'][:-3] + item['test_info']['created'][-2:]
            if ':' == item['statuses'][0]['created'][-3:-2]:
                item['statuses'][0]['created'] = item['statuses'][0]['created'][:-3] + item['statuses'][0]['created'][-2:]
            if item['statuses'][0]['status'] != 'end_suite':
                item['test_info']['status'] = 'Testing'
                for test_case in item['statuses']:
                    if test_case['status'] == 'end_test' and test_case['message'].split(':')[1][:4] == 'FAIL':
                        item['test_info']['status'] = 'failing'
                        break

                item['test_info']['test_case'] = item['statuses'][0]['message']
                created_time = datetime.datetime.strptime(item['test_info']['created'], '%Y-%m-%dT%H:%M:%S.%f%z')
                tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
                elapsed_time = datetime.datetime.now(tz) - created_time.replace(tzinfo=tz)
                item['test_info']['elapsed_time'] = str(elapsed_time).split('.')[0]
            else:
                creat_time = datetime.datetime.strptime(item['test_info']['created'], '%Y-%m-%dT%H:%M:%S.%f%z')
                finish_time = datetime.datetime.strptime(item['statuses'][0]['created'], '%Y-%m-%dT%H:%M:%S.%f%z')
                item['test_info']['elapsed_time'] = str(finish_time - creat_time).split('.')[0]
                item['test_info']['status'] = item['statuses'][0]['message'].split(':')[1].strip()
                item['test_info']['status'] = 'passes' if item['test_info']['status'] == 'PASS' else 'failed'
        test_slot[int(location)-1] = {'slot': int(location), 'data': item}
    if len(test_slot) > 0:
        for interact in get_interactions():
            tmp_slot = int(interact['slot_no'])
            test_slot[tmp_slot-1]['data']['user_interactions'] = interact
    return test_slot


def put_test(test):
    logging.info('Creating test ...')
    test['created'] = datetime.datetime.now()
    db_session.add(Test(**test))
    db_session.commit()
    return NoContent, 201


def delete_test(id):
    test = db_session.query(Test).filter(Test.id == id).one_or_none()
    if test is not None:
        logging.info('Deleting pet %s..', id)
        db_session.query(Test).filter(Test.id == id).delete()
        db_session.commit()
        return NoContent, 204
    else:
        return NoContent, 404


def check_test_slot_isEmpty(location):
    q = test = db_session.query(Test).filter(
        Test.location == location).one_or_none()
    if not q:
        return True
    return False


def get_status_slot(location):
    statuses = db_session.query(Status).filter(
        Status.location == location)
    return [p.dump() for p in statuses]


def get_testcaselist_slot(location):
    return [p.dump() for p in db_session.query(TestCaseList).filter(TestCaseList.location == location)]


def get_alltestcaselist_slot(location):
    return [p.dump() for p in db_session.query(AllTestCaseList).filter(AllTestCaseList.location == location)]

# Testing functions ###


def scanin(body):
    """
        execute robot framwork to testing with serial number that provide from website
    """
    # Prepare variable for this process

    global managing_model
    testing_model = Testing()
    tmpReturnData = testing_model.return_data
    request_body = Testing.from_dict(request.get_json())
    log_header = "[{}-{}]".format("Testing", "Scanin")
    managing_model.print_log.info(
        log_header, "request body is\n{}".format(request_body))
    # Set path of root this testing.
    testing_model.root_path = request_body.get(
        "code_from"), request_body.get("slot_location")
    print("scanin", testing_model.root_path)

    ck_empty = testing_model.root_path.split("/")

    # Send verify serial number to ODC if get status OK process can start test
    if request_body.get("odc_type") == "verifychamber":

            # return tmpReturnData, 400

        try:
            result_odc = testing_model.run_command_python(
                testing_model.getScaninChamberPathScript(), json.dumps(request_body))
            result_odc_json = json.loads(result_odc)
        except Exception as e:
            managing_model.print_log.error(
                log_header, "Error with: {}".format(e))
            tmpReturnData["error"] = "Error with execution ODC Script."
        else:
            managing_model.print_log.info(
                log_header, "Verify process is done.\n{}".format(result_odc_json))
            tmpReturnData["data"] = result_odc_json

        status = 200 if tmpReturnData["error"] else 400
        return tmpReturnData, 200
    elif request_body.get("odc_type") == "verify":

            # return tmpReturnData, 400

        try:
            result_odc = testing_model.run_command_python(
                testing_model.getScaninPathScript(), json.dumps(request_body))
            result_odc_json = json.loads(result_odc)
        except Exception as e:
            if ck_empty[3] == "empty":
                print("Please create Zone Release", ck_empty[3])
                tmpReturnData["error"] = "Please create Zone Release"
            else:
                managing_model.print_log.error(
                    log_header, "Error with: {}".format(e))
                tmpReturnData["error"] = "Error with execution ODC Script."
        else:
            managing_model.print_log.info(
                log_header, "Verify process is done.\n{}".format(result_odc_json))
            tmpReturnData["data"] = result_odc_json

        status = 200 if tmpReturnData["error"] else 400
        return tmpReturnData, 200
    # If parameter not found process cannot start test
    if not request_body or not request_body.get("sn_count"):
        managing_model.print_log.error(
            log_header, "Process is not starting test because parameter is empty.Please try again")
        tmpReturnData["error"] = "Process is not starting test because parameter is empty.Please try again"
        return json.dumps(tmpReturnData), 400
    managing_model.print_log.info(
        log_header, testing_model.getScaninPathScript())

    # tmp_csn = request_body.get("slot_location").split("_", 1)[0]
    tmp_batch_id = request_body.get("batch_id")
    tmp_sn = request_body.get("serial_number").strip()

    if not tmp_batch_id in managing_model.all_sn_scaning:
        managing_model.all_sn_scaning[tmp_batch_id] = {
            "sns": [],
            "sn_count": int(request_body.get("sn_count"))
        }

    if not tmp_sn in managing_model.all_sn_scaning.get(tmp_batch_id) and not request_body.get("odc_type") == "verify":
        managing_model.print_log.info(log_header, "New sn scan-in")
        managing_model.all_sn_scaning[tmp_batch_id]["sns"].append(
            request_body.get("serial_number").strip())
    else:
        tmpReturnData["error"] = "Duplicate sn scan-in: {}".format(tmp_sn)
        return tmpReturnData, 400

    # Execute ODC Script
    try:
        result_odc = testing_model.run_command_python(
            testing_model.getScaninPathScript(), json.dumps(request_body))
    except Exception as e:
        managing_model.print_log.error(log_header, "Error on execute Scanin_ODC.py with: {}".format(e))
        tmpReturnData["error"] = "Process error on execute Scanin_ODC.py: {}".format(e)
        return json.dumps(tmpReturnData), 400
    else:
        try:
            result_odc_json = json.loads(result_odc)
        except Exception as e:
            managing_model.print_log.error(log_header, f'Cannot create json of result from odc script with: {e}')
            tmpReturnData["error"] = f'Process is not starting test when create json data from ODC script: {e}'
            return json.dumps(tmpReturnData), 400
        else:
            managing_model.print_log.info(log_header, "Result from odc:\n{}".format(result_odc_json))
            try:
                if (not request_body.get("operation") or request_body.get("operation") == 'None') and not testing_model.checkRobotFileExists(result_odc_json, request_body):
                    tmpReturnData["error"] = "Cannot found robot file please create robot file {}/{}_{}_{}.robot and try again.".format(
                        testing_model.root_path, result_odc_json.get("part_number"), result_odc_json.get("product_reversion"), request_body.get("logop"))
                    raise Exception
                if request_body.get("operation") and request_body.get("operation") != 'None' and not testing_model.checkRobotFileExistslu(request_body):
                    tmpReturnData["error"] = "Cannot found robot file please create robot file {}/{}.robot and try again.".format(
                        testing_model.root_path, request_body.get("operation"))
                    raise Exception
                if not testing_model.checkListenerFileExists:
                    tmpReturnData["error"] = "Cannot found listener file please create listener file and try again."
                    raise Exception

                ts_timestamp = testing_model.timestamp
                if request_body.get("loop") != None:
                    loop = 1
                else:
                    loop = ""
                # Set parameter for send to robot testing
                try:
                    parameter_robot_test, robot_name, console_log, param_timestamp = testing_model.getParameterRobot(
                        result_odc_json, request_body, request_body.get("test_case"), loop, ts_timestamp)
                except Exception as e:
                    tmpReturnData['error'] = f'Process is not starting test: {e}'
                    raise Exception

                # create all test case list
                path_to_test_suite = robot_name
                # suite = TestData(parent=None, source=path_to_test_suite)
                suite = TestSuite.from_model(get_model(path_to_test_suite))
                remove_alltestcaselist(request_body.get("slot_location"))
                # for idx, testcase in enumerate(suite.testcase_table):
                for testcase in suite.tests:
                    add_alltestcaselist(testcase.name, request_body.get("slot_location"))
                # create test in database
                if check_test_slot_isEmpty(request_body.get("slot_location")):
                    try:
                        test_case_list = request_body.get("test_case")
                        print(test_case_list)
                        if len(test_case_list) > 0:
                            for test_case in test_case_list:
                                add_testcaselist(test_case_list[test_case], request_body.get("slot_location"))
                        # use param_timestamp for the same folder name
                        tmp_batch_id = tmp_batch_id
                        serial_number = request_body.get("serial_number")
                        operation = request_body.get("operation")
                        operation_id = request_body.get("operation_id")
                        slot_location = request_body.get("slot_location")
                        slot_no = request_body.get("slot_no")
                        uut_log_dir = "{}_{}_{}".format(result_odc_json.get("product_id"), request_body.get("serial_number"), param_timestamp)
                        test_mode = request_body.get("test_mode")
                        code_from = request_body.get("code_from")
                        logop = request_body.get("logop")
                        part_number = result_odc_json.get("part_number")
                        product_reversion = result_odc_json.get(
                            "product_reversion")
                        product_id = result_odc_json.get("product_id")
                        product_name = result_odc_json.get("product_name")

                        add_testing(tmp_batch_id, serial_number, robot_name, operation, operation_id, slot_location, slot_no,
                                    uut_log_dir, test_mode, code_from, logop, part_number, product_reversion, product_id, product_name, 1)
                        add_loop(request_body.get("slot_location"), request_body.get("loop"))
                        # Execute robot testing
                        cmd = "{} -m robot {} {} {} &".format(sys.executable, parameter_robot_test, robot_name, console_log)
                        print("cmd= {}".format(cmd))
                        pro = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
                    except Exception as e:
                        tmpReturnData["error"] = "Cannot add test: {}".format(
                            e)
                        # remove test case list
                        remove_alltestcaselist(request_body.get("slot_location"))
                        remove_testcaselist(request_body.get("slot_location"))
                        # find already added testing or not then remove test
                        remove_testing(request_body.get("slot_location"))
                        raise Exception

                else:
                    tmpReturnData["error"] = "Process is not starting test: Test exist in database slot: {}".format(
                        request_body.get("slot_location"))
                    managing_model.print_log.error(
                        log_header, tmpReturnData["error"])
            except Exception as e:
                managing_model.print_log.error(
                    log_header, tmpReturnData["error"])
                # Remove all file in BOM of this serial number if path exists
                if os.path.exists("{}.py".format(testing_model.bom_path(result_odc_json.get("serial_number")))):
                    os.remove("{}.py".format(testing_model.bom_path(
                        result_odc_json.get("serial_number"))))
                print(e)
            else:
                if not tmpReturnData["error"]:
                    tmpReturnData["data"] = "Process starting test"
                    tmpReturnData["error"] = None

    if not tmpReturnData["error"] is None:
        remove_sync_point_internal(tmp_sn)
    # De-Allocate variable
    testing_model = None
    request_body = None
    log_header = None
    result_odc = None
    result_odc_json = None
    parameter_robot_test = None
    robot_name = None
    status = 200 if tmpReturnData["data"] else 400

    return tmpReturnData, status

# Testing functions ###


def verify(body):
    '''
        execute robot framwork to testing with serial number that provide from website
    '''
    request_body = json.loads(body.decode())
    if not request_body:
        return "Parameter is empty", 401
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    serial_number = request_body.get("serial_number")
    sn_timestamp = "{}_{}".format(serial_number, timestamp)
    result_odc = subprocess.check_output(
        [sys.executable, '/opt/Robot/ODC_Script/Scanin_ODC.py', json.dumps(request_body)])
    print("Response from ODC: {}".format(result_odc))
    result_odc_json = json.loads(result_odc)
    res = dict()

    res["status"] = "OK"
    res["error_message"] = "Return value from ODC"
    # db_session.add(Test(test_id='123', file_name=u'W400_PreFCT_MTP',
    #                     work_dir=u'/tmp/work', location=request_body["slot_no"], created=datetime.datetime.utcnow()))
    return res, 200


def continue_test(body):
    '''
        execute robot framwork to testing with serial number that provide from website
    '''
    global managing_model
    testing_model = Testing()
    tmpReturnData = testing_model.return_data
    json_request_body = Testing.from_dict(request.get_json())
    log_header = "[{}-{}]".format("Testing", "Continue-Test")
    managing_model.print_log.info(log_header, f"request json body is\n{json_request_body}")
    testing_model.root_path = json_request_body.get(
        "code_from"), json_request_body.get("slot_location")
    print("Continue Test path ", testing_model.root_path)

    request_body = get_test_by_slot(json_request_body["slot_location"])
    managing_model.print_log.info(
        log_header, "request body is\n{}".format(request_body))

    status = get_status_slot(json_request_body["slot_location"])
    remove_statuses(json_request_body["slot_location"])

    testcaselist = dict()

    get_list_test = get_testcaselist_slot(json_request_body["slot_location"])
    num_list = len(get_list_test)
    if num_list > 0:
        for idx, val in enumerate(get_list_test):
            testcaselist[idx] = val['test_case']

    else:
        get_list_test = get_alltestcaselist_slot(
            json_request_body["slot_location"])
        for idx, val in enumerate(get_list_test):
            testcaselist[idx] = val['test_case']

    for idx, val in enumerate(status):
        if val['message'] == 'Result:PASS' and status[idx-1]['message'][0] != '0':
            test = db_session.query(Test).filter(
                Test.location == json_request_body["slot_location"]).one_or_none()
            db_session.add(Status(status=status[idx-1]['status'], message=status[idx-1]['message'],
                                  location=status[idx-1]['location'], created=status[idx-1]['created'], test_id=test.id))
            db_session.add(Status(status=status[idx]['status'], message=status[idx]['message'],
                                  location=status[idx]['location'], created=status[idx]['created'], test_id=test.id))
            db_session.commit()

            for item in testcaselist:
                if testcaselist[item] == status[idx-1]['message']:
                    del testcaselist[item]
                    break
        elif idx == 0:
            test = db_session.query(Test).filter(
                Test.location == json_request_body["slot_location"]).one_or_none()
            db_session.add(Status(status=status[idx]['status'], message=status[idx]['message'],
                                  location=status[idx]['location'], created=status[idx]['created'], test_id=test.id))
            db_session.commit()

    count_testcaselist = len(testcaselist)
    print(count_testcaselist)
    if (count_testcaselist == 0):
        return tmpReturnData, 400

    request_body["second_param"] = json_request_body["second_param"]
    request_body["slot_location"] = json_request_body["slot_location"]
    request_body["test_case"] = testcaselist

    result_odc_json = dict()
    result_odc_json["part_number"] = request_body["part_number"]
    result_odc_json["product_reversion"] = request_body["product_reversion"]
    result_odc_json["product_id"] = request_body["product_id"]

    tmp_batch_id = request_body.get("batch_id")
    tmp_sn = request_body.get("serial_number").strip()

    if not tmp_batch_id in managing_model.all_sn_scaning:
        managing_model.all_sn_scaning[tmp_batch_id] = {
            "sns": [],
            "sn_count": int(json_request_body.get("sn_count"))
        }

    if not tmp_sn in managing_model.all_sn_scaning.get(tmp_batch_id) and not request_body.get("odc_type") == "verify":
        managing_model.print_log.info(log_header, "New sn scan-in")
        managing_model.all_sn_scaning[tmp_batch_id]["sns"].append(
            request_body.get("serial_number").strip())
    else:
        tmpReturnData["error"] = "Duplicate sn scan-in: {}".format(tmp_sn)
        return tmpReturnData, 400

    loop = ""
    print("uut_log_dir ", request_body["uut_log_dir"])
    ts_timestamp = request_body["uut_log_dir"].split("_")
    ts_timestamp = ts_timestamp[-1]
    print("ts_timestamp ", ts_timestamp)
    # Set parameter for send to robot testing
    try:
        parameter_robot_test, robot_name, console_log, param_timestamp = testing_model.getParameterRobot(
            result_odc_json, request_body, request_body["test_case"], loop, ts_timestamp)
    except Exception as e:
        tmpReturnData["error"] = "Process is not starting test: {}".format(
            e)
        raise Exception

    # Execute robot testing
    try:
        cmd = "{} -m robot {} {} {} &".format(
            sys.executable, parameter_robot_test, robot_name, console_log)
        print("cmd= {}".format(cmd))
        pro = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, shell=True)
    except Exception as e:
        tmpReturnData["error"] = "Cannot add test: {}".format(
            e)
        raise Exception

    if not tmpReturnData["error"] is None:
        remove_sync_point_internal(tmp_sn)
    # De-Allocate variable
    testing_model = None
    request_body = None
    log_header = None
    result_odc = None
    result_odc_json = None
    parameter_robot_test = None
    robot_name = None
    status = 200 if tmpReturnData["data"] else 400

    return tmpReturnData, status


def verify_testcase(body):

    request_body = body
    testing_model = Testing()
    testing_model.root_path = request_body.get(
        "code_from"), request_body.get("slot_location")
    request_body["odc_type"] = "verify"

    result_odc = json.loads(testing_model.run_command_python(
        testing_model.getScaninPathScript(), json.dumps(request_body)))
    result_odc["robot_path"] = testing_model.root_path

    return result_odc


def checkout(body):
    '''
        Delivery out testing from server with serial number
    '''
    tmpReturnError = "Cannot checkout because"
    global managing_model
    log_header = "[{}-{}]".format("Testing_Controller", "Checkout")
    request_body = Testing.from_dict(request.get_json())
    testing_model = Testing()
    tmpReturnData = testing_model.return_data
    # Set path of root this testing.

    testing_model.root_path = request_body.get(
        "code_from"), request_body.get("slot_location")

    # testing_model.root_logs = request_body.get("test_mode")

    if not request_body:
        tmpReturnData["error"] = "Cannot checkout the test becuase parameter is empty"
        return tmpReturnData, 400

    serial_number = request_body.get("serial_number")
    uut_log_path = testing_model.uut_log_path(request_body)
    print(uut_log_path, "uut_log_path")
    bom_path = testing_model.bom_path(serial_number)
    request_body["uut_log_dir_path"] = uut_log_path

    # Execute Scanout_ODC.py for check can checkout this serial number
    print(request_body, "request_body")

    dataLog = get_test_info_status_by_slot(request_body.get("slot_location"))

    if not dataLog or len(dataLog['statuses']) == 0:
        managing_model.print_log.error(
            log_header, "Checkout fail with: No test data in database serial number: {}".format(serial_number))
        tmpReturnData["error"] = "Checkout fail with: No test data in database serial number: {}".format(
            serial_number)
        return tmpReturnData, 400

    dataLog["start_time"] = dataLog.get(
        "start_time").strftime("%Y-%m-%d %H:%M:%S")
    request_body["start_time"] = dataLog["start_time"]
    dataLog["end_time"] = dataLog.get("end_time").strftime("%Y-%m-%d %H:%M:%S")
    request_body["end_time"] = dataLog["end_time"]

    release_version = get_release_version_by_location(
        request_body.get("slot_location"))

    request_body["release_version"] = release_version['value']

    try:
        result_odc = testing_model.run_command_python(
            testing_model.getScanoutPathScript(), json.dumps(request_body))

    except Exception as e:
        managing_model.print_log.error(
            log_header, "Error on execute Scanout_ODC.py with: {}".format(e))
        tmpReturnData["error"] = "{} error on execute Scanout_ODC.py: {}".format(
            tmpReturnError, e)
        return tmpReturnData, 400

    # Create JSON object from result of ODC script
    try:
        result_odc_json = json.loads(result_odc)
        print(result_odc_json, "result_odc_json")
    except Exception as e:
        managing_model.print_log.error(
            log_header, "Cannot create json from result scanout odc with: {}".format(e))
        tmpReturnData["error"] = "{} error on parse data to json"
        return tmpReturnData, 400

    if not result_odc_json.get("status") == "OK" or not result_odc_json.get("status"):
        managing_model.print_log.error(log_header, "ScanOut from ODC return fail with: {} ".format(
            result_odc_json.get("error_message")))
        tmpReturnData["error"] = "{} get status fail from Scanout_ODC.py because: {}".format(
            tmpReturnError, result_odc_json.get("error_message"))
        return tmpReturnData, 400

    try:
        result_delete_inteaction = delete_interaction_by_slot(
            request_body.get("slot_no"))
    except Exception as e:
        managing_model.print_log.error(log_header, "Error with: {}".format(e))
        tmpReturnData["error"] = True

    # Extract log file before remove directory
    checkZip, message = testing_model.archiveLogFile(
        request_body, dataLog.get("start_time")[:10])
    if not checkZip:
        managing_model.print_log.error(
            log_header, "Cannot create archive file because: {}".format(message))
        tmpReturnData["error"] = "{} error on archive file: {}".format(
            tmpReturnError, message)
        return tmpReturnData, 400

    checkMeta, message = testing_model.createMetadataLog(
        request_body, dataLog)
    if not checkMeta:
        managing_model.print_log.error(
            log_header, "Cannot create metadata file because: {}".format(message))
        tmpReturnData["error"] = "{} error on creating metadata file: {}".format(
            tmpReturnError, message)
        return tmpReturnData, 400

    try:
        # Remove all files in UUT of this serial number if path exists
        if os.path.exists(uut_log_path):
            shutil.rmtree(uut_log_path)
        # Remove all file in BOM of this serial number if path exists
        if os.path.exists(bom_path):
            shutil.rmtree(bom_path)
    except Exception as e:
        managing_model.print_log.error(
            log_header, "Cannot checkout {}:\n{}".format(serial_number, e))
        tmpReturnData["error"] = "{} error on delete data of {} with {}".format(
            tmpReturnError, serial_number, e)
        return tmpReturnData, 400

    remove_loop(request_body.get("slot_location"))
    remove_alltestcaselist(request_body.get("slot_location"))
    remove_testcaselist(request_body.get("slot_location"))
    remove_testing(request_body.get("slot_location"))
    managing_model.print_log.info(
        log_header, "Checkout {} complete".format(serial_number))

    tmp_batch_id = request_body.get("batch_id")
    if managing_model.all_sn_scaning.get(tmp_batch_id) and len(managing_model.all_sn_scaning.get(tmp_batch_id).get("sns")) > 0:
        managing_model.all_sn_scaning.pop(tmp_batch_id)
        if managing_model.sn_sync.get(tmp_batch_id):
            managing_model.sn_sync.pop(tmp_batch_id)
        managing_model.print_log.info(
            log_header, "Remove data scan-in complete")
    managing_model.print_log.info(
        log_header, "Checkout {} complete".format(serial_number))

    # De-Allocate variable
    testing_model = None
    serial_number = None
    uut_log_path = None
    bom_path = None
    checkZip = None
    message = None
    tmp_csn_sn = None
    tmpReturnData["data"] = "Checkout is complete"
    return tmpReturnData, 200

# call init testcase


def set_flag_abort(body):
    request_body = json.loads(body.decode())
    if not request_body:
        return "Parameter is empty", 400

    flag = request_body["flag"]
    res = {"data": {"message": ""}, "error": ""}

    q = db_session.query(Test).filter(
        Test.location == request_body["slot_location_no"]).one_or_none()
    q.flag = flag
    res["data"]["message"] = "Set flag Successfully."
    q.update()
    db_session.commit()

    return res, 200


def abort_pid(pid):
    # Send the signal to all the process groups
    os.killpg(os.getpgid(pid), signal.SIGTERM)
    return "ff"


def abort_process(test_location):
    procs = {p.pid: p.info for p in psutil.process_iter(
        attrs=['name', 'cmdline']) if 'python' in p.info['name']}

    for x in procs:
        cmd = procs[x]["cmdline"]
        for var in reversed(cmd):
            if test_location in var:
                # os.killpg(os.getpgid(x), signal.SIGTERM)  # Send the signal to all the process groups
                os.kill(x, signal.SIGTERM)
                return "Killed, Test Abort Successfully."
    return "Not found process, Test may be aborted or finished"

# ui call abort command


def test_abort(body):
    request_body = json.loads(body.decode())
    if not request_body:
        return "Parameter is empty", 400

    res = {"data": {"message": ""}, "error": ""}

    q = db_session.query(Test).filter(
        Test.location == request_body["test_location"]).one_or_none()
    if q.flag == "lock":
        q.flag = "abort"
        res["data"]["message"] = "Set Abort Successfully. Please wait for test ending."
        q.update()
        db_session.commit()
    elif q.flag == "abort":
        res["data"]["message"] = "Test was set to abort. Please wait for test ending."
    else:
        message = abort_process(request_body["test_location"])
        res["data"]["message"] = message
        stop_loop(request_body["test_location"])
        delete_interaction_by_slot(request_body["test_location"])

    return res, 200

# test profile call to check abort flag


def get_abort(slot_location_no):
    '''
        Abort robot testing process with user
    '''

    # testing_model = Testing()
    # tmpReturnData = testing_model.return_data
    # global managing_model
    # print(slot_no)
    q = db_session.query(Test).filter(
        Test.location == slot_location_no).one_or_none()
    print(q.flag)

    res = {"data": {"flag": q.flag}, "error": ""}
    return res, 200

    # managing_model.log_header = "[{}-{}]".format("Testing_Controller", "abort")
    # tmp_csn_sn = request_body.get("slot_location").split("_", 1)[0]

    # if not tmp_csn_sn:
    #     managing_model.print_log.error(managing_model.log_header, "Chassis is not found")
    #     tmpReturnData["error"] = "Chassis is not found on slot-location"
    #     return json.dumps(tmpReturnData), 400

    # try:
    #     tmp_parent_sn = managing_model.all_sn_scaning.get(tmp_csn_sn)
    # except Exception as e:
    #     managing_model.print_log.error(managing_model.log_header, "Cannot get chassis serial number that user starting test\n:{}".format(e))
    #     tmpReturnData["error"] = "Cannot get chassis serial number that user starting test"
    #     return json.dumps(tmpReturnData), 400

    # tmp_parent_sn.remove(request_body.get("serial_number"))

    # tmpReturnData["data"] = "Abort is complete"

    # De-allowcate variable
    # request_body = None
    # testing_model = None
    # tmp_csn_sn = None
    # tmp_parent_sn = None

    # return tmpReturnData, 200


def view_log(start_time, product_name, sn):
    log_header = "[{}-{}]".format("Testing_Controller", "viewLog")
    print(
        log_header, "Welcome to view log: {}".format(sn))
    testing_model = Testing()
    tmpReturnError = "Cannot view log because"
    tmpReturnData = testing_model.return_data
    print(
        log_header, "star_time: {}\nsn: {}".format(start_time, sn))

    if not (sn == "" and start_time == "") and (sn == "" or start_time == ""):
        testing_model.print_log.error(
            log_header, "some parameter is empty please try again with all parameter are not empty or all parameter are empty")
        tmpReturnData["error"] = "some parameter is empty please try again with all parameter are not empty or all parameter are empty"
    else:
        try:
            if not (sn == "" and start_time == ""):
                try:
                    datetime.datetime.strptime(start_time, "%Y-%m-%d")
                except Exception as e:
                    testing_model.print_log.error(
                        log_header, "Datetime is wrong format, , it should be YYYY-mm-dd")
                    return "Start Datetime is wrong format, it should be YYYY-mm-dd: {}".format(start_time), 400
                else:
                    testing_model.viewLog(start_time, product_name, sn)
            else:
                testing_model.viewLog()
        except Exception as e:
            testing_model.print_log.error(
                log_header, "Error view log with: {}".format(e))

    status = 200 if tmpReturnData.get("data") else 400

    # De-allocate variable
    testing_model = None
    log_header = None
    tmpReturnError = None

    return tmpReturnData, status


def view_scanin(slot_num, chassis_name):
    test = get_tests(100)
    testing_model = Testing()
    data = testing_model.view_scanin()
    verify_data = {'LOGOP','OPERATORID','SLOT','SERIALNUMBER','FAMILY','OPERATION'}
    for d in data:
        for verify in verify_data:
            if verify not in d:
                d[verify] = '-'
                d['status'] = 'verified-failed'
                d['message'] = 'Can not find {}'.format(verify)
                break
            else:
                d['status'] = 'verified'
                d['message'] = 'verified'
        if d['status'] == 'verified':
            for i in range(1, slot_num+1):
                if d['SLOT'] == chassis_name + str(i):
                    d['status'] = 'verified'
                    d['message'] = 'verified'
                    break
                else:
                    d['status'] = 'verified-failed'
                    d['message'] = 'Can not find Slot {}'.format(d['SLOT'])

        if d['status'] == 'verified':
            for t in test:
                if d['SLOT'] == t['location']:
                    d['status'] = 'verified-failed'
                    d['message'] = '{} is available'.format(d['SLOT'])
                    break
            
    return data


def requeue(body):
    '''
        Function remove xml file in /opt/Scanin
    '''
    request_body = json.loads(body.decode())
    print(request_body)

    testing_model = Testing()
    response = testing_model.find_xml_scanin(request_body['serial_number'])

    print(response)

    return response


def sync_point(body):
    '''
        Function sync point for provide robot framework wait or continue testing
    '''
    global managing_model
    request_body = json.loads(body.decode())
    # tmpReturnData = managing_model.return_sync_point
    managing_model.log_header = "{}-{}".format("managing", "sync_point")
    tmp_allow_timeout = True if request_body.get(
        "allow_timeout") == "True" else False
    request_body["allow_timeout"] = tmp_allow_timeout
    tmp_batch_id = request_body.get("batch_id")
    managing_model.print_log.info(
        managing_model.log_header, "Parameter: {}".format(request_body))
    tmp_return = {
        "data": None,
        "error": True
    }

    if managing_model.remove_csn_after_complete(request_body):
        tmp_return["data"] = "Sync-point is complete"
        tmp_return["error"] = None
        managing_model.print_log.info(
            managing_model.log_header, "after remove Sync sn: {}\n ".format(managing_model.sn_sync))
        return tmp_return, 200

    if request_body.get("setup"):
        request_body["setup"] = True if request_body.get(
            "setup") == "True" else False

    if request_body.get("sn_count") == 1:
        tmp_return['data'] = "Sync-point is complete"
        tmp_return['error'] = None
        return tmp_return, 200

    try:
        if managing_model.sn_sync.get(tmp_batch_id) and len(managing_model.sn_sync.get(tmp_batch_id).get("sn")) > 0 and request_body.get("allow_timeout"):
            managing_model.check_timeout_sync_point(request_body)
        managing_model.check_sync_point(request_body)
    except Exception as e:
        managing_model.print_log.error(
            managing_model.log_header, "error on check sync point: {}".format(e))

    tmp_return["data"] = managing_model.sn_sync.get(tmp_batch_id).get("data")
    tmp_return["error"] = managing_model.sn_sync.get(tmp_batch_id).get("error")
    managing_model.print_log.info(
        managing_model.log_header, "return data: {}".format(tmp_return))

    # De-allocate variable
    request_body = None
    status = 200 if not tmp_return.get("error") else 400

    return tmp_return, status


def remove_sync_point(body):
    '''
        Remove serial number that kept on scan-in process out of stack that using check on sync-point process
    '''
    global managing_model
    request_body = json.loads(body.decode())
    tmpReturnData = managing_model.return_sync_point
    managing_model.log_header = 'Test_controller-remove_sync_point'
    managing_model.print_log.info(managing_model.log_header, "Remove sync-point request from robot")
    managing_model.remove_sn_from_syncpoint(request_body)
    managing_model.print_log.info(managing_model.log_header,
                                  f"Status from remove serial-number: {managing_model.return_sync_point.get('error')}")
    status = 200 if not tmpReturnData.get("error") else 400
    return tmpReturnData, status


def queue_hardware(body):
    """
        Function Request/Release queue for using a queue or using a queue complete.
    """
    global managing_model
    managing_model.log_header = "managing-queue"
    queue = json.loads(body.decode())
    managing_model.print_log.info(managing_model.log_header, "Check parameter: {}".format(body))
    tmpReturnData = managing_model.return_queue
    tmpReturnData["error"] = True
    if not queue.get("serial_number") and not queue.get("type"):
        tmpReturnData["error"] = "Cannot get serial number and queue type please check parameter and try again."
    else:
        try:
            managing_model.queue_access_hardware(queue)
        except Exception as e:
            managing_model.print_log.info(managing_model.log_header, e)
            tmpReturnData["data"] = e
    status = 200 if not tmpReturnData['error'] else 400
    managing_model.print_log.info(managing_model.log_header, f"Return: {tmpReturnData}")
    return tmpReturnData, status


def update_latest_code(repo_path):
    for i in ['checkout .', 'master', 'pull']:
        git_query = subprocess.Popen(f'/usr/bin/git {i} --quiet', cwd=repo_path, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, shell=True)
        _, error = git_query.communicate()
        if len(error.decode('utf-8').strip()) > 0:
            return error.decode('utf-8').strip(), True
    return "Code Updated", None


def get_data_monitor():
    test_slot = list()
    info = dict()
    settings = db_session.query(Setting).all()
    for item in settings:
        if item.dump()['name'] == 'ipaddress':
            info['ipaddress'] = item.dump()['value']
        elif item.dump()['name'] == 'slot':
            info['slot'] = int(item.dump()['value'])
        elif item.dump()['name'] == 'chassis_name':
            info['chassis_name'] = item.dump()['value']
        elif item.dump()['name'] == 'station':
            info['station'] = item.dump()['value']

    for i in range(1, info['slot']+1):
        slot_name = f"{info['chassis_name']}{i}"
        url = f"http://{info['ipaddress']}:8080/"
        data = {'station': info['station'],
                'slot_name': slot_name,
                'slot_number': i,
                'result': 'empty',
                'test_time': 'Available',
                'sn': '',
                'led': '',
                'url': url,
                'product_name': ''
                }
        test_slot.append(data)
    q = db_session.query(Test).options(joinedload_all('statuses')).all()
    for p in q:
        location = test_schema.dump(p).data['location']
        item = test_schema.dump(p).data
        item["statuses"] = sorted(
            item["statuses"], key=lambda i: i['id'], reverse=True)
        item["test_info"] = dict()
        if len(item["statuses"]) > 0:
            # set created time from first test case created
            item["test_info"]["created"] = item["statuses"][-1]["created"]
            # remove timezone string
            if ":" == item["test_info"]["created"][-3:-2]:
                item["test_info"]["created"] = item["test_info"]["created"][:-3] + \
                    item["test_info"]["created"][-2:]
            if ":" == item["statuses"][0]["created"][-3:-2]:
                item["statuses"][0]["created"] = item["statuses"][0]["created"][:-3] + \
                    item["statuses"][0]["created"][-2:]
            # check last status not end suite(still testing)
            if item["statuses"][0]["status"] != "end_suite":
                # loop to find failing
                item["test_info"]["status"] = "Testing"
                for test_case in item["statuses"]:
                    # if end testcase  and message is fail
                    if test_case["status"] == "end_test" and test_case["message"].split(':')[1][:4] == "FAIL":
                        item["test_info"]["status"] = "failing"
                        break

                item["test_info"]["test_case"] = item["statuses"][0]["message"]
                created_time = datetime.datetime.strptime(item["test_info"]["created"], "%Y-%m-%dT%H:%M:%S.%f%z")
                # get timezone info
                tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
                # change time object to use same timezone and differential
                elapsed_time = datetime.datetime.now(tz) - created_time.replace(tzinfo=tz)
                # remove millisecond
                item["test_info"]["elapsed_time"] = str(elapsed_time).split('.')[0]
            else:
                created_time = datetime.datetime.strptime(item["test_info"]["created"], "%Y-%m-%dT%H:%M:%S.%f%z")
                finished_time = datetime.datetime.strptime(item["statuses"][0]["created"], "%Y-%m-%dT%H:%M:%S.%f%z")
                elapsed_time = finished_time - created_time
                item["test_info"]["elapsed_time"] = str(elapsed_time).split('.')[0]
                item["test_info"]["status"] = item["statuses"][0]["message"].split(':')[1].strip()
                if item["test_info"]["status"] == "FAIL":
                    item["test_info"]["status"] = "failed"
                elif item["test_info"]["status"] == "PASS":
                    item["test_info"]["status"] = "passes"
                else:
                    item["test_info"]["status"] = "failed"
        test_slot[int(location)-1] = {"slot": int(location), "data": item}

        slot_name = f"{info['chassis_name']}{location}"

        url = f"http://{info['ipaddress']}:8080/"
        data = {'station': info['station'],
                'slot_name': slot_name,
                'slot_number':  location,
                'result': item["test_info"]["status"],
                'test_time': item["test_info"]["elapsed_time"],
                'sn': test_schema.dump(p).data['serial_number'],
                'led': '',
                'url': url,
                'product_name': test_schema.dump(p).data['product_name']
                }
        test_slot[int(location)-1] = data

    if len(test_slot) > 0:
        user_interactions = get_interactions()
        for interact in user_interactions:
            tmp_slot = int(interact["slot_no"])
            test_slot[tmp_slot-1]["result"] = "Interaction"

    return test_slot

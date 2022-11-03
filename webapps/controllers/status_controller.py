from sqlalchemy.sql.elements import Null
from database import db_session
from model.status import Status
from model.test import Test
from model.loop import Loop
from model.testcaselist import TestCaseList
from model.alltestcaselist import AllTestCaseList
from model.setting import Setting
from connexion import NoContent
from os.path import join, dirname
import datetime
import logging

from sqlalchemy import or_
import os
import shutil
import sys
import subprocess
from flask import g
from model.swagger.testing import Testing
from model.statusView import status_schema
from model.swagger.managing import Managing
from flask import current_app as app
from werkzeug.local import LocalProxy

import json
import re

managing_model = Managing()

# Create json file path.
# test_json_path = join(dirname(__file__), 'test.json')
# status_json_path = join(dirname(__file__), 'status.json')
# testcaselist_json_path = join(dirname(__file__), 'testcaselist.json')
# alltestcaselist_json_path = join(dirname(__file__), 'alltestcaselist.json')
# loop_json_path = join(dirname(__file__), 'loop.json')


def add_testing(batch_id, sn, robot_name, operation, operation_id, location, slot_no, uut_log_dir, test_mode, code_from, logop, part_number, product_reversion, product_id, product_name, loop_no):
    db_session.add(Test(batch_id=batch_id, serial_number=sn, robot_name=robot_name, operation=operation, operation_id=operation_id, test_mode=test_mode, code_from=code_from,
                        logop=logop, part_number=part_number, product_reversion=product_reversion, product_id=product_id, product_name=product_name, loop_no=loop_no, uut_log_dir=uut_log_dir, flag="unlock", location=location, slot_no=slot_no, created=datetime.datetime.now()))
    db_session.commit()

def remove_testing(location):
    db_session.query(Test).filter(Test.location == location).delete()
    db_session.query(Status).filter(
        Status.location == location).delete()
    db_session.commit()

def remove_only_testing(location):
    db_session.query(Test).filter(Test.location == location).delete()
    db_session.commit()

def remove_statuses(location):
    db_session.query(Status).filter(
        Status.location == location).delete()
    db_session.commit()

def add_testcaselist(test_case, location):
    print(location)
    db_session.add(TestCaseList(
        test_case=test_case, location=location))
    db_session.commit()

def remove_testcaselist(location):
    db_session.query(TestCaseList).filter(
        TestCaseList.location == location).delete()
    db_session.commit()

def add_alltestcaselist(test_case, location):
    db_session.add(AllTestCaseList(
        test_case=test_case, location=location))
    db_session.commit()

def remove_alltestcaselist(location):
    db_session.query(AllTestCaseList).filter(
        AllTestCaseList.location == location).delete()
    db_session.commit()

def add_loop(location, loop_no):
    db_session.add(Loop(loop_no=loop_no, location=location))
    db_session.commit()

def remove_loop(location):
    db_session.query(Loop).filter(
        Loop.location == location).delete()
    db_session.commit()

def stop_loop(location):
    db_session.query(Loop).filter(
        Loop.location == location).delete()
    db_session.commit()
    db_session.add(Loop(loop_no="", location=location))
    db_session.commit()

def get_loop_by_slot(location):
    loop = db_session.query(Loop).filter(
        Loop.location == location).one_or_none()
    return loop.dump() or ('Not found', 404)

def get_statuses(limit):
    q = db_session.query(Status)
    # return [p.dump() for p in q][:limit]
    return [status_schema.dump(p).data for p in q][:limit]

def get_status(id):
    status = db_session.query(Status).filter(
        Status.id == id).one_or_none()
    return status.dump() or ('Not found', 404)

def get_status_by_slot(location):
    statuses = db_session.query(Status).filter(
        Status.location == location)
    return [p.dump() for p in statuses]

def get_test_info_status_by_slot(location):
    statuses = db_session.query(Status).filter(Status.location == location).filter(
        or_(Status.status == "start_suite", Status.status == "end_suite", Status.status == "end_test"))
    info = dict()
    info["statuses"] = get_status_by_slot(location)
    for index, item in enumerate(info["statuses"]):
        item["created"] = item["created"].strftime("%Y-%m-%d %H:%M:%S")

    info["chassis_name"] = ''
    info["slot_no"] = ''
    info["result"] = ''
    for x in statuses:
        status = x.__dict__
        if status["status"] == "start_suite":
            info["start_time"] = status["created"]
        elif status["message"].split(':')[1][:5] == "ABORT":
            info["result"] = "ABORT"
            info["end_time"] = status["created"]
        elif status["status"] == "end_suite":
            info["end_time"] = status["created"]
            if info["result"] != "ABORT":
                info["result"] = status["message"].split(':')[1].strip()
    return info


def put_status(status):
    logging.info('Creating status')
    logging.info('Put status to  : ' + status['test_location'])
    logging.info('Put status : ' + status['status'])
    logging.info('Put message : ' + status['message'])

    created = datetime.datetime.now()
    test = db_session.query(Test).filter(
        Test.location == status['test_location']).one_or_none()
    db_session.add(Status(status=status['status'], message=status['message'],
                          location=status['test_location'], created=created, test_id=test.id))
    # status['created'] = datetime.datetime.utcnow()
    # db_session.add(Status(**status))
    if(status['status'] == 'start_suite'):
        start_suite = db_session.query(Status).filter(Status.location == status['test_location']).filter(
            Status.status == "start_suite")
        if not start_suite.count() > 0:
            db_session.commit()
    else:
        db_session.commit()

    if(status['status'] == 'end_suite'):
        testing_model = Testing()
        request_body = dict()
        request_test = get_test_by_slot(status['test_location'])
        logging.info('data test : {}'.format(request_test))
        request_body['uut_log_dir'] = get_test_by_slot(status['test_location'])['uut_log_dir']
        log_template = get_setting_by_name_for_status('log_template')[
            'value']
        chassis_name = get_setting_by_name_for_status('chassis_name')['value']
        
        request_test["slot_location"] = request_test["location"]

        
        testing_model.root_path = request_test.get(
        "code_from"), request_test["slot_location"]

        uut_log_path = testing_model.uut_log_path(request_body)
        print(uut_log_path, "uut_log_path")

        dataLog = get_test_info_status_by_slot(status['test_location'])

        dataLog["start_time"] = dataLog.get(
            "start_time").strftime("%Y-%m-%d %H:%M:%S")
        dataLog["end_time"] = dataLog.get(
            "end_time").strftime("%Y-%m-%d %H:%M:%S")

        station = get_setting_by_name_for_status('station')['value']
        sn = request_test["serial_number"]
        sn_datetime = request_body["uut_log_dir"].split("_")
        sn_datetime = sn_datetime[-1]
        sn_datetime = sn_datetime.replace('-', '')
        result = dataLog["result"]
        test_mode = request_test["test_mode"]
        product_name = request_test["product_name"]
        logop = request_test["logop"]

        log_template = log_template.replace('==station==', station)
        log_template = log_template.replace('==sn==', sn)
        log_template = log_template.replace('==chassis==', chassis_name)
        log_template = log_template.replace('==datetime==', sn_datetime)
        log_template = log_template.replace('==result==', result)
        log_template = log_template.replace('==test_mode==', test_mode)
        log_template = log_template.replace('==product_name==', product_name)
        log_template = log_template.replace('==logop==', logop)

        request_body['log_name'] = log_template
        request_body['product_name'] = request_test["product_name"]

        logging.info('request_body : {}'.format(request_body))

        # check loop
        loop_max = get_loop_by_slot(status['test_location'])
        logging.info('loop : {}'.format(loop_max["loop_no"]))
        if loop_max["loop_no"] and loop_max["loop_no"] > request_test["loop_no"]:
            print("Loop")
            tmpReturnData = testing_model.return_data

            tmp_batch_id = request_test.get("batch_id")

            request_test["second_param"] = {"option_param" : ''}
            request_test["test_case"] = {}

            ts_timestamp = request_body["uut_log_dir"].split("_")
            ts_timestamp = ts_timestamp[-1]
            print("ts_timestamp " ,ts_timestamp)

            result_odc_json = dict()
            result_odc_json["part_number"] = request_test.get("part_number")
            result_odc_json["product_reversion"] = request_test.get("product_reversion")
            result_odc_json["product_id"] = request_test.get("product_id")

            print("result_odc_json", result_odc_json)
            print("request_body", request_test)

            loop = request_test["loop_no"] + 1

            get_test_case = get_testcaselist_by_slot(status['test_location'])

            test_case = dict()
            for index, item in enumerate(get_test_case):
                test_case[index] = item
            
    
            # Set parameter for send to robot testing
            try:
                parameter_robot_test, robot_name, console_log, param_timestamp = testing_model.getParameterRobot(
                    result_odc_json, request_test, test_case, loop, ts_timestamp)
            except Exception as e:
                logging.info("Process is not starting test: {}".format(e))
                raise Exception
            
            print(parameter_robot_test)
            
            # remove old test
            remove_only_testing(status['test_location'])

            # Add test 
            try:
                # use param_timestamp for the same folder name
                tmp_batch_id = tmp_batch_id 
                serial_number = request_test.get("serial_number") 
                robot_path = "{}/{}.robot".format(testing_model.root_path, robot_name)
                operation = request_test.get("operation")
                operation_id = request_test.get("operation_id")
                slot_location = request_test.get("location")
                slot_no = request_test.get("slot_no")
                uut_log_dir = "{}_{}_{}".format(result_odc_json.get("product_id"), request_test.get("serial_number"), param_timestamp)
                test_mode = request_test.get("test_mode")
                code_from = request_test.get("code_from")
                logop = request_test.get("logop")
                part_number = request_test.get("part_number")
                product_reversion = request_test.get("product_reversion")
                product_id = request_test.get("product_id")
                product_name = request_test.get("product_name")
                loop_no = request_test["loop_no"] + 1
                add_testing(tmp_batch_id, serial_number, robot_path, operation, operation_id, slot_location, slot_no,
                                    uut_log_dir, test_mode, code_from, logop, part_number, product_reversion, product_id, product_name, loop_no)
                # Execute robot testing
                cmd = "{} -m robot {} {} {} &".format(
                    sys.executable, parameter_robot_test, robot_name, console_log)
                print("cmd= {}".format(cmd))
                pro = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, shell=True)
            except Exception as e:
                tmpReturnData["error"] = "Cannot add test: {}".format(
                    e)
                # remove test case list
                remove_testcaselist(request_test.get("location"))
                remove_alltestcaselist(request_test.get("location"))
                # find already added testing or not then remove test
                remove_only_testing(request_body.get("slot_location"))
                raise Exception

        # else:

        #     # Extract log file before remove directory
        #     testing_model.archiveLogFile(
        #         request_body, dataLog.get("start_time")[:10])

        #     testing_model.createMetadataLog(request_body, dataLog)
        #     print(uut_log_path)
        #     try:
        #         # Remove all files in UUT of this serial number if path exists
        #         if os.path.exists(uut_log_path):
        #             shutil.rmtree(uut_log_path)
        #     except Exception as e:
        #         logging.info(
        #             "Cannot checkout {}:\n{}".format(sn, e))
            
        #     logging.info("Checkout {} complete".format(sn))
        #     global managing_model

        #     tmp_batch_id = request_body.get("batch_id")
        #     if managing_model.all_sn_scaning.get(tmp_batch_id) and len(managing_model.all_sn_scaning.get(tmp_batch_id).get("sns")) > 0:
        #         managing_model.all_sn_scaning.pop(tmp_batch_id)
        #         if managing_model.sn_sync.get(tmp_batch_id):
        #             managing_model.sn_sync.pop(tmp_batch_id)
        #         logging.info("Remove data scan-in complete")
        #     logging.info("Checkout {} complete".format(sn))


        testing_model = None
        request_body = None
        result_odc_json = None
        parameter_robot_test = None
        robot_name = None

    return NoContent, 201


def convert_timestamp(item_date_object):
    if isinstance(item_date_object, (datetime.date, datetime.datetime)):
        return str(item_date_object)


def update_data(location):
    raw_statuses = get_status_by_slot(location)
    statuses = list()
    info = {'result': "Testing", 'slot_no': location}
    if len(raw_statuses) == 0:
        return {}
    for index, item in enumerate(raw_statuses):
        if item["status"] == 'start_test':
            elapsed_time = datetime.datetime.now() - item['created']
            statuses.append({'name': item['message'], 'status': 'Testing', 'started': item['created'],
                             'finished': None, 'elapsed_time': str(elapsed_time).split('.')[0], 'reason': '', "id": index})
        elif item["status"] == 'end_test':
            msg = item['message'].split(' ', 1)
            statuses[-1]['status'] = msg[0].replace("Result:", "")
            if len(msg) > 1:
                statuses[-1]['reason'] = msg[1]
            else:
                statuses[-1]['reason'] = '-'
            statuses[-1]['finished'] = item['created']
            elapsed_time = statuses[-1]['finished'] - statuses[-1]['started']
            statuses[-1]['elapsed_time'] = str(elapsed_time).split('.')[0]
            statuses[-1]['finished'] = str(statuses[-1]
                                           ['finished']).split('.')[0]
            statuses[-1]['started'] = str(statuses[-1]
                                          ['started']).split('.')[0]
        elif item["status"] == 'end_suite':
            info["result"] = item['message'].split(':')[1].strip()
        elif item["status"] == 'start_suite':
            pass
    if item["status"] != 'start_suite':
        statuses[-1]['started'] = str(statuses[-1]['started']).split('.')[0]
    return {"statuses": statuses, "info": info}


def delete_status(id):
    status = db_session.query(Status).filter(Status.id == id).one_or_none()
    if status is not None:
        logging.info('Deleting pet %s..', id)
        db_session.query(Status).filter(Status.id == id).delete()
        db_session.commit()
        return NoContent, 204
    else:
        return NoContent, 404


def view_status_rawlog(location, filename):
    testing_model = Testing()
    test = get_test_by_slot(location)
    path = test["uut_log_dir"]
    testing_model.root_path = test["code_from"], location

    raw_logs_dir = "Raw_logs"
    fullpath = os.path.join(testing_model.getLogsPath,
                            path, raw_logs_dir, filename+'.raw')
    print(fullpath)
    testing_model = None
    if not os.path.exists(fullpath):
        data = ['File not found']
        return data
    else:
        with open(fullpath, 'r', encoding="ISO-8859-1") as f:
            data = f.readlines()
        data = [x.strip() for x in data]
        return data


def view_status_sequencelog(location, filename):
    testing_model = Testing()
    test = get_test_by_slot(location)
    path = test["uut_log_dir"]
    testing_model.root_path = test["code_from"], location

    raw_logs_dir = "Raw_logs"
    fullpath = os.path.join(testing_model.getLogsPath,
                            path, raw_logs_dir, filename+'.txt')
    print(fullpath)
    testing_model = None
    if not os.path.exists(fullpath):
        data = ['File not found']
        return data
    else:
        with open(fullpath, 'r', encoding="ISO-8859-1") as f:
            data = f.readlines()
        data = [x.strip() for x in data]
        return data

def view_bom_value(location, filename):
    testing_model = Testing()
    test = get_test_by_slot(location)
    testing_model.root_path = test["code_from"], location
    fullpath = testing_model.bom_path(filename+'.py')
    print(fullpath)
    testing_model = None
    if not os.path.exists(fullpath):
        data = ['File not found']
        return data
    else:
        with open(fullpath, 'r', encoding="ISO-8859-1") as f:
            data = f.readlines()
        data = [x.strip() for x in data]
        return data


def view_log_rawlog(filezip, filename):
    testing_model = Testing()
    folder = filezip.split(".")[0]
    raw_logs_dir = "Raw_logs"
    fullpath = os.path.join(testing_model.getViewLogPath,
                            folder, raw_logs_dir, filename+'.raw')
    print(fullpath)
    if not os.path.exists(fullpath):
        data = ['File not found']
        return data
    else:
        with open(fullpath, 'r', encoding="ISO-8859-1") as f:
            data = f.readlines()
        data = [x.strip() for x in data]
        return data


def view_log_sequencelog(filezip, filename):
    testing_model = Testing()
    folder = filezip.split(".")[0]
    raw_logs_dir = "Raw_logs"
    fullpath = os.path.join(testing_model.getViewLogPath,
                            folder, raw_logs_dir, filename+'.txt')
    print(fullpath)
    if not os.path.exists(fullpath):
        data = ['File not found']
        return data
    else:
        with open(fullpath, 'r', encoding="ISO-8859-1") as f:
            data = f.readlines()
        data = [x.strip() for x in data]
        return data


def get_test_by_slot(location):
    test = db_session.query(Test).filter(
        Test.location == location).one_or_none()
    return test.dump() or ('Not found', 404)


def get_testcaselist_by_slot(location):
    testcaselist = list()
    test_cases = db_session.query(TestCaseList).filter(
        TestCaseList.location == location).all()
    for test_case in test_cases:
        testcaselist.append(test_case.test_case)

    return testcaselist

def get_alltestcaselist_by_slot(location):
    alltestcaselist = list()
    test_cases = db_session.query(AllTestCaseList).filter(
        AllTestCaseList.location == location).all()
    for test_case in test_cases:
        alltestcaselist.append(test_case.test_case)

    return alltestcaselist


def get_setting_by_name_for_status(name):
    setting = db_session.query(Setting).filter(
        Setting.name == name).one_or_none()
    if setting:
        return setting.dump()
    else:
        return ('Not found', 404)

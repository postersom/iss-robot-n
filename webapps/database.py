from sqlalchemy import create_engine, Column, DateTime, String
from sqlalchemy.orm import scoped_session, sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from flask import current_app
import datetime
import os
from os.path import join, dirname
from dotenv import load_dotenv
import subprocess
import socket

import dateutil.parser

import json

# Create .env file path.
dotenv_path = join(dirname(__file__), '.env')

# Create json file path.
setting_json_path = join(dirname(__file__), 'setting.json')
logop_json_path = join(dirname(__file__), 'logop.json')
release_version_json_path = join(dirname(__file__), 'release_version.json')
# test_json_path = join(dirname(__file__), 'controllers', 'test.json')
# status_json_path = join(dirname(__file__), 'controllers', 'status.json')
# testcaselist_json_path = join(dirname(__file__), 'controllers', 'testcaselist.json')
# loop_json_path = join(dirname(__file__), 'controllers', 'loop.json')

# Load file from the path.
load_dotenv(dotenv_path)
path = join(dirname(__file__), os.getenv('DATABASE'))
engine = create_engine('sqlite:///'+path, convert_unicode=True)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False,
                                         bind=engine))
Base = declarative_base()


def init_db():
    print("init_db")
    from model.setting import Setting
    from model.status import Status
    from model.test import Test
    from model.log import Log
    from model.userinteraction import Userinteraction
    # Base.query = db_session.query_property()
    # Base.metadata.drop_all(bind=engine)
    # Base.metadata.create_all(bind=engine)
    # db_session.commit()


def populate():
    print("populate")
    from model.setting import Setting
    from model.logop import Logop
    from model.releaseversion import ReleaseVersion
    from model.test import Test
    from model.status import Status
    from model.testcaselist import TestCaseList
    from model.loop import Loop

    test_list = db_session.query(Test).all()
    for test in test_list:
        id = test.dump()["id"]
        location = test.dump()["location"]
        created = datetime.datetime.now()
        # print(test.dump())
        statuses = db_session.query(Status).filter(
            Status.test_id == id, Status.status == "end_suite").all()
        if len(statuses) == 0:
            db_session.add(Status(status="end_test", message="Result:ABORT ISS Stop process",
                                  location=location, created=created, test_id=test.id))
            db_session.add(Status(status="end_suite", message="Result:FAIL",
                                  location=location, created=created, test_id=test.id))
    #     else:
    #         for status in statuses:
    #             print(status.dump())
    print("***************************************")

    try:
        print("Update version")
        git_version = subprocess.check_output(
            '/usr/bin/git describe --tag', cwd=dirname(__file__), shell=True).decode('utf-8').strip()
        # db_session.add(Setting(name=u'version', title=u'Version',
        #                        value=git_version, categories=u'lock', order=0))
        setting = db_session.query(Setting).filter(Setting.name == "version").first()
        setting.value = git_version

    except Exception as e:
        print(e)

    # with open(setting_json_path) as json_file:
    #     json_decoded = json.load(json_file)
    #     for item in json_decoded:
    #         if json_decoded[item]["name"] == 'ipaddress':
    #             try:
    #                 s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #                 s.connect(('10.196.66.66', 1))
    #                 ipaddress = s.getsockname()[0]
    #                 s.close()
    #             except:
    #                 ipaddress = '0.0.0.0'
    #             db_session.add(Setting(name=json_decoded[item]["name"], title=json_decoded[item]["title"],
    #                                value=ipaddress, categories=json_decoded[item]["categories"], order=json_decoded[item]["order"]))
    #         else:
    #             db_session.add(Setting(name=json_decoded[item]["name"], title=json_decoded[item]["title"],
    #                                value=json_decoded[item]["value"], categories=json_decoded[item]["categories"], order=json_decoded[item]["order"]))

    # with open(release_version_json_path) as json_file:
    #     json_decoded = json.load(json_file)
    #     for item in json_decoded:
    #         db_session.add(ReleaseVersion(
    #             location=item, value=json_decoded[item]["release_path_version"]))

    # with open(logop_json_path) as json_file:
    #     json_decoded = json.load(json_file)
    #     for item in json_decoded:
    #         db_session.add(Logop(name=item, order=json_decoded[item]["order"]))

    # with open(test_json_path) as json_file:
    #     json_decoded = json.load(json_file)
    #     for item in json_decoded:
    #         created = dateutil.parser.isoparse(json_decoded[item]["created"])
    #         db_session.add(Test(batch_id=json_decoded[item]["batch_id"], serial_number=json_decoded[item]["sn"], robot_name=json_decoded[item]["robot_name"], operation_id=json_decoded[item]["operation_id"], test_mode=json_decoded[item]["test_mode"], code_from=json_decoded[item]["code_from"],
    #                             logop=json_decoded[item]["logop"], part_number=json_decoded[item]["part_number"], product_reversion=json_decoded[item]["product_reversion"], product_id=json_decoded[item]["product_id"], product_name=json_decoded[item]["product_name"], uut_log_dir=json_decoded[item]["uut_log_dir"], flag=json_decoded[item]["flag"], location=json_decoded[item]["location"], created=created))

    # with open(status_json_path) as json_file:
    #     json_decoded = json.load(json_file)
    #     for item in json_decoded:
    #         created = dateutil.parser.isoparse(json_decoded[item]["created"])
    #         db_session.add(Status(status=json_decoded[item]["status"], message=json_decoded[item]["message"],
    #                               slot_no=json_decoded[item]["slot_no"], created=created, test_id=json_decoded[item]["test_id"]))

    # with open(testcaselist_json_path) as json_file:
    #     json_decoded = json.load(json_file)
    #     for item in json_decoded:
    #         db_session.add(TestCaseList(test_case=json_decoded[item]["test_case"], slot_no=json_decoded[item]["slot_no"]))

    # with open(loop_json_path) as json_file:
    #     json_decoded = json.load(json_file)
    #     for item in json_decoded:
    #         db_session.add(Loop(loop_no=json_decoded[item], slot_no=item))

    db_session.commit()

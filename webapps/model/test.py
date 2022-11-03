from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from database import Base
from flask import json
from collections import defaultdict
from sqlalchemy import inspect


class Test(Base):
    __tablename__ = 'test_db'
    id = Column(Integer, primary_key=True)
    batch_id = Column(String(100))
    serial_number = Column(String(100))
    robot_name = Column(String(100))
    flag = Column(String(100))
    uut_log_dir = Column(String(1000))  # uut_log_dir
    operation = Column(String(100))
    operation_id = Column(String(100))
    test_mode = Column(String(100))
    code_from = Column(String(100))
    location = Column(String(100))
    slot_no = Column(Integer)
    logop = Column(String(100))
    part_number = Column(String(100))
    product_reversion = Column(String(100))
    product_id = Column(String(100))
    product_name = Column(String(100))
    loop_no = Column(Integer)
    created = Column(DateTime())
    statuses = relationship('Status', backref="test_db")

    def update(self, id=None, batch_id=None, serial_number=None, robot_name=None, flag=None, uut_log_dir=None, operation=None, operation_id=None, test_mode=None, code_from=None, location=None, slot_no=None, logop=None, part_number=None, product_reversion=None, product_id=None, product_name=None, loop_no=None, statuses=None, created=None):
        if batch_id is not None:
            self.batch_id = batch_id
        if serial_number is not None:
            self.serial_number = serial_number
        if robot_name is not None:
            self.robot_name = robot_name
        if flag is not None:
            self.flag = flag
        if uut_log_dir is not None:
            self.uut_log_dir = uut_log_dir
        if location is not None:
            self.location = location
        if slot_no is not None:
            self.slot_no = slot_no
        if operation is not None:
            self.operation = operation
        if operation_id is not None:
            self.operation_id = operation_id
        if test_mode is not None:
            self.test_mode = test_mode
        if code_from is not None:
            self.code_from = code_from
        if logop is not None:
            self.logop = logop
        if part_number is not None:
            self.part_number = part_number
        if product_reversion is not None:
            self.product_reversion = product_reversion
        if product_id is not None:
            self.product_id = product_id
        if product_name is not None:
            self.product_name = product_name
        if loop_no is not None:
            self.loop_no = loop_no
        if created is not None:
            self.created = created
        if statuses is not None:
            self.statuses = statuses

    def dump(self):
        return dict([(k, v) for k, v in self.__dict__.items() if k[0] != '_'])

    def dump2(self):
        insp = inspect(self)
        attr_state = insp.attrs.statuses
        print(attr_state.value)
        return("completed")

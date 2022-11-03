from sqlalchemy import Column, Integer, String
from database import Base


class AllTestCaseList(Base):
    __tablename__ = 'alltestcaselist_db'
    id = Column(Integer, primary_key=True)
    test_case = Column(String(100))
    location = Column(String(100))

    def update(self, id=None, test_case=None, location=None):
        if test_case is not None:
            self.test_case = test_case
        if location is not None:
            self.location = location

    def dump(self):
        return dict([(k, v) for k, v in self.__dict__.items() if k[0] != '_'])

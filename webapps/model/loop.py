from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from database import Base


class Loop(Base):
    __tablename__ = 'loop_db'
    id = Column(Integer, primary_key=True)
    loop_no = Column(Integer)
    location = Column(String(100))

    def update(self, id=None, loop_no=None, location=None):
        if loop_no is not None:
            self.loop_no = loop_no
        if location is not None:
            self.location = location

    def dump(self):
        return dict([(k, v) for k, v in self.__dict__.items() if k[0] != '_'])

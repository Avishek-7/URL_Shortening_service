from sqlalchemy import Column, Integer, Text, DateTime, func
from sqlalchemy.orm import relationship
from db.database import Base

class URL(Base):
    __tablename__ = "urls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    long_url = Column(Text, nullable=False, unique=True)
    short_code = Column(Text, unique=True)
    clicks = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)
    user_id = Column(Integer, nullable=True)
    user = relationship("User", back_populates="urls")

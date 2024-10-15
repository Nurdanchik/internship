from sqlalchemy import Column, Integer, String, Text
from .database import Base
import json

class Face(Base):
    __tablename__ = "faces"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(Integer, unique=True, nullable=False)
    name = Column(String, index=True)
    landmarks = Column(Text, unique=False)  # Храним landmarks как строку (JSON)
    picture = Column(String)

    def as_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "landmarks": json.loads(self.landmarks) if self.landmarks else None,  # Десериализация JSON
            "picture": self.picture
        }

    # Метод для сохранения landmarks как JSON-строки
    def set_landmarks(self, landmarks_data):
        self.landmarks = json.dumps(landmarks_data)
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from umongo.frameworks import MotorAsyncIOInstance

class LockboxDB:
    
    def __init__(self, host: str, port: int):
        self.client = AsyncIOMotorClient(host, port)
        self._private_db = self.client["lockbox"]
        self._shared_db = self.client["shared"]
        self._private_instance = MotorAsyncIOInstance(self._private_db)
        self._shared_instance = MotorAsyncIOInstance(self._shared_db)
    
    def private_db(self) -> AsyncIOMotorDatabase:
        return self._private_db
    
    def shared_db(self) -> AsyncIOMotorDatabase:
        return self._shared_db

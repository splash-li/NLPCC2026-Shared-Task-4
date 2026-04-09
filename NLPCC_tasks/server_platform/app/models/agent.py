from pydantic import BaseModel

class AgentRegistration(BaseModel):
    username: str
    password: str

class AgentLogin(BaseModel):
    username: str
    password: str
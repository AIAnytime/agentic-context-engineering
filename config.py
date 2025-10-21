import os

from pydantic import BaseModel, Field


class Config(BaseModel):
    agent_dir: str = os.path.dirname(os.path.abspath(__file__)) + "/agents"
    serve_web_interface: bool = True
    reload_agents: bool = True

    generator_model: str = Field(default="gemini-2.5-flash")
    reflector_model: str = Field(default="gemini-2.5-flash")
    curator_model: str = Field(default="gemini-2.5-flash")

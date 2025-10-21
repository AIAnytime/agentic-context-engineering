import uvicorn
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app

from config import Config

config = Config()

app: FastAPI = get_fast_api_app(
    agents_dir=config.agent_dir,
    web=config.serve_web_interface,
    reload_agents=config.reload_agents,
)


def main():
    uvicorn.run(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()

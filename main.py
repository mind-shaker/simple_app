import sys
from fastapi import FastAPI

app = FastAPI()

@app.get("/python-version")
def get_python_version():
    return {"python_version": sys.version}

import json


def read_json(path):
    return json.loads(path.read_text())

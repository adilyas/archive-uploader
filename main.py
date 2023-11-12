import argparse
import json
import os
import sys

import xml.etree.ElementTree as ET

from polygon_cli import problem
from polygon_cli import config as cli_config


class ImporterConfig:
    def __init__(self, problem_dir):
        self.config_path = os.path.join(problem_dir, "import-config.json")

        if not os.path.exists(self.config_path):
            with open(self.config_path, "w") as f:
                f.write("{}")

        with open(self.config_path, "r") as f:
            self.data_json = json.loads(f.read())

    def save_config(self):
        with open(self.config_path, "w") as f:
            f.write(json.dumps(self.data_json))

    def set_imported(self):
        self.data_json["imported"] = True

    def get_imported(self):
        return "imported" in self.data_json and self.data_json["imported"]

    def set_short_name(self, short_name):
        self.data_json["short-name"] = short_name

    def set_problem_id(self, problem_id):
        self.data_json["problem-id"] = problem_id

    def get_problem_id(self):
        if "problem-id" not in self.data_json:
            return None
        return self.data_json["problem-id"]


def create_problem(short_name, retry_count=0):
    cli_config.setup_login_by_url("main")
    session = problem.ProblemSession(cli_config.polygon_url, None, None)

    problem_json = None
    try_id = 0
    while problem_json is None and try_id <= retry_count:
        create_name = short_name
        if try_id > 0:
            create_name += "-" + str(try_id + 1)
        try:
            problem_json = session.send_api_request("problem.create", {"name": create_name})
        except Exception as e:
            print(f"Failed to create problem with name {create_name}")
            print(e)

            if try_id + 1 <= retry_count:
                try_id += 1
                print("Retrying...")
    return problem_json


def create_documents_path(d):
    documents_path = os.path.join(d, "documents")
    if not os.path.exists(documents_path):
        os.mkdir(documents_path)
    descriptiontxt_path = os.path.join(documents_path, "description.txt")
    if not os.path.exists(descriptiontxt_path):
        with open(descriptiontxt_path, "w") as f:
            pass
    tutorialtxt_path = os.path.join(documents_path, "tutorial.txt")
    if not os.path.exists(tutorialtxt_path):
        with open(tutorialtxt_path, "w") as f:
            pass


def ensure_polygon_xml(problem_xml_path):
    problem_dir = os.path.dirname(problem_xml_path)
    polygon_xml_path = os.path.join(problem_dir, "problem.xml.polygon")
    if os.path.exists(polygon_xml_path):
        os.rename(problem_xml_path, problem_xml_path + ".pcms")
        os.rename(polygon_xml_path, problem_xml_path)


def main():
    parser = argparse.ArgumentParser(
            prog="PolygonContestImporter",
            description="Imports problems to polygon from a local archive",
    )
    parser.add_argument("src_dir", help="Path to a directory with problems", type=str)
    parser.add_argument("--retry-create", help="Max number of retries while creating a problem", default=0, type=int)

    options = parser.parse_args(sys.argv[1:])

    for problem_dir in os.listdir(options.src_dir):
        problem_dir = os.path.abspath(os.path.join(options.src_dir, problem_dir))
        if not os.path.isdir(problem_dir):
            continue

        problem_config = ImporterConfig(problem_dir)
        if problem_config.get_imported():
            continue

        problem_xml_path = os.path.join(problem_dir, "problem.xml")
        ensure_polygon_xml(problem_xml_path)

        create_documents_path(problem_dir)

        tree = ET.parse(problem_xml_path)
        problem_node = tree.getroot()
        short_name = problem_node.attrib["short-name"]
        print(f"Uploading problem {short_name}")

        if problem_config.get_problem_id() is None:
            try:
                problem_json = create_problem(short_name, retry_count=options.retry_create)
                problem_config.set_short_name(problem_json["name"])
                problem_config.set_problem_id(int(problem_json["id"]))
                problem_config.save_config()
            except Exception as e:
                print(f"Encountered an error while creating problem {short_name}, skipping...")
                print(e)
                continue

        try:
            cli_config.setup_login_by_url("main")
            session = problem.ProblemSession(cli_config.polygon_url, problem_config.get_problem_id(), None)
            session.import_problem_from_package(problem_dir, skip_standart_resources=False)
        except Exception as e:
            print(f"Failed to import problem {short_name}")
            print(e)
            continue
        try:
            session.send_api_request("problem.commitChanges", {"minorChanges": "true", "message": "new"})
            session.send_api_request("problem.buildPackage", {"full": "true", "verify": "true"})
        except Exception as e:
            print(f"Failed to commit problem or build a package for problem {short_name}")
            print(e)
            continue

        problem_config.set_imported()
        problem_config.save_config()


if __name__ == "__main__":
    main()

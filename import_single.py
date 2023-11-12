import difflib
import json
import os
import sys

import xml.etree.ElementTree as ET

from polygon_cli import problem
from polygon_cli import config as cli_config
from polygon_cli.exceptions import PolygonApiError

DIFF_SEP = "-" * 100


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

    def get_short_name(self):
        if "short-name" not in self.data_json:
            return None
        return self.data_json["short-name"]

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

            if try_id + 1 <= retry_count:
                try_id += 1
                print("Retrying...")
            else:
                raise e
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


def diff_resource_files(problem_node, problem_dir, session):
    files = ["olymp.sty", "statements.ftl"]
    print(f"Calculating diffs for the files {files}")

    files_node = problem_node.find("files")
    if files_node is None:
        print("No files_node")
        return {}

    resources_node = files_node.find("resources")
    if resources_node is None:
        print("No resources_node")
        return {}

    new_contents = {}
    for file in files:
        file_path = None
        for resource_file in resources_node.findall("file"):
            if resource_file.attrib["path"].endswith(file):
                file_path = os.path.join(problem_dir, resource_file.attrib["path"])
                break
        if file_path is None:
            print(f"File {file} not found")
            continue

        with open(file_path, "rU") as f:
            new_contents[file] = f.read()

    polygon_files = session.send_api_request("problem.files", {});
    assert polygon_files is not None, "No resource files in polygon"

    default_contents = {}
    for file in files:
        polygon_file = None
        for polygon_file_ in polygon_files["resourceFiles"]:
            if polygon_file_["name"].endswith(file):
                polygon_file = polygon_file_
                break
        content = session.send_api_request("problem.viewFile", {"type": "resource", "name": polygon_file["name"]}, is_json=False)
        assert content is not None, f"Failed to fetch {file} file content"

        default_contents[file] = content

    diff = {}
    for file in files:
        lhs = default_contents[file].decode("utf-8").replace('', '').split('\n')
        rhs = new_contents[file].split('\n')
        diff[file] = '\n'.join(difflib.unified_diff(lhs, rhs))
    return diff


def dump_diff(diff_sum, src_dir):
    for file, diff in diff_sum.items():
        path = os.path.join(src_dir, f"{file}.diff")
        with open(path, "w") as f:
            f.write(diff)
        print(f"Dumped {file} diff to {path}.")


def find_true_src_dir(src_dir):
    for dirpath, dirnames, filenames in os.walk(src_dir):
        if "problem.xml" in filenames:
            return os.path.dirname(dirpath)
    return src_dir


def import_single(src_dir, retry_count):
    src_dir = find_true_src_dir(src_dir)
    diff_sum = {}
    for problem_dir in os.listdir(src_dir):
        problem_dir = os.path.abspath(os.path.join(src_dir, problem_dir))
        if not os.path.isdir(problem_dir):
            continue

        problem_config = ImporterConfig(problem_dir)
        if problem_config.get_imported():
            continue

        problem_xml_path = os.path.join(problem_dir, "problem.xml")
        ensure_polygon_xml(problem_xml_path)

        create_documents_path(problem_dir)

        try:
            tree = ET.parse(problem_xml_path)
            problem_node = tree.getroot()
            short_name = problem_node.attrib["short-name"]
        except:
            print(f"Skipping non-standart package for problem {problem_dir}")
            continue

        print(f"Uploading problem {short_name}")

        if problem_config.get_problem_id() is None:
            try:
                problem_json = create_problem(short_name, retry_count=retry_count)
                problem_config.set_short_name(problem_json["name"])
                problem_config.set_problem_id(int(problem_json["id"]))
                problem_config.save_config()
            except Exception as e:
                print(f"Encountered an error while creating problem {short_name}, skipping...")
                print(e)
                continue

        cli_config.setup_login_by_url("main")
        session = problem.ProblemSession(cli_config.polygon_url, problem_config.get_problem_id(), None)

        diff = diff_resource_files(problem_node, problem_dir, session)
        for k, v in diff.items():
            if k not in diff_sum:
                diff_sum[k] = ""
            diff_sum[k] += f"\n{DIFF_SEP}\n{problem_config.get_short_name()}\n" + v

        try:
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

    dump_diff(diff_sum, src_dir)


def add_subparsers(subparsers, parents):
    import_single_parser = subparsers.add_parser("import_single",
                                                  help="Imports contest problems from contest's 'problems' dir",
                                                  parents=parents)
    import_single_parser.add_argument("src_dir", help="Path to a directory with problems", type=str)
    import_single_parser.set_defaults(func=lambda options: import_single(options.src_dir, options.retry_count))


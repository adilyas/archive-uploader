import os
import zipfile

from import_single import import_single


def import_many(archives_dir, archives, retry_count):
    archives = set(archives)
    for zip_file in os.listdir(archives_dir):
        if not zip_file.endswith(".zip") or zip_file not in archives:
            continue

        archive_name = zip_file[:-4]
        unpack_dir = os.path.abspath(os.path.join(archives_dir, archive_name))
        if not os.path.exists(unpack_dir):
            print(f"Unpacking archive {archive_name} to {unpack_dir}")
            with zipfile.ZipFile(os.path.join(archives_dir, zip_file), "r") as zip_ref:
                zip_ref.extractall(unpack_dir)

        print(f"Importing archive {archive_name}")
        src_dir = os.path.join(unpack_dir, "problems")
        if not os.path.exists(src_dir):
            src_dir = unpack_dir
        import_single(src_dir, retry_count)


def add_subparsers(subparsers, parents):
    import_many_parser = subparsers.add_parser("import_many",
                                                  help="Imports contest problems from contest's 'problems' dir",
                                                  parents=parents)
    import_many_parser.add_argument("archives_dir", help="Path to a directory with contest archives", type=str)
    import_many_parser.add_argument("--archives", nargs="+", help="Archive names to import, format: name.zip", type=str)
    import_many_parser.set_defaults(func=lambda options: import_many(options.archives_dir, options.archives, options.retry_count))


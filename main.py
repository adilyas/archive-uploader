import argparse
import sys

import import_single
import import_many


parser = argparse.ArgumentParser(
    description="Imports contest problems to polygon from a local archive(s)",
)

common_args = argparse.ArgumentParser(add_help=False)
common_args.add_argument("--retry-count", help="Max number of retries on an error", default=0, type=int)

subparsers = parser.add_subparsers(description="available commands")
subparsers.required = True

import_single.add_subparsers(subparsers, [common_args])
import_many.add_subparsers(subparsers, [common_args])


def main():
    options = parser.parse_args(sys.argv[1:])
    options.func(options)


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""Print derived page text; the input HTTP snapshot remains the source record."""
import argparse
from pathlib import Path

from dl_outcomes.page_payloads import embedded_page_text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    args = parser.parse_args()
    print(embedded_page_text(args.snapshot.read_bytes()))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
User Template Generator for JupyterHub

This script generates template files for batch user creation.
Supports CSV and Excel formats.

Usage:
    # Generate numbered users (student01, student02, ...)
    python generate_users_template.py --prefix student --count 50 --output users.csv

    # Generate with custom starting number
    python generate_users_template.py --prefix AUP --count 30 --start 1 --output aup_users.xlsx

    # Generate admin users
    python generate_users_template.py --prefix admin --count 5 --admin --output admins.csv

    # Custom list of usernames
    python generate_users_template.py --names alice bob charlie --output custom_users.csv
"""

import argparse
import sys

import pandas as pd


def generate_numbered_users(prefix: str, count: int, start: int = 1, admin: bool = False, digits: int = 2):
    """
    Generate numbered usernames.

    Args:
        prefix: Username prefix (e.g., 'student', 'AUP')
        count: Number of users to generate
        start: Starting number (default: 1)
        admin: Whether users should be admins (default: False)
        digits: Number of digits for padding (default: 2, e.g., 01, 02)

    Returns:
        List of user dictionaries
    """
    users = []
    for i in range(start, start + count):
        username = f"{prefix}{i:0{digits}d}"
        users.append({"username": username, "admin": admin})
    return users


def generate_custom_users(names: list, admin: bool = False):
    """
    Generate users from custom list of names.

    Args:
        names: List of usernames
        admin: Whether users should be admins (default: False)

    Returns:
        List of user dictionaries
    """
    users = []
    for name in names:
        users.append({"username": name.strip(), "admin": admin})
    return users


def save_users(users: list, filepath: str):
    """
    Save users to CSV or Excel file.

    Args:
        users: List of user dictionaries
        filepath: Output file path
    """
    try:
        df = pd.DataFrame(users)

        if filepath.endswith(".xlsx") or filepath.endswith(".xls"):
            df.to_excel(filepath, index=False)
        else:
            df.to_csv(filepath, index=False)

        print(f"✅ Generated {len(users)} users in {filepath}")
        print("\n📄 Preview:")
        print(df.head(10).to_string(index=False))

        if len(users) > 10:
            print(f"... and {len(users) - 10} more users")

    except Exception as e:
        print(f"❌ Error saving file: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Generate user template files for JupyterHub batch operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate 50 students (student01, student02, ...)
  python generate_users_template.py --prefix student --count 50 --output users.csv

  # Generate AUP users starting from AUP01
  python generate_users_template.py --prefix AUP --count 30 --start 1 --output aup_users.xlsx

  # Generate with 3-digit padding (student001, student002, ...)
  python generate_users_template.py --prefix student --count 100 --digits 3 --output users.csv

  # Generate admin users
  python generate_users_template.py --prefix admin --count 5 --admin --output admins.csv

  # Generate from custom list
  python generate_users_template.py --names alice bob charlie dave --output custom_users.csv

  # Combine multiple prefixes (useful for different groups)
  python generate_users_template.py --prefix TEST --count 20 --output test_users.csv
  python generate_users_template.py --prefix ROSCON --count 20 --output roscon_users.csv
        """,
    )

    # Generation mode
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--prefix", help="Username prefix for numbered generation")
    mode_group.add_argument("--names", nargs="+", help="Custom list of usernames")

    # Numbered generation options
    parser.add_argument("--count", type=int, help="Number of users to generate (required with --prefix)")

    parser.add_argument("--start", type=int, default=1, help="Starting number (default: 1)")

    parser.add_argument("--digits", type=int, default=2, help="Number of digits for padding (default: 2)")

    # Common options
    parser.add_argument("--admin", action="store_true", help="Mark users as admins")

    parser.add_argument("--output", "-o", required=True, help="Output file (CSV or Excel)")

    args = parser.parse_args()

    # Validate arguments
    if args.prefix and not args.count:
        parser.error("--count is required when using --prefix")

    # Generate users
    if args.prefix:
        users = generate_numbered_users(
            prefix=args.prefix, count=args.count, start=args.start, admin=args.admin, digits=args.digits
        )
    else:
        users = generate_custom_users(names=args.names, admin=args.admin)

    # Save to file
    save_users(users, args.output)


if __name__ == "__main__":
    main()

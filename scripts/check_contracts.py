"""Kiểm tra tính hợp lệ của các schema và ví dụ contracts."""
import json
import os
import sys

def check():
    print("Checking contracts...")
    for root, _, files in os.walk("contracts"):
        for f in files:
            if f.endswith(".json"):
                path = os.path.join(root, f)
                with open(path, "r", encoding="utf-8") as fp:
                    json.load(fp)
                print(f"  [OK] {path}")
    print("All contracts are valid JSON.")

if __name__ == "__main__":
    check()
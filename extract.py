#!/usr/bin/env python3
"""
E-vrit book library extractor.
Downloads all purchased books from e-vrit.co.il and saves them as decrypted EPUBs.
"""
import hashlib
import json
import base64
import zipfile
import io
import os
import sys
import time
import uuid
import requests
import re

EMAIL = os.environ.get("EVRIT_EMAIL", "")
PASSWORD = os.environ.get("EVRIT_PASSWORD", "")
DEVICE_SERIAL = os.environ.get("EVRIT_DEVICE_SERIAL", uuid.uuid4().hex)
API_BASE = "https://api.e-vrit.co.il/api"
OUTPUT_DIR = os.environ.get("EVRIT_OUTPUT_DIR", os.path.join(os.path.dirname(__file__), "books"))

AES_IV = bytes([0x72, 0x20, 0x40, 0x12, 0x1a, 0x03, 0xe9, 0x22,
                0xd9, 0xc1, 0x1b, 0x22, 0x00, 0x8d, 0x15, 0x04])
KEY_SUFFIX = "aJQecSAfdIArerEoQkVkDC8UNJADN8RiC8ACCn8RoSMdYjEx+SmHknsFST"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://read.e-vrit.co.il",
    "Referer": "https://read.e-vrit.co.il/",
}

_access_token = None


def log(msg):
    print(msg, flush=True)


def login():
    global _access_token
    body = {
        "login": {
            "DeviceSerialNum": DEVICE_SERIAL,
            "DeviceModel": "", "DeviceBrand": "Apple",
            "username": EMAIL, "password": PASSWORD,
        },
        "applicationType": "EvritWeb",
        "version": "6.0",
        "DeviceModuleID": "6",
        "deviceNickname": "Chrome macOS",
    }
    resp = requests.post(f"{API_BASE}/user/LoginUser", json=body, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("IsSuccess"):
        raise RuntimeError(f"Login failed: {data}")
    _access_token = data["Tokens"]["AccessToken"]
    log(f"Logged in (CustomerID: {data['Message']})")


def api_post(endpoint, extra_body=None):
    headers = {**HEADERS}
    if _access_token:
        headers["Authorization"] = _access_token
    body = {
        "login": {"DeviceSerialNum": DEVICE_SERIAL},
        "applicationType": "EvritWeb",
        "version": "6.0",
        "DeviceModuleID": "6",
    }
    if extra_body:
        body.update(extra_body)
    resp = requests.post(f"{API_BASE}{endpoint}", json=body, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json()


def get_purchased_books():
    data = api_post("/book/GetPurchasedBooks", {"excludeIDs": []})
    if not data.get("IsSuccess"):
        raise RuntimeError(f"GetPurchasedBooks failed: {data}")
    return data["ResponseData"]["ActiveBooks"]


def download_book(product_id):
    dl = api_post("/book/BookDownloadRequest", {"ProductID": product_id})
    if not dl.get("IsSuccess"):
        raise RuntimeError(f"BookDownloadRequest failed for {product_id}: {dl}")

    content_id = dl["ResponseData"]["ContentId"]
    guid = dl["ResponseData"]["GUID"]

    book = api_post("/book/GetBook", {"contentId": content_id, "GUID": guid})
    if not book.get("IsSuccess"):
        raise RuntimeError(f"GetBook failed for {product_id}: {book}")

    return book["ResponseData"]["Token"], book["ResponseData"]["Book"]


def derive_key(token):
    key_input = token + DEVICE_SERIAL.upper() + KEY_SUFFIX
    sha256_hex = hashlib.sha256(key_input.encode()).hexdigest()
    return sha256_hex[:32]


def decrypt_epub(book_b64, key_str):
    from Crypto.Cipher import AES

    epub_bytes = base64.b64decode(book_b64)
    key_bytes = key_str.encode("utf-8")  # 32 bytes = AES-256

    in_zip = zipfile.ZipFile(io.BytesIO(epub_bytes))
    out_buf = io.BytesIO()
    out_zip = zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED)

    for name in in_zip.namelist():
        raw = in_zip.read(name)
        info = in_zip.getinfo(name)

        if name.endswith((".xhtml", ".html")) and len(raw) > 0 and len(raw) % 16 == 0:
            cipher = AES.new(key_bytes, AES.MODE_CBC, AES_IV)
            decrypted = cipher.decrypt(raw)
            pad = decrypted[-1]
            if 0 < pad <= 16 and all(b == pad for b in decrypted[-pad:]):
                decrypted = decrypted[:-pad]
            out_zip.writestr(info, decrypted)
        else:
            out_zip.writestr(info, raw)

    out_zip.close()
    return out_buf.getvalue()


def sanitize_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    return name.strip()[:200]


def main():
    if not EMAIL or not PASSWORD:
        print("Error: set EVRIT_EMAIL and EVRIT_PASSWORD environment variables.")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    login()
    log("Fetching purchased books...")
    books = get_purchased_books()
    log(f"Found {len(books)} books in library.\n")

    for i, book in enumerate(books, 1):
        pid = book["ProductID"]
        title = book["Name"]
        authors = ", ".join(book.get("Authors", []))
        safe_name = sanitize_filename(f"{title} - {authors}" if authors else title)

        out_path = os.path.join(OUTPUT_DIR, f"{safe_name}.epub")
        if os.path.exists(out_path):
            log(f"[{i}/{len(books)}] Skipping '{title}' (already exists)")
            continue

        log(f"[{i}/{len(books)}] Downloading '{title}' (ID: {pid})...")

        try:
            token, book_b64 = download_book(pid)
            key_str = derive_key(token)
            epub_data = decrypt_epub(book_b64, key_str)

            with open(out_path, "wb") as f:
                f.write(epub_data)
            log(f"  -> Saved: {out_path} ({len(epub_data):,} bytes)")
        except Exception as e:
            log(f"  -> ERROR: {e}")

        time.sleep(1)

    log(f"\nDone! Books saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

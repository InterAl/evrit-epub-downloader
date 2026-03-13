# evrit-epub-downloader

Downloads all your purchased books from [e-vrit.co.il](https://www.e-vrit.co.il) as decrypted EPUBs.

This tool was created for educational purposes only. Check out [REVERSE-ENGINEERING.md](REVERSE-ENGINEERING.md) to understand how e-vrit tries to obfuscate and encrypt their books. Do not use it to pirate books.

## Prerequisites

- Python 3.8+
- `requests` and `pycryptodome` packages

```bash
pip install requests pycryptodome
```

## Usage

Set your e-vrit credentials as environment variables and run the script:

```bash
EVRIT_EMAIL="your@email.com" EVRIT_PASSWORD="yourpassword" python3 extract.py
```

Books are saved to the `books/` folder next to the script.

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `EVRIT_EMAIL` | *(required)* | Your e-vrit account email |
| `EVRIT_PASSWORD` | *(required)* | Your e-vrit account password |
| `EVRIT_OUTPUT_DIR` | `./books` | Where to save the EPUB files |
| `EVRIT_DEVICE_SERIAL` | auto-generated | Device fingerprint for API auth |

### Re-running

The script skips books that already exist in the output folder (matched by filename), so re-running it will only download new purchases.

## How it works

1. **Login** - authenticates with the e-vrit API and gets a JWT token. Without this token the API only returns free books.
2. **Fetch library** - calls `GetPurchasedBooks` to get the full book list.
3. **Download** - for each book, calls `BookDownloadRequest` then `GetBook` to get the encrypted EPUB data.
4. **Decrypt** - the XHTML content inside each EPUB is AES-256-CBC encrypted. The key is derived from the book's token, the device serial, and a constant baked into the app. The script decrypts the content and writes a normal EPUB.

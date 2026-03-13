# E-vrit Book Extractor

Downloads your entire [e-vrit.co.il](https://www.e-vrit.co.il) library as decrypted EPUB files — not just the free books, but every book on your account.

## Prerequisites

- Python 3.8+
- `requests` and `pycryptodome` packages

Install dependencies:

```bash
pip install requests pycryptodome
```

## Usage

Set your e-vrit credentials as environment variables and run the script:

```bash
EVRIT_EMAIL="your@email.com" EVRIT_PASSWORD="yourpassword" python3 extract.py
```

Books are saved to the `books/` folder next to the script.

### Optional environment variables

| Variable | Default | Description |
|---|---|---|
| `EVRIT_EMAIL` | *(required)* | Your e-vrit account email |
| `EVRIT_PASSWORD` | *(required)* | Your e-vrit account password |
| `EVRIT_OUTPUT_DIR` | `./books` | Where to save the EPUB files |
| `EVRIT_DEVICE_SERIAL` | auto-generated | Device fingerprint for API auth |

### Re-running

The script skips books that already exist in the output folder (matched by filename), so re-running it will only download new purchases.

## How it works

1. **Login** — authenticates with the e-vrit API using your credentials and obtains a JWT token. Without this token, the API only returns free books.
2. **Fetch library** — calls `GetPurchasedBooks` to list every book on your account.
3. **Download** — for each book, requests the encrypted EPUB data via `BookDownloadRequest` + `GetBook`.
4. **Decrypt** — each EPUB's XHTML content is AES-256-CBC encrypted. The script derives the decryption key from the book's token, the device serial, and an application constant, then decrypts and writes a standard EPUB.

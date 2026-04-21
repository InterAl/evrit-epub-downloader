# Reverse engineering the e-vrit DRM

Notes on how the e-vrit web reader's encryption and API auth were figured out.

## The obfuscated bundle

The reader at `read.e-vrit.co.il` is a React [SPA](https://en.wikipedia.org/wiki/Single-page_application). Its main bundle (`main.chunk.js`, ~15,000 lines) has all meaningful strings and property names obfuscated.

Strings are stored in a big array called `a7_0x1947` (~1350 entries). At startup, the array is rotated 107 times. A lookup function `a7_0x3698(x)` resolves indices to strings via `a7_0x1947[x - 0xf5]`. So instead of `obj["Token"]`, the code reads `obj[a7_0x3698(0x2f1)]`.

I wrote a Node.js script (`decode_strings.js`) that replays the array rotation and lookup function so I can resolve what each obfuscated reference actually points to.

## API authentication

Auth is device-based. Each client generates a `DeviceSerialNum` (a fingerprint hash) and registers it with the user's account via `/user/LoginUser`. The login returns [JWT](https://en.wikipedia.org/wiki/JSON_Web_Token) tokens (`AccessToken` and `RefreshToken`).

Without passing the JWT `AccessToken` as an `Authorization` header, the `GetPurchasedBooks` endpoint only returns free books. With the token, it returns the full library.

Credentials go inside a `login` object in the request body (not top-level fields or HTTP basic auth). Found this by tracing the request wrapper functions in the bundle (`_0xe1afb0`, `_0x259edd`, `_0x39dd5f`).

## Book download flow

Downloading a book is a two-step API process:

1. `BookDownloadRequest` with a `ProductID` returns a `ContentId` and `GUID`.
2. `GetBook` with the `ContentId` and `GUID` returns a `Token` and the [base64](https://en.wikipedia.org/wiki/Base64)-encoded encrypted EPUB.

The ownership check happens at step 2 - step 1 succeeds for any ProductID.

## Encryption

Each EPUB is a zip file where the XHTML chapter files are individually encrypted. Other files (CSS, images, metadata) are not encrypted.

The encryption is [AES](https://en.wikipedia.org/wiki/Advanced_Encryption_Standard)-256-[CBC](https://en.wikipedia.org/wiki/Block_cipher_mode_of_operation#CBC) with [PKCS7](https://en.wikipedia.org/wiki/PKCS_7) padding.

### IV ([Initialization Vector](https://en.wikipedia.org/wiki/Initialization_vector))

The IV is hardcoded in the decryption function (around line 12522 in the bundle) as an array literal:

```
[0x72, 0x20, 0x40, 0x12, 0x1a, 0x03, 0xe9, 0x22, 0xd9, 0xc1, 0x1b, 0x22, 0x00, 0x8d, 0x15, 0x04]
```

### Key derivation

The key derivation function (around line 14934) concatenates three values:

1. The `Token` returned by the `GetBook` API (unique per book download)
2. `DeviceSerialNum.toUpperCase()`
3. A constant suffix string

The suffix is split across three [webpack](https://en.wikipedia.org/wiki/Webpack) modules in the obfuscated code:

- Module 0x1f, property `f.one`: `"aJQecSAfdIArerEoQkV"`
- Module 0x1f, property `g.two`: `"kDC8UNJADN8RiC8ACCn"`
- Module 0x14, property `k`: `"8RoSMdYjEx+SmHknsFST"`

Concatenated: `aJQecSAfdIArerEoQkVkDC8UNJADN8RiC8ACCn8RoSMdYjEx+SmHknsFST`

The full concatenated string is hashed with [SHA-256](https://en.wikipedia.org/wiki/SHA-2), producing a 64-character hex string. Only the first 32 characters are used.

### Key encoding (the tricky part)

The 32-character hex string is **not** hex-decoded into 16 bytes (which would give AES-128). Instead, it's UTF-8 encoded directly, so the string `"a1b2c3d4..."` becomes 32 ASCII bytes. This gives a 32-byte key, which is why it's AES-256.

This was the hardest part to figure out. The hash function also wasn't named directly in the obfuscated code - MD5 was tried first and produced garbage. SHA256 turned out to be correct.

## Client-side libraries

The reader app uses `aes-js`, `crypto-js`, and `pkcs7` packages for client-side decryption, all bundled into `vendor.chunk.js`.

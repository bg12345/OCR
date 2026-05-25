# OCR API

Flask REST API for extracting details from Indian identity documents using OCR, QR decoding, MongoDB, and Amazon S3.

Supported documents:

- PAN card
- Aadhaar card
- Driving licence

Uploaded files are processed in memory with `BytesIO`, uploaded privately to S3, and returned in API responses as 10-minute presigned URLs. MongoDB stores the private S3 object URLs.

## Features

- Browser demo UI for uploading documents and viewing extracted JSON.
- OCR with Tesseract for English and Hindi text.
- PDF image extraction with Poppler.
- Aadhaar QR decoding with `pyaadhaar`.
- Image preprocessing with OpenCV, deskewing, denoising, and resizing.
- QR detection with ZBar/pyzbar.
- Existing-record checks for PAN, Aadhaar, and driving licence numbers.
- Private S3 uploads with Signature V4 presigned download URLs.
- Docker setup with native OCR dependencies included.

## Requirements

For Docker setup:

- Docker Desktop
- AWS S3 bucket
- MongoDB instance

For local setup without Docker:

- Python 3.14
- Tesseract OCR
- Poppler
- ZBar
- MongoDB access
- AWS credentials with S3 permissions

Docker is recommended because it installs Tesseract, Poppler, ZBar, and NLTK data inside the image.

## Environment Variables

Create a `.env` file in the project root:

```env
MONGO_URI=mongodb://user:password@host/database

AWS_ACCESS_KEY=your_access_key
AWS_ACCESS_SECRET=your_secret_key
AWS_REGION=ap-south-1
AWS_BUCKET_NAME=your_bucket_name

TESSERACT_PATH=/usr/bin/tesseract
POPPLER_PATH=/usr/bin
```

If you use temporary AWS credentials, also set:

```env
AWS_SESSION_TOKEN=your_session_token
```

The app also supports separate MongoDB variables if `MONGO_URI` is not set:

```env
MONGO_USERNAME=
MONGO_PASSWORD=
MONGO_HOST=
MONGO_DB=
```

## Docker Setup

Build and run from the project root:

```powershell
docker compose -f docker/docker-compose.yml up --build
```

The API will be available at:

```txt
http://localhost:5000
```

Open this URL in a browser to use the demo UI.

The Docker image includes:

- `tesseract-ocr`
- `tesseract-ocr-eng`
- `tesseract-ocr-hin`
- `poppler-utils`
- `libgl1`
- `libzbar0`
- NLTK `stopwords`
- NLTK `punkt_tab`

## Docker Image Design

The Dockerfile uses a multi-stage build to reduce final image size.

Builder stage:

- Installs build tools such as `build-essential` and `git`.
- Creates a Python virtual environment at `/opt/venv`.
- Installs Python dependencies.
- Downloads required NLTK data.
- Replaces `opencv-python` with `opencv-python-headless` during the Docker build because the API does not need OpenCV GUI features.

Runtime stage:

- Starts from a clean `python:3.14-slim` image.
- Copies only the prepared virtual environment and NLTK data from the builder stage.
- Installs only runtime native packages: Tesseract, Poppler, ZBar, OpenCV shared-library dependencies, and required shared libraries.
- Does not include compiler/build tooling in the final image.

After changes to the Dockerfile, rebuild without cache to see the real image size:

```powershell
docker compose -f docker/docker-compose.yml build --no-cache
docker images
```

## Local Setup

Create and activate a virtual environment:

```powershell
python -m venv venv
venv\Scripts\activate
```

Install dependencies:

```powershell
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

Download NLTK data:

```powershell
python -m nltk.downloader stopwords punkt_tab
```

Set local Windows paths in `.env`, for example:

```env
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
POPPLER_PATH=C:\poppler\Library\bin
```

Run the app:

```powershell
python run.py
```

## API Endpoints

### Health / Index

```http
GET /
```

Serves the browser demo UI for PAN, Aadhaar, and driving licence uploads.

### PAN OCR

```http
POST /pan_ocr
```

Form data:

- `file`: PAN image or PDF

Supported file types:

- `pdf`
- `jpeg`
- `jpg`
- `png`

### Driving Licence OCR

```http
POST /dl_ocr
```

Form data:

- `file`: driving licence image or PDF

### Aadhaar OCR

```http
POST /aadhaar_ocr
```

Form data:

- `front_file`: Aadhaar front image or PDF
- `back_file`: optional Aadhaar back image

If a two-page Aadhaar PDF is uploaded as `front_file`, the app attempts to process both pages.

## S3 URL Behavior

Files are uploaded to S3 without public ACLs.

MongoDB stores private object URLs such as:

```txt
https://bucket.s3.ap-south-1.amazonaws.com/pan/file.jpeg
```

API responses return temporary presigned URLs valid for 10 minutes.

Presigned URLs should contain Signature V4 query parameters such as:

```txt
X-Amz-Algorithm=AWS4-HMAC-SHA256
X-Amz-Expires=600
```

## Status Codes

- `200`: existing record found or basic API response
- `201`: new OCR record created
- `415`: unsupported or invalid file type
- `422`: file could not be processed/read
- `500`: unexpected server error

## Notes

- Do not commit `.env`; it contains AWS and database credentials.
- If S3 presigned URLs fail with `SignatureDoesNotMatch`, verify `AWS_ACCESS_KEY`, `AWS_ACCESS_SECRET`, `AWS_SESSION_TOKEN`, `AWS_REGION`, and system clock.
- OCR accuracy depends heavily on document quality, lighting, orientation, and scan resolution.

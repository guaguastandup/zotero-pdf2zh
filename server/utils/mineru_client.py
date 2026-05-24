import json
import os
import time
import urllib.error
import urllib.request
import zipfile

import requests


class MinerUError(RuntimeError):
    pass


class MinerUClient:
    """
    Minimal client for MinerU Precision Extract API.

    The flow is:
    1. request a pre-signed upload URL with /api/v4/file-urls/batch
    2. PUT the local file to that URL
    3. poll /api/v4/extract-results/batch/{batch_id}
    4. download and unzip full_zip_url
    """

    def __init__(
        self,
        token=None,
        base_url=None,
        model_version=None,
        language=None,
        timeout=None,
        poll_interval=None,
        request_timeout=None,
    ):
        self.token = os.getenv("MINERU_TOKEN", "") if token is None else str(token).strip()
        self.base_url = (
            os.getenv("MINERU_BASE_URL", "https://mineru.net")
            if base_url is None
            else str(base_url).strip()
        ).rstrip("/")
        self.model_version = (
            os.getenv("MINERU_MODEL_VERSION", "vlm")
            if model_version is None
            else str(model_version).strip()
        )
        self.language = (
            os.getenv("MINERU_LANGUAGE", "en")
            if language is None
            else str(language).strip()
        )
        timeout_value = timeout if timeout not in (None, "") else os.getenv("MINERU_TIMEOUT", "900")
        self.timeout = int(timeout_value)
        self.poll_interval = int(poll_interval or os.getenv("MINERU_POLL_INTERVAL", "5"))
        self.request_timeout = int(request_timeout or os.getenv("MINERU_REQUEST_TIMEOUT", "120"))

    def parse_pdf(self, pdf_path, output_dir, data_id=None):
        if not self.token:
            raise MinerUError("MinerU token is not configured")
        if not os.path.exists(pdf_path):
            raise MinerUError(f"PDF file not found: {pdf_path}")

        os.makedirs(output_dir, exist_ok=True)
        file_name = os.path.basename(pdf_path)
        batch_id, upload_url = self._apply_upload_url(file_name, data_id)
        self._upload_file(upload_url, pdf_path)
        result = self._wait_for_result(batch_id, file_name)
        zip_url = result.get("full_zip_url")
        if not zip_url:
            raise MinerUError("MinerU result does not include full_zip_url")

        zip_path = os.path.join(output_dir, "mineru_result.zip")
        self._download_file(zip_url, zip_path)
        self._extract_zip(zip_path, output_dir)
        result["batch_id"] = batch_id
        result["zip_path"] = zip_path
        result["output_dir"] = output_dir
        return result

    def _headers(self, content_type=True):
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "*/*",
        }
        if content_type:
            headers["Content-Type"] = "application/json"
        return headers

    def _apply_upload_url(self, file_name, data_id):
        url = f"{self.base_url}/api/v4/file-urls/batch"
        payload = {
            "files": [
                {
                    "name": file_name,
                    "data_id": data_id or os.path.splitext(file_name)[0],
                    "is_ocr": False,
                }
            ],
            "model_version": self.model_version,
            "language": self.language,
            "enable_formula": True,
            "enable_table": True,
        }
        result = self._request_json("POST", url, payload, self._headers())
        if result.get("code") != 0:
            raise MinerUError(f"MinerU upload URL request failed: {result.get('msg') or result}")

        data = result.get("data") or {}
        batch_id = data.get("batch_id")
        urls = data.get("file_urls") or []
        if not batch_id or not urls:
            raise MinerUError(f"MinerU upload URL response missing batch_id/file_urls: {result}")
        return batch_id, urls[0]

    def _upload_file(self, upload_url, pdf_path):
        last_error = None
        for attempt in range(1, 4):
            try:
                with open(pdf_path, "rb") as f:
                    response = requests.put(upload_url, data=f, timeout=self.request_timeout)
                if response.status_code in (200, 201, 204):
                    return
                last_error = f"HTTP {response.status_code} {response.text[:500]}"
            except requests.RequestException as e:
                last_error = str(e)
            if attempt < 3:
                time.sleep(2 * attempt)
        raise MinerUError(f"MinerU file upload failed after 3 attempts: {last_error}")

    def _wait_for_result(self, batch_id, file_name):
        url = f"{self.base_url}/api/v4/extract-results/batch/{batch_id}"
        deadline = time.time() + self.timeout
        last_state = None
        while time.time() < deadline:
            result = self._request_json("GET", url, None, self._headers(content_type=False))
            if result.get("code") != 0:
                raise MinerUError(f"MinerU result polling failed: {result.get('msg') or result}")

            data = result.get("data") or {}
            extract_results = data.get("extract_result") or []
            item = self._select_result(extract_results, file_name)
            if item:
                state = item.get("state")
                last_state = state
                if state == "done":
                    return item
                if state == "failed":
                    raise MinerUError(item.get("err_msg") or "MinerU extraction failed")
            time.sleep(self.poll_interval)

        raise MinerUError(f"MinerU extraction timed out after {self.timeout}s, last_state={last_state}")

    @staticmethod
    def _select_result(extract_results, file_name):
        if not extract_results:
            return None
        for item in extract_results:
            if item.get("file_name") == file_name:
                return item
        return extract_results[0]

    def _request_json(self, method, url, payload, headers):
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.request_timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                if resp.status < 200 or resp.status >= 300:
                    raise MinerUError(f"HTTP {resp.status}: {body}")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise MinerUError(f"HTTP {e.code}: {body}") from e
        except urllib.error.URLError as e:
            raise MinerUError(f"Network error: {e}") from e
        except json.JSONDecodeError as e:
            raise MinerUError(f"Invalid JSON response from MinerU: {e}") from e

    def _download_file(self, url, output_path):
        last_error = None
        for attempt in range(1, 4):
            try:
                with requests.get(url, stream=True, timeout=self.request_timeout) as response:
                    if response.status_code < 200 or response.status_code >= 300:
                        last_error = f"HTTP {response.status_code} {response.text[:500]}"
                    else:
                        with open(output_path, "wb") as f:
                            for chunk in response.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    f.write(chunk)
                        return
            except requests.RequestException as e:
                last_error = str(e)
            if attempt < 3:
                time.sleep(2 * attempt)
        raise MinerUError(f"MinerU result download failed after 3 attempts: {last_error}")

    @staticmethod
    def _extract_zip(zip_path, output_dir):
        with zipfile.ZipFile(zip_path, "r") as zf:
            base = os.path.abspath(output_dir)
            for member in zf.infolist():
                target = os.path.abspath(os.path.join(output_dir, member.filename))
                if os.path.commonpath([base, target]) != base:
                    raise MinerUError(f"Unsafe zip member path: {member.filename}")
            zf.extractall(output_dir)

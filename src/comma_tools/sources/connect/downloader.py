"""
Log file downloader for comma connect.

Handles streaming downloads with resume capability, atomic writes,
and idempotent behavior for comma log files.
"""

import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .client import ConnectClient


class DownloadReport:
    """Report of download operation results."""

    def __init__(self):
        self.written_paths: List[str] = []
        self.skipped_paths: List[str] = []
        self.failed_paths: List[str] = []
        self.total_bytes: int = 0
        self.skipped_bytes: int = 0

    def add_written(self, path: str, size: int) -> None:
        """Record a successfully written file."""
        self.written_paths.append(path)
        self.total_bytes += size

    def add_skipped(self, path: str, size: int) -> None:
        """Record a skipped file (already exists)."""
        self.skipped_paths.append(path)
        self.skipped_bytes += size

    def add_failed(self, path: str) -> None:
        """Record a failed download."""
        self.failed_paths.append(path)

    @property
    def success_count(self) -> int:
        return len(self.written_paths)

    @property
    def skip_count(self) -> int:
        return len(self.skipped_paths)

    @property
    def failure_count(self) -> int:
        return len(self.failed_paths)

    @property
    def total_count(self) -> int:
        return self.success_count + self.skip_count + self.failure_count


class LogDownloader:
    """
    Downloads log files from comma connect with resume and idempotency.

    Implements atomic writes, resume capability, and stable file layout
    as specified in the technical design.
    """

    def __init__(self, client: ConnectClient, parallel: int = 4):
        self.client = client
        self.parallel = parallel

    def _get_file_size(self, url: str) -> Optional[int]:
        """Get file size from URL via HEAD request."""
        try:
            request = Request(url, method="HEAD")
            with urlopen(request, timeout=10) as response:
                content_length = response.headers.get("Content-Length")
                return int(content_length) if content_length else None
        except (HTTPError, URLError, ValueError):
            return None

    def _download_file(self, url: str, dest_path: Path, resume: bool = True) -> bool:
        """
        Download a single file with resume capability.

        Args:
            url: Signed URL to download from
            dest_path: Final destination path
            resume: Whether to resume partial downloads

        Returns:
            True if download succeeded, False otherwise
        """
        temp_path = dest_path.with_suffix(dest_path.suffix + ".part")

        if dest_path.exists():
            expected_size = self._get_file_size(url)
            if expected_size and dest_path.stat().st_size == expected_size:
                return True  # File already complete

        start_byte = 0
        if resume and temp_path.exists():
            start_byte = temp_path.stat().st_size

        try:
            request = Request(url)
            if start_byte > 0:
                request.add_header("Range", f"bytes={start_byte}-")

            dest_path.parent.mkdir(parents=True, exist_ok=True)

            with urlopen(request, timeout=30) as response:
                mode = "ab" if start_byte > 0 else "wb"
                with open(temp_path, mode) as f:
                    shutil.copyfileobj(response, f, length=64 * 1024)

            temp_path.rename(dest_path)
            return True

        except (HTTPError, URLError, OSError) as e:
            if temp_path.exists():
                temp_path.unlink()
            print(f"Download failed for {dest_path.name}: {e}")
            return False

    def _build_file_plan(
        self, route_name: str, dest_root: Path, file_types: Dict[str, bool]
    ) -> List[Tuple[str, Path]]:
        """
        Build download plan mapping URLs to destination paths.

        Args:
            route_name: Canonical route name
            dest_root: Root destination directory
            file_types: Dictionary of file type flags

        Returns:
            List of (url, dest_path) tuples
        """
        dongle_id, route_timestamp = route_name.split("|")

        try:
            files = self.client.route_files(route_name)
        except Exception as e:
            raise RuntimeError(f"Failed to get file list for {route_name}: {e}") from e

        plan = []

        type_mapping = {
            "logs": files.get("logs", []),
            "qlogs": files.get("qlogs", []),
            "cameras": files.get("cameras", []),
            "dcameras": files.get("dcameras", []),
            "ecameras": files.get("ecameras", []),
            "qcameras": files.get("qcameras", []),
        }

        for file_type, urls in type_mapping.items():
            if not file_types.get(file_type, False):
                continue

            for url in urls:
                url_parts = url.rstrip("/").split("/")
                if len(url_parts) >= 2:
                    segment = url_parts[-2]
                    filename = url_parts[-1]

                    dest_path = dest_root / dongle_id / route_timestamp / segment / filename
                    plan.append((url, dest_path))

        return plan

    def download_route(
        self, route_name: str, dest_root: Path, file_types: Dict[str, bool], resume: bool = True
    ) -> DownloadReport:
        """
        Download all requested files for a route.

        Args:
            route_name: Canonical route name
            dest_root: Root destination directory
            file_types: Dictionary specifying which file types to download
            resume: Whether to resume partial downloads

        Returns:
            DownloadReport with results
        """
        report = DownloadReport()

        try:
            plan = self._build_file_plan(route_name, dest_root, file_types)
        except Exception as e:
            print(f"Failed to build download plan: {e}")
            return report

        if not plan:
            print("No files to download based on selected file types")
            return report

        print(f"Downloading {len(plan)} files for route {route_name}")

        with ThreadPoolExecutor(max_workers=self.parallel) as executor:
            future_to_info = {
                executor.submit(self._download_file, url, dest_path, resume): (url, dest_path)
                for url, dest_path in plan
            }

            for future in as_completed(future_to_info):
                url, dest_path = future_to_info[future]

                try:
                    success = future.result()
                    if success:
                        if dest_path.exists():
                            size = dest_path.stat().st_size
                            if size > 0:
                                report.add_written(str(dest_path), size)
                            else:
                                report.add_skipped(str(dest_path), 0)
                        else:
                            report.add_failed(str(dest_path))
                    else:
                        report.add_failed(str(dest_path))
                except Exception as e:
                    print(f"Download task failed: {e}")
                    report.add_failed(str(dest_path))

        self._write_route_index(route_name, dest_root, report)

        return report

    def _write_route_index(self, route_name: str, dest_root: Path, report: DownloadReport) -> None:
        """Write optional index.json file for the route."""
        dongle_id, route_timestamp = route_name.split("|")
        route_dir = dest_root / dongle_id / route_timestamp

        if not route_dir.exists():
            return

        index_data = {
            "route_name": route_name,
            "dongle_id": dongle_id,
            "route_timestamp": route_timestamp,
            "download_summary": {
                "written_files": len(report.written_paths),
                "skipped_files": len(report.skipped_paths),
                "failed_files": len(report.failed_paths),
                "total_bytes": report.total_bytes,
            },
            "files": [],
        }

        for file_path in report.written_paths + report.skipped_paths:
            path_obj = Path(file_path)
            if path_obj.exists():
                rel_path = path_obj.relative_to(route_dir)
                index_data["files"].append(
                    {
                        "path": str(rel_path),
                        "size": path_obj.stat().st_size,
                    }
                )

        index_file = route_dir / "index.json"
        try:
            with open(index_file, "w") as f:
                json.dump(index_data, f, indent=2)
        except OSError:
            pass  # Index file is optional

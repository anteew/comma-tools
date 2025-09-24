"""
Command-line interface for comma connect downloader.

Provides the comma-connect-dl CLI tool for downloading log files
from comma connect with comprehensive options and error handling.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from .auth import load_auth
from .client import ConnectClient
from .resolver import RouteResolver
from .downloader import LogDownloader, DownloadReport


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for comma-connect-dl CLI."""
    parser = argparse.ArgumentParser(
        prog='comma-connect-dl',
        description='Download log files from comma connect',
        epilog="""
Examples:
  comma-connect-dl --url https://connect.comma.ai/dcb4c2e18426be55/00000008--0696c823fa --logs

  comma-connect-dl --route dcb4c2e18426be55|2024-04-19--12-33-20 --logs --cameras

  comma-connect-dl --url <connect-url> --logs --dest ./my-logs --parallel 8

For more information, see: https://github.com/commaai/comma-api
Note: Drives are retained 3 days (or 1 year with comma prime)
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '--route', 
        help='Canonical route name (dongle_id|YYYY-MM-DD--HH-MM-SS)'
    )
    input_group.add_argument(
        '--url', 
        help='Connect URL (https://connect.comma.ai/dongle/slug)'
    )
    
    parser.add_argument('--logs', action='store_true', help='Download rlog.bz2 files')
    parser.add_argument('--qlogs', action='store_true', help='Download qlog.bz2 files')
    parser.add_argument('--cameras', action='store_true', help='Download fcamera.hevc files')
    parser.add_argument('--dcameras', action='store_true', help='Download dcamera.hevc files')
    parser.add_argument('--ecameras', action='store_true', help='Download ecamera.hevc files')
    parser.add_argument('--qcameras', action='store_true', help='Download qcamera.ts files')
    
    parser.add_argument(
        '--dest', 
        type=Path,
        default=Path.home() / '.cache' / 'comma-tools' / 'downloads',
        help='Destination directory (default: ~/.cache/comma-tools/downloads)'
    )
    parser.add_argument(
        '--parallel', 
        type=int, 
        default=4,
        help='Number of parallel downloads (default: 4)'
    )
    parser.add_argument('--no-resume', action='store_true', help='Disable resume of partial downloads')
    
    parser.add_argument(
        '--since', 
        help='Search start date (YYYY-MM-DD) for connect URL resolution'
    )
    parser.add_argument(
        '--until', 
        help='Search end date (YYYY-MM-DD) for connect URL resolution'
    )
    parser.add_argument(
        '--days', 
        type=int, 
        default=7,
        help='Number of days to search backwards for connect URLs (default: 7)'
    )
    
    parser.add_argument('--print-files', action='store_true', help='Print downloaded file paths')
    parser.add_argument('--json', action='store_true', help='Output results as JSON')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be downloaded without downloading')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    return parser


def validate_args(args: argparse.Namespace) -> None:
    """Validate command line arguments."""
    file_types = ['logs', 'qlogs', 'cameras', 'dcameras', 'ecameras', 'qcameras']
    if not any(getattr(args, ft) for ft in file_types):
        raise ValueError(
            "At least one file type must be selected. "
            "Use --logs, --qlogs, --cameras, --dcameras, --ecameras, or --qcameras"
        )
    
    if args.since:
        try:
            datetime.strptime(args.since, '%Y-%m-%d')
        except ValueError:
            raise ValueError(f"Invalid --since date format: {args.since}. Use YYYY-MM-DD")
    
    if args.until:
        try:
            datetime.strptime(args.until, '%Y-%m-%d')
        except ValueError:
            raise ValueError(f"Invalid --until date format: {args.until}. Use YYYY-MM-DD")


def calculate_search_days(args: argparse.Namespace) -> int:
    """Calculate search window in days for connect URL resolution."""
    if args.since and args.until:
        since_date = datetime.strptime(args.since, '%Y-%m-%d')
        until_date = datetime.strptime(args.until, '%Y-%m-%d')
        return (until_date - since_date).days
    elif args.since:
        since_date = datetime.strptime(args.since, '%Y-%m-%d')
        now = datetime.now()
        return (now - since_date).days
    else:
        return args.days


def format_bytes(size: int) -> str:
    """Format byte size in human readable format."""
    size_float = float(size)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_float < 1024:
            return f"{size_float:.1f} {unit}"
        size_float /= 1024
    return f"{size_float:.1f} TB"


def print_report(report: DownloadReport, args: argparse.Namespace) -> None:
    """Print download report in requested format."""
    if args.json:
        result = {
            'success': True,
            'written_files': len(report.written_paths),
            'skipped_files': len(report.skipped_paths),
            'failed_files': len(report.failed_paths),
            'total_bytes': report.total_bytes,
            'skipped_bytes': report.skipped_bytes,
            'paths': {
                'written': report.written_paths,
                'skipped': report.skipped_paths,
                'failed': report.failed_paths,
            }
        }
        print(json.dumps(result, indent=2))
    else:
        print(f"\nDownload Summary:")
        print(f"  Written: {len(report.written_paths)} files ({format_bytes(report.total_bytes)})")
        print(f"  Skipped: {len(report.skipped_paths)} files ({format_bytes(report.skipped_bytes)})")
        if report.failed_paths:
            print(f"  Failed:  {len(report.failed_paths)} files")
        
        if args.print_files and report.written_paths:
            print(f"\nDownloaded files:")
            for path in report.written_paths:
                print(f"  {path}")


def main() -> int:
    """Main entry point for comma-connect-dl CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    try:
        validate_args(args)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    try:
        load_auth()
        if args.verbose:
            print("Authentication: JWT token found")
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    client = ConnectClient()
    resolver = RouteResolver(client)
    downloader = LogDownloader(client, parallel=args.parallel)
    
    try:
        input_str = args.route if args.route else args.url
        search_days = calculate_search_days(args)
        canonical_route = resolver.resolve(input_str, search_days)
        
        if args.verbose:
            print(f"Resolved route: {canonical_route}")
            
    except Exception as e:
        print(f"Error resolving route: {e}", file=sys.stderr)
        return 1
    
    file_types = {
        'logs': args.logs,
        'qlogs': args.qlogs,
        'cameras': args.cameras,
        'dcameras': args.dcameras,
        'ecameras': args.ecameras,
        'qcameras': args.qcameras,
    }
    
    if args.dry_run:
        print(f"Would download from route: {canonical_route}")
        print(f"File types: {[ft for ft, enabled in file_types.items() if enabled]}")
        print(f"Destination: {args.dest}")
        return 0
    
    try:
        report = downloader.download_route(
            canonical_route, 
            args.dest, 
            file_types,
            resume=not args.no_resume
        )
        
        print_report(report, args)
        
        if report.failure_count > 0:
            return 2  # Partial failure
        else:
            return 0  # Success
            
    except Exception as e:
        if args.verbose:
            import traceback
            traceback.print_exc()
        else:
            print(f"Error during download: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

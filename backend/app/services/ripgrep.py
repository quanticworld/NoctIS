"""Ripgrep service for executing searches"""
import asyncio
import re
import time
from pathlib import Path
from typing import AsyncGenerator, Optional
from ..models import SearchRequest, SearchMatch, SearchProgress, SearchResult, RegexTemplate


class RipgrepService:
    """Service for executing ripgrep searches with progress tracking"""

    @staticmethod
    def build_pattern(request: SearchRequest) -> str:
        """Build regex pattern from template and parameters"""
        if request.template == RegexTemplate.CUSTOM:
            if not request.pattern:
                raise ValueError("Custom template requires pattern parameter")
            return request.pattern

        elif request.template == RegexTemplate.NAME_SEARCH:
            if not request.first_name or not request.last_name:
                raise ValueError("Name search requires first_name and last_name")
            # Don't escape to allow regex patterns (e.g., .*, \d+, etc.)
            # Users can input regex directly for flexible matching
            first = request.first_name
            last = request.last_name
            return f"({first}.*{last}|{last}.*{first})"

        elif request.template == RegexTemplate.EMAIL:
            return r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"

        elif request.template == RegexTemplate.PHONE_FR:
            return r"0[1-9][\s.-]?(?:\d{2}[\s.-]?){4}"

        elif request.template == RegexTemplate.IP_ADDRESS:
            return r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"

        else:
            raise ValueError(f"Unknown template: {request.template}")

    @staticmethod
    def build_rg_command(pattern: str, request: SearchRequest) -> list[str]:
        """Build ripgrep command with all parameters"""
        cmd = [
            "rg",
            pattern,
            "--json",  # Output in JSON format for parsing
            f"--threads={request.threads}",
            f"--max-filesize={request.max_filesize}",
        ]

        if request.case_insensitive:
            cmd.append("-i")

        # Add file type filters
        if request.file_types:
            for ft in request.file_types:
                cmd.append(f"--type={ft}")

        if request.exclude_types:
            for ft in request.exclude_types:
                cmd.append(f"--type-not={ft}")

        # Add search path
        cmd.append(request.search_path)

        return cmd

    @staticmethod
    async def count_files(request: SearchRequest) -> int:
        """
        Quickly count files that will be searched (without reading content)
        """
        cmd = ["rg", "--files", request.search_path]

        # Add file type filters
        if request.file_types:
            for ft in request.file_types:
                cmd.append(f"--type={ft}")

        if request.exclude_types:
            for ft in request.exclude_types:
                cmd.append(f"--type-not={ft}")

        cmd.append(f"--max-filesize={request.max_filesize}")

        # Run file listing
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        count = 0
        async for line in process.stdout:
            count += 1

        await process.wait()
        return count

    @staticmethod
    async def execute_search(
        request: SearchRequest,
        cancel_event: asyncio.Event = None,
        websocket = None,
        manager = None,
    ) -> AsyncGenerator[SearchProgress | SearchResult, None]:
        """
        Execute ripgrep search and yield progress/results in real-time

        Args:
            request: Search parameters
            cancel_event: Optional event to signal cancellation
        """
        pattern = RipgrepService.build_pattern(request)
        cmd = RipgrepService.build_rg_command(pattern, request)

        start_time = time.time()
        files_scanned = 0
        matches_found = 0
        current_file = ""
        last_progress_time = start_time

        # Send initial progress to show search has started
        yield SearchProgress(
            files_scanned=0,
            current_file="Starting search...",
            matches_found=0,
            speed=0,
        )

        # Skip file counting - on large datasets it's too slow
        # We'll just show files_scanned without a total
        total_files = None

        # Start ripgrep process
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Store process PID in manager so it can be killed on cancel
        if manager and websocket:
            manager.process_pids[websocket] = process.pid
            print(f"[RIPGREP] Started process {process.pid}, stored in manager")

        try:
            # Read output line by line
            lines_processed = 0
            async for line in process.stdout:
                # Check if cancel was requested
                if cancel_event and cancel_event.is_set():
                    print(f"[RIPGREP] Cancel event detected! Killing process {process.pid}")
                    if process.returncode is None:
                        import signal
                        import os
                        try:
                            os.kill(process.pid, signal.SIGKILL)
                            print(f"[RIPGREP] Sent SIGKILL to process {process.pid}")
                        except ProcessLookupError:
                            print(f"[RIPGREP] Process {process.pid} already dead")
                            pass
                    break

                lines_processed += 1

                try:
                    import json

                    data = json.loads(line.decode())

                    # Handle different message types from rg --json
                    msg_type = data.get("type")

                    if msg_type == "begin":
                        # File search beginning
                        path_data = data.get("data", {}).get("path", {})
                        current_file = path_data.get("text", "")
                        files_scanned += 1

                    elif msg_type == "match":
                        # Match found
                        match_data = data.get("data", {})
                        path_data = match_data.get("path", {})
                        line_number = match_data.get("line_number", 0)
                        lines = match_data.get("lines", {})
                        submatches = match_data.get("submatches", [])

                        file_path = path_data.get("text", "")
                        line_content = lines.get("text", "").rstrip("\n")

                        # Get first submatch position
                        match_start = 0
                        match_end = 0
                        if submatches:
                            match_start = submatches[0].get("start", 0)
                            match_end = submatches[0].get("end", 0)

                        matches_found += 1

                        yield SearchResult(
                            match=SearchMatch(
                                file_path=file_path,
                                line_number=line_number,
                                line_content=line_content,
                                match_start=match_start,
                                match_end=match_end,
                            )
                        )

                    # Send periodic progress updates (every 0.5s)
                    current_time = time.time()
                    if current_time - last_progress_time >= 0.5:
                        elapsed = current_time - start_time
                        # Calculate speed based on files_scanned OR lines_processed as fallback
                        if files_scanned > 0:
                            speed = files_scanned / elapsed if elapsed > 0 else 0
                        else:
                            # Fallback: show activity even if no "begin" messages
                            speed = lines_processed / elapsed if elapsed > 0 else 0

                        # Calculate ETA (only if we know total)
                        eta = None
                        if speed > 0 and total_files and total_files > 0:
                            remaining = total_files - files_scanned
                            eta = remaining / speed

                        # Update current_file to show activity
                        if not current_file:
                            current_file = f"Processing... ({lines_processed} messages)"

                        yield SearchProgress(
                            files_scanned=files_scanned,
                            total_files=total_files,
                            current_file=current_file,
                            matches_found=matches_found,
                            speed=speed,
                            eta_seconds=eta,
                        )
                        last_progress_time = current_time

                except json.JSONDecodeError:
                    # Skip invalid JSON lines
                    continue

            # Wait for process to complete (or kill if cancel was requested)
            if cancel_event and cancel_event.is_set():
                print(f"[RIPGREP] Cancel event set after loop, killing process {process.pid}")
                if process.returncode is None:
                    import signal
                    import os
                    try:
                        os.kill(process.pid, signal.SIGKILL)
                        print(f"[RIPGREP] Sent SIGKILL to process {process.pid}")
                    except ProcessLookupError:
                        pass

            await process.wait()

            # Send final progress
            elapsed = time.time() - start_time
            speed = files_scanned / elapsed if elapsed > 0 else 0

            yield SearchProgress(
                files_scanned=files_scanned,
                total_files=total_files,
                current_file="",
                matches_found=matches_found,
                speed=speed,
                eta_seconds=0,
            )

        except asyncio.CancelledError:
            # Task was cancelled, kill the ripgrep process immediately
            print(f"[RIPGREP] CancelledError caught! Process PID: {process.pid}, returncode: {process.returncode}")
            if process.returncode is None:
                try:
                    print(f"[RIPGREP] Killing process {process.pid}")
                    process.kill()  # SIGKILL for immediate termination
                    await asyncio.wait_for(process.wait(), timeout=1.0)
                    print(f"[RIPGREP] Process {process.pid} killed successfully")
                except asyncio.TimeoutError:
                    # Process didn't die, force kill
                    print(f"[RIPGREP] Timeout, force killing {process.pid}")
                    import signal
                    try:
                        import os
                        os.kill(process.pid, signal.SIGKILL)
                        print(f"[RIPGREP] Force killed {process.pid}")
                    except ProcessLookupError:
                        print(f"[RIPGREP] Process {process.pid} already dead")
                        pass  # Already dead
            raise
        finally:
            # Clean up PID from manager
            if manager and websocket and websocket in manager.process_pids:
                del manager.process_pids[websocket]
                print(f"[RIPGREP] Removed PID {process.pid} from manager")

            # Ensure process is cleaned up (belt and suspenders)
            if process.returncode is None:
                try:
                    process.terminate()  # Try graceful first
                    await asyncio.wait_for(process.wait(), timeout=0.5)
                except asyncio.TimeoutError:
                    # Timeout, force kill
                    process.kill()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=1.0)
                    except asyncio.TimeoutError:
                        # Last resort: send SIGKILL directly
                        import signal
                        import os
                        try:
                            os.kill(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass  # Already dead

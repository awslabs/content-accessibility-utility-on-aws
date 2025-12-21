# Copyright 2025 Amazon.com, Inc. or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""
Docker client utility for running containerized tools.

This module provides functionality for executing Docker containers,
particularly for tools like pdf2htmlEX that are distributed as Docker images.
"""

import os
import platform
import subprocess
import shutil
from dataclasses import dataclass
from typing import Dict, List, Optional

from content_accessibility_utility_on_aws.utils.logging_helper import setup_logger

logger = setup_logger(__name__)


@dataclass
class DockerRunResult:
    """Result from running a Docker container."""

    return_code: int
    """Exit code from the container."""

    stdout: str
    """Standard output from the container."""

    stderr: str
    """Standard error from the container."""

    @property
    def success(self) -> bool:
        """Return True if the container exited successfully."""
        return self.return_code == 0


class DockerClient:
    """
    Utility class for running Docker containers.

    Provides methods for checking Docker availability, pulling images,
    and executing containers with volume mounts.
    """

    def __init__(self):
        """Initialize the Docker client."""
        self._docker_path: Optional[str] = None
        self._is_apple_silicon: Optional[bool] = None

    @property
    def docker_path(self) -> Optional[str]:
        """Get the path to the Docker executable."""
        if self._docker_path is None:
            self._docker_path = shutil.which("docker")
        return self._docker_path

    @property
    def is_apple_silicon(self) -> bool:
        """Check if running on Apple Silicon (M1/M2/M3)."""
        if self._is_apple_silicon is None:
            self._is_apple_silicon = (
                platform.system() == "Darwin" and platform.machine() == "arm64"
            )
        return self._is_apple_silicon

    def is_available(self) -> bool:
        """
        Check if Docker is installed and running.

        Returns:
            True if Docker is available and the daemon is running.
        """
        if not self.docker_path:
            logger.debug("Docker executable not found in PATH")
            return False

        try:
            result = subprocess.run(
                [self.docker_path, "info"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.debug(f"Docker daemon not running: {result.stderr}")
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.debug("Docker info command timed out")
            return False
        except Exception as e:
            logger.debug(f"Error checking Docker availability: {e}")
            return False

    def image_exists(self, image: str) -> bool:
        """
        Check if a Docker image exists locally.

        Args:
            image: Docker image name with optional tag.

        Returns:
            True if the image exists locally.
        """
        if not self.docker_path:
            return False

        try:
            result = subprocess.run(
                [self.docker_path, "image", "inspect", image],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0
        except Exception as e:
            logger.debug(f"Error checking image existence: {e}")
            return False

    def pull_image(self, image: str, platform_override: Optional[str] = None) -> bool:
        """
        Pull a Docker image from the registry.

        Args:
            image: Docker image name with optional tag.
            platform_override: Optional platform to pull for (e.g., 'linux/amd64').

        Returns:
            True if the image was pulled successfully.
        """
        if not self.docker_path:
            return False

        cmd = [self.docker_path, "pull"]

        # Add platform flag for Apple Silicon if needed
        if platform_override:
            cmd.extend(["--platform", platform_override])
        elif self.is_apple_silicon:
            cmd.extend(["--platform", "linux/amd64"])

        cmd.append(image)

        logger.info(f"Pulling Docker image: {image}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minutes for large images
            )
            if result.returncode != 0:
                logger.error(f"Failed to pull image: {result.stderr}")
                return False
            logger.info(f"Successfully pulled image: {image}")
            return True
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout pulling image: {image}")
            return False
        except Exception as e:
            logger.error(f"Error pulling image: {e}")
            return False

    def run_container(
        self,
        image: str,
        command: List[str],
        volumes: Optional[Dict[str, Dict[str, str]]] = None,
        working_dir: Optional[str] = None,
        timeout: int = 300,
        platform_override: Optional[str] = None,
        user: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
    ) -> DockerRunResult:
        """
        Run a Docker container with the specified configuration.

        Args:
            image: Docker image name with optional tag.
            command: Command and arguments to run in the container.
            volumes: Volume mounts as {host_path: {"bind": container_path, "mode": "rw"}}.
            working_dir: Working directory inside the container.
            timeout: Maximum time in seconds to wait for the container.
            platform_override: Optional platform to run on (e.g., 'linux/amd64').
            user: Optional user to run as inside the container.
            environment: Optional environment variables to set.

        Returns:
            DockerRunResult with exit code, stdout, and stderr.

        Raises:
            DockerError: If Docker is not available or the container fails to start.
        """
        from content_accessibility_utility_on_aws.utils.logging_helper import DockerError

        if not self.docker_path:
            raise DockerError("Docker is not available")

        cmd = [self.docker_path, "run", "--rm"]

        # Add platform flag for Apple Silicon if needed
        if platform_override:
            cmd.extend(["--platform", platform_override])
        elif self.is_apple_silicon:
            cmd.extend(["--platform", "linux/amd64"])

        # Add volume mounts
        if volumes:
            for host_path, mount_config in volumes.items():
                container_path = mount_config.get("bind", host_path)
                mode = mount_config.get("mode", "rw")
                cmd.extend(["-v", f"{host_path}:{container_path}:{mode}"])

        # Add working directory
        if working_dir:
            cmd.extend(["-w", working_dir])

        # Add user
        if user:
            cmd.extend(["-u", user])

        # Add environment variables
        if environment:
            for key, value in environment.items():
                cmd.extend(["-e", f"{key}={value}"])

        # Add image and command
        cmd.append(image)
        cmd.extend(command)

        logger.debug(f"Running Docker command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return DockerRunResult(
                return_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        except subprocess.TimeoutExpired as e:
            logger.error(f"Docker container timed out after {timeout} seconds")
            return DockerRunResult(
                return_code=-1,
                stdout=e.stdout.decode() if e.stdout else "",
                stderr=f"Container timed out after {timeout} seconds",
            )
        except Exception as e:
            logger.error(f"Error running Docker container: {e}")
            return DockerRunResult(
                return_code=-1,
                stdout="",
                stderr=str(e),
            )

    def get_version(self) -> Optional[str]:
        """
        Get the Docker version.

        Returns:
            Version string or None if Docker is not available.
        """
        if not self.docker_path:
            return None

        try:
            result = subprocess.run(
                [self.docker_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception:
            return None

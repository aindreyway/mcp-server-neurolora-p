"""Storage management functionality.

This module handles the storage structure and symlinks for the
Neurolora project.
"""

import logging
import os
from pathlib import Path
from typing import Optional

# Get module logger
logger = logging.getLogger(__name__)


class StorageManager:
    """Manages storage directories and symlinks for Neurolora."""

    def __init__(
        self,
        project_root: Optional[Path] = None,
        subproject_id: Optional[str] = None,
    ) -> None:
        """Initialize the StorageManager.

        Args:
            project_root: Optional path to project root directory.
                        If not provided, uses current working directory.
            subproject_id: Optional subproject identifier.
                        If provided, will be appended to project name.
        """
        self.project_root = project_root or Path.cwd()
        logger.info("Initializing storage manager")
        logger.debug("Project root: %s", self.project_root)

        # Get project name and handle subproject
        base_name = self.project_root.name
        if subproject_id:
            self.project_name = f"{base_name}-{subproject_id}"
        else:
            self.project_name = base_name

        # Setup paths according to project structure
        self.mcp_docs_dir = Path.home() / ".mcp-docs"
        self.project_docs_dir = self.mcp_docs_dir / self.project_name
        self.neurolora_link = self.project_root / ".neurolora"

        # Ensure mcp_docs_dir exists
        self.mcp_docs_dir.mkdir(parents=True, exist_ok=True)

        logger.debug("Project name: %s", self.project_name)
        logger.debug("Project docs dir: %s", self.project_docs_dir)
        logger.debug("Neurolora link: %s", self.neurolora_link)
        logger.info("Storage manager initialized")

    def setup(self) -> None:
        """Setup storage structure and symlinks."""
        # Create all required directories immediately
        self._create_directories()

        # Create symlink and required files
        self._create_symlinks()
        self._create_ignore_file()
        self._create_task_files()

        # Ensure the project directory exists and is ready
        logger.info(
            "Storage setup complete. Project directory: %s",
            self.project_docs_dir,
        )

    def _create_directories(self) -> None:
        """Create required directories."""
        try:
            # Create all directories with parents
            self.project_docs_dir.mkdir(parents=True, exist_ok=True)
            logger.info(
                "Created/verified project directory: %s",
                self.project_docs_dir,
            )

            # Create marker file and force immediate directory availability
            marker = self.project_docs_dir / ".initialized"
            with open(marker, "w") as f:
                f.write("initialized")
                f.flush()
                os.fsync(f.fileno())

            # Force sync to ensure all changes are written
            os.sync()

            # Verify directory exists and is accessible
            if not self.project_docs_dir.exists():
                raise RuntimeError(
                    f"Failed to create directory: {self.project_docs_dir}"
                )

            # Wait for directory to be visible in filesystem
            import time

            max_retries = 10
            retry_delay = 0.1  # seconds
            for _ in range(max_retries):
                if self.project_docs_dir.exists():
                    break
                time.sleep(retry_delay)
            else:
                raise RuntimeError(
                    f"Directory not visible after {max_retries} retries: "
                    f"{self.project_docs_dir}"
                )

            # Final sync
            os.sync()
        except Exception as e:
            logger.error("Error creating directories: %s", str(e))
            raise

    def _create_symlinks(self) -> None:
        """Create or update symlinks."""
        try:
            # Create symlink from project root to project docs directory
            self._create_or_update_symlink(
                self.neurolora_link,
                self.project_docs_dir,
                ".neurolora",
            )
            # Force sync to ensure symlink is visible
            os.sync()

            # Wait for symlink to be visible in filesystem
            import time

            max_retries = 10
            retry_delay = 0.1  # seconds
            for _ in range(max_retries):
                if (
                    self.neurolora_link.exists()
                    and self.neurolora_link.is_symlink()
                ):
                    break
                time.sleep(retry_delay)
            else:
                raise RuntimeError(
                    f"Symlink not visible after {max_retries} retries: "
                    f"{self.neurolora_link}"
                )

            # Final sync
            os.sync()

            logger.info(
                "Symlink created and verified: %s",
                self.neurolora_link,
            )
        except Exception as e:
            logger.error("Error creating symlinks: %s", str(e))
            raise

    def _create_or_update_symlink(
        self, link_path: Path, target_path: Path, link_name: str
    ) -> None:
        """Create or update a symlink.

        Args:
            link_path: Path where symlink should be created
            target_path: Path that symlink should point to
            link_name: Name of the symlink for logging
        """
        logger.debug(
            "Creating symlink: %s -> %s",
            link_path,
            target_path,
        )
        try:
            # Ensure target directory exists
            target_path.mkdir(parents=True, exist_ok=True)

            # Create relative symlink
            relative_target = os.path.relpath(target_path, link_path.parent)

            if link_path.exists():
                logger.debug("Link path exists: %s", link_path)
                if not link_path.is_symlink():
                    logger.warning("Removing non-symlink %s", link_name)
                    link_path.unlink()
                    link_path.symlink_to(
                        relative_target, target_is_directory=True
                    )
                elif link_path.resolve() != target_path:
                    logger.warning("Updating incorrect %s symlink", link_name)
                    link_path.unlink()
                    link_path.symlink_to(
                        relative_target, target_is_directory=True
                    )
            else:
                logger.debug("Creating new symlink")
                link_path.symlink_to(relative_target, target_is_directory=True)
                logger.debug("Created %s symlink", link_name)

            # Verify symlink
            if not link_path.exists():
                raise RuntimeError(f"Symlink was not created: {link_path}")
            if not link_path.is_symlink():
                raise RuntimeError(
                    f"Path exists but is not a symlink: {link_path}"
                )
            resolved = link_path.resolve()
            if resolved != target_path:
                msg = (
                    f"Symlink points to wrong target: "
                    f"{resolved} != {target_path}"
                )
                raise RuntimeError(msg)
            logger.debug("Symlink verified successfully")

        except Exception as e:
            logger.error("Error creating symlink: %s", str(e))
            raise

    def _create_template_file(
        self,
        template_name: str,
        output_name: str,
        output_dir: Optional[Path] = None,
    ) -> None:
        """Create a file from a template if it doesn't exist.

        Args:
            template_name: Name of the template file
            output_name: Name of the output file
            output_dir: Optional directory for output file.
                       If not provided, uses project_docs_dir.
        """
        try:
            output_file = (output_dir or self.project_docs_dir) / output_name
            if not output_file.exists():
                # Copy from template
                template_file = (
                    Path(__file__).parent / "templates" / template_name
                )
                if template_file.exists():
                    try:
                        with open(template_file, "r", encoding="utf-8") as src:
                            content = src.read()
                        with open(output_file, "w", encoding="utf-8") as dst:
                            dst.write(content)
                        logger.debug(f"Created {output_name} from template")
                    except PermissionError:
                        logger.error(
                            f"Permission denied accessing files: "
                            f"{output_file} or {template_file}"
                        )
                        raise
                    except UnicodeDecodeError:
                        logger.error(
                            f"Invalid file encoding in template: "
                            f"{template_file}"
                        )
                        raise
                    except IOError as e:
                        logger.error(f"I/O error with files: {str(e)}")
                        raise
                else:
                    logger.warning(f"Template file not found: {template_file}")
        except (PermissionError, UnicodeDecodeError, IOError) as e:
            logger.error(f"File system error with files: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error with files: {str(e)}")
            logger.debug("Stack trace:", exc_info=True)
            raise

    def _create_ignore_file(self) -> None:
        """Create .neuroloraignore file if it doesn't exist."""
        self._create_template_file(
            "ignore.template", ".neuroloraignore", self.project_root
        )

    def _create_task_files(self) -> None:
        """Create TODO.md and DONE.md files if they don't exist."""
        self._create_template_file("todo.template.md", "TODO.md")
        self._create_template_file("done.template.md", "DONE.md")

    def get_output_path(self, filename: str) -> Path:
        """Get path for output file in project docs directory.

        Args:
            filename: Name of the file

        Returns:
            Path: Full path in project docs directory
        """
        return self.project_docs_dir / filename

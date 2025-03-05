"""
Central registry for quest files with unified discovery, validation, and deduplication.

This module provides a single source of truth for quest management throughout the system.
"""
import glob
import hashlib
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

from llm_quest_benchmark.constants import QUEST_ROOT_DIRECTORY

logger = logging.getLogger(__name__)


@dataclass
class QuestInfo:
    """Information about a quest file"""
    path: Path  # Absolute path to the quest file
    name: str  # Quest name (filename without extension)
    directory: str  # Relative directory from QUEST_ROOT_DIRECTORY
    file_hash: str  # Hash of file contents for deduplication
    duplicate_of: Optional[str] = None  # If this is a duplicate, path to original
    size: int = 0  # File size in bytes

    @property
    def is_duplicate(self) -> bool:
        """Whether this quest is a duplicate of another"""
        return self.duplicate_of is not None

    @property
    def relative_path(self) -> str:
        """Get the relative path from QUEST_ROOT_DIRECTORY"""
        return str(self.path.relative_to(Path(QUEST_ROOT_DIRECTORY)))


class QuestRegistry:
    """Central registry for quest files"""

    def __init__(self, reset_cache: bool = False):
        """Initialize the quest registry.

        Args:
            reset_cache: If True, force rescan even if cache exists
        """
        self._quests: Dict[str, QuestInfo] = {}  # Maps path -> QuestInfo
        self._quest_by_hash: Dict[str, Path] = {}  # Maps file_hash -> first path with that hash
        self._quest_by_name: Dict[str, List[Path]] = {}  # Maps quest name -> list of paths
        self._initialized = False

        # Initialize registry
        if reset_cache or not self._initialized:
            self._scan_quests()
            self._initialized = True

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute a hash of the file contents for deduplication.

        Args:
            file_path: Path to the file

        Returns:
            str: Hash of file contents
        """
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _scan_quests(self) -> None:
        """Scan for quest files and add them to the registry."""
        logger.info(f"Scanning for quest files in {QUEST_ROOT_DIRECTORY}")
        root_path = Path(QUEST_ROOT_DIRECTORY)

        # Clear existing data
        self._quests = {}
        self._quest_by_hash = {}
        self._quest_by_name = {}

        # Walk through all directories
        for path in root_path.glob("**/*.qm"):
            if not path.is_file():
                continue

            try:
                # Compute relative directory from QUEST_ROOT_DIRECTORY
                rel_dir = str(path.parent.relative_to(root_path))
                if rel_dir == ".":
                    rel_dir = ""

                # Compute file hash for deduplication
                file_hash = self._compute_file_hash(path)

                # Check if we've seen this hash before
                duplicate_of = None
                if file_hash in self._quest_by_hash:
                    duplicate_of = str(self._quest_by_hash[file_hash])
                else:
                    self._quest_by_hash[file_hash] = path

                # Create quest info
                quest_info = QuestInfo(path=path,
                                       name=path.stem,
                                       directory=rel_dir,
                                       file_hash=file_hash,
                                       duplicate_of=duplicate_of,
                                       size=path.stat().st_size)

                # Add to mappings
                self._quests[str(path)] = quest_info

                # Add to name mapping for lookup
                if path.stem not in self._quest_by_name:
                    self._quest_by_name[path.stem] = []
                self._quest_by_name[path.stem].append(path)

            except Exception as e:
                logger.error(f"Error processing quest file {path}: {e}")

        logger.info(f"Found {len(self._quests)} quest files "
                    f"({len(self._quest_by_hash)} unique, "
                    f"{len(self._quests) - len(self._quest_by_hash)} duplicates)")

    def resolve_quest_path(self, quest_path: Union[str, Path]) -> List[Path]:
        """Resolve a quest path (file, directory, or glob pattern) to list of quest file paths.

        Args:
            quest_path: Quest path or pattern

        Returns:
            List of resolved quest file paths
        """
        quest_path = str(quest_path)  # Convert Path to str if needed
        result = []

        # Check if it's a glob pattern
        if '*' in quest_path:
            # Use glob.glob to resolve the pattern
            for match in glob.glob(quest_path, recursive=True):
                p = Path(match)
                if p.is_file() and p.suffix == '.qm':
                    result.append(p)
        else:
            # Regular path processing
            p = Path(quest_path)

            # Handle relative paths that don't exist yet
            # If path starts with the quest root directory, use it as is
            if p.is_file() and p.suffix == '.qm':
                result.append(p)
            elif p.is_dir():
                result.extend(sorted(p.glob("**/*.qm")))
            # Otherwise, try treating as path relative to QUEST_ROOT_DIRECTORY
            elif not p.is_absolute() and not str(p).startswith(QUEST_ROOT_DIRECTORY):
                # First try with QUEST_ROOT_DIRECTORY prepended
                full_path = Path(QUEST_ROOT_DIRECTORY) / p

                if full_path.is_file() and full_path.suffix == '.qm':
                    result.append(full_path)
                elif full_path.is_dir():
                    result.extend(sorted(full_path.glob("**/*.qm")))
                # If path contains directory component, check if directory exists
                elif '/' in str(p):
                    # Extract directory part
                    dir_part = str(p).rsplit('/', 1)[0]
                    full_dir = Path(QUEST_ROOT_DIRECTORY) / dir_part
                    if full_dir.is_dir():
                        # Find all matching quest files in this directory
                        file_pattern = str(p).rsplit('/', 1)[1]
                        if not file_pattern.endswith('.qm'):
                            file_pattern += '.qm'
                        for match in full_dir.glob(file_pattern):
                            if match.is_file():
                                result.append(match)
                # Check if it's just a quest name (without directory or extension)
                elif quest_path in self._quest_by_name:
                    result.extend(self._quest_by_name[quest_path])
                # Last try - look for case-insensitive match in names
                else:
                    lower_quest_path = quest_path.lower()
                    for name, paths in self._quest_by_name.items():
                        if name.lower() == lower_quest_path:
                            result.extend(paths)
                            break
            # Otherwise, try direct lookup in registry (handles absolute paths)
            elif str(p) in self._quests:
                result.append(p)

        # Return unique, sorted paths
        unique_paths = list(dict.fromkeys(result))  # Preserve order while removing duplicates
        return sorted(unique_paths)

    def get_quest_info(self, path: Union[str, Path]) -> Optional[QuestInfo]:
        """Get information about a quest file.

        Args:
            path: Path to the quest file

        Returns:
            QuestInfo if found, None otherwise
        """
        path_str = str(path) if isinstance(path, Path) else path
        return self._quests.get(path_str)

    def get_unique_quests(self) -> List[QuestInfo]:
        """Get list of unique quest files (no duplicates).

        Returns:
            List of unique quest files
        """
        return [info for info in self._quests.values() if not info.is_duplicate]

    def get_all_quests(self) -> List[QuestInfo]:
        """Get list of all quest files.

        Returns:
            List of all quest files
        """
        return list(self._quests.values())

    def resolve_quests_from_config(self, quest_paths: List[str]) -> List[Path]:
        """Resolve a list of quest paths from a configuration.

        Args:
            quest_paths: List of quest paths from configuration

        Returns:
            List of resolved, unique quest file paths
        """
        result = []
        for path in quest_paths:
            resolved = self.resolve_quest_path(path)
            result.extend(resolved)

        # Filter out duplicates while preserving order
        seen = set()
        unique_result = [p for p in result if not (str(p) in seen or seen.add(str(p)))]
        return unique_result

    def search_quests(self, query: str) -> List[QuestInfo]:
        """Search for quests by name or directory.

        Args:
            query: Search query

        Returns:
            List of matching quest files
        """
        query = query.lower()
        return [
            info for info in self._quests.values()
            if query in info.name.lower() or query in info.directory.lower()
        ]


# Global registry instance
_registry = None


def get_registry(reset_cache: bool = False) -> QuestRegistry:
    """Get the global quest registry instance.

    Args:
        reset_cache: If True, force rescan even if registry exists

    Returns:
        The global quest registry
    """
    global _registry
    if _registry is None or reset_cache:
        _registry = QuestRegistry(reset_cache)
    return _registry


def resolve_quest_paths(quest_paths: List[str]) -> List[Path]:
    """Resolve a list of quest paths to actual file paths.

    This is a convenient wrapper around the registry for use in other modules.

    Args:
        quest_paths: List of quest paths (files, directories, or glob patterns)

    Returns:
        List of resolved, unique quest file paths
    """
    registry = get_registry()
    return registry.resolve_quests_from_config(quest_paths)


def validate_quest_path(quest_path: str) -> bool:
    """Validate that a quest path resolves to at least one existing quest file.

    Args:
        quest_path: Path to validate

    Returns:
        True if path is valid, False otherwise
    """
    registry = get_registry()
    resolved = registry.resolve_quest_path(quest_path)
    return len(resolved) > 0

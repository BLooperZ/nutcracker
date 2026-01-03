"""
FileSegment: Memory-Efficient File Reading

Provides offset-based file segment references with deferred data loading,
maintaining memory usage bounded by accessed segment size rather than total file size.
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path
from typing import Self

import numpy as np

open_mmaps: dict[str, ResourceFile] = {}


class FileSegment:
    """
    Memory-efficient file segment with deferred loading.

    Represents a byte range within a file using a chain of slices, supporting:
    - Slice chain for nested segments without offset arithmetic
    - Slice notation for creating sub-segments
    - Buffer protocol (bytes(), memoryview())
    - XOR decryption
    """

    __slots__ = (
        '_parent_ref',
        '_slice_chain',
        '_xor_key',
    )

    def __init__(
        self,
        slice_chain: tuple[slice, ...] = (),
        key: int = 0,
        parent_ref: ResourceFile | None = None,
    ) -> None:
        """
        Create a file segment reference using slice chain.

        Args:
            slice_chain: Tuple of slices to apply sequentially (empty = entire file)
            key: XOR key for decryption (0 = no encryption)
            parent_ref: Parent ResourceFile for resource sharing
        """
        self._slice_chain = tuple(slice_chain)
        self._xor_key = key
        self._parent_ref = parent_ref

    def __len__(self) -> int:
        """Return the size of the segment in bytes."""
        assert self._parent_ref is not None
        current_array = self._parent_ref.get_buffer(self._slice_chain)
        return len(current_array)

    def __getitem__(self, key: int | slice) -> int | FileSegment:
        """
        Support indexing and slicing.

        Args:
            key: Integer index or slice object

        Returns:
            For integer index: byte value (0-255)
            For slice: new FileSegment with extended slice chain
        """
        assert self._parent_ref is not None
        self._parent_ref._check_file_state()

        if isinstance(key, slice):
            # Extend slice chain without copying data
            new_slice_chain = (*self._slice_chain, key)
            return FileSegment(
                slice_chain=new_slice_chain,
                key=self._xor_key,
                parent_ref=self._parent_ref,
            )

        if isinstance(key, int):
            current_array = self._parent_ref.get_buffer(self._slice_chain)
            byte_val = current_array[key]
            if self._xor_key != 0:
                byte_val = byte_val ^ self._xor_key
            return int(byte_val)

        msg = f'Indices must be integers or slices, not {type(key).__name__}'
        raise TypeError(msg)

    def _get_raw_data(self) -> np.ndarray:
        """
        Get segment data as NumPy array by applying slice chain.

        Returns:
            NumPy array view of the data (supports buffer protocol directly)
        """
        assert self._parent_ref is not None
        current_array = self._parent_ref.get_buffer(self._slice_chain)

        if self._xor_key != 0:
            return current_array ^ self._xor_key
        return current_array

    def _get_data(self) -> bytes:
        """
        Get segment data as bytes.

        Returns:
            Bytes data for this segment
        """
        return self._get_raw_data().tobytes()

    def __bytes__(self) -> bytes:
        """Convert segment to bytes."""
        return self._get_data()

    def tobytes(self) -> bytes:
        """Convert segment to bytes (alternative method)."""
        return self._get_data()

    def __buffer__(self, flags: int) -> memoryview:
        """Support buffer protocol (Python 3.12+)."""
        return memoryview(self._get_raw_data())

    def __repr__(self) -> str:
        """String representation."""
        slices_str = ' -> '.join(str(s) for s in self._slice_chain) if self._slice_chain else 'full'
        return f'FileSegment(slices={slices_str}, size={len(self)} bytes)'

    def decrypt(self, key: int) -> FileSegment:
        """Return a new FileSegment that applies the given XOR key.

        This does not modify the current segment; it returns a new segment
        that will apply the XOR key on reads.
        """
        return FileSegment(slice_chain=self._slice_chain, key=key, parent_ref=self._parent_ref)


class ResourceFile(FileSegment):
    """
    Resource file for creating segments with resource sharing.

    Inherits from FileSegment and represents the entire file (offset 0 to file_size).
    Manages shared resources (file handle, memory map) that child segments can use.

    Entry point for loading files:
        file_ref = ResourceFile.load("data.bin")
        segment = file_ref[1000:2000]  # Creates FileSegment child
        data = bytes(file_ref)          # ResourceFile IS a FileSegment (entire file)
    """

    __slots__ = (
        '_closed',
        '_file_path',
        '_mmap_array',  # NumPy memmap or array
        '_tmpfile',  # Temporary file for ejected memmap
    )

    def __init__(self, file_path: Path, key: int = 0) -> None:
        """
        Create a resource file reference (represents entire file).

        Args:
            file_path: Path to the file
            key: XOR key for decryption (0 = no encryption)
        """
        stat = file_path.stat()
        file_size = stat.st_size

        super().__init__(
            slice_chain=(),
            key=key,
            parent_ref=None,
        )

        self._closed = False
        self._file_path = file_path
        # ResourceFile acts as its own parent
        self._parent_ref = self
        self._tmpfile = None

        if file_size < io.DEFAULT_BUFFER_SIZE:
            # Small files: load directly (< 8KB)
            self._mmap_array = np.fromfile(file_path, dtype=np.uint8)
        else:
            # Large files: use memory-mapped file
            self._mmap_array = np.memmap(self._file_path, dtype=np.uint8, mode='r')

    @classmethod
    def load(
        cls,
        file_path: str | Path,
        key: int = 0,
        copy: bool = True,
    ) -> ResourceFile:
        """
        Load a file as a resource for creating segments.

        Reuses existing ResourceFile if the file is already open.

        Args:
            file_path: Path to the file
            key: XOR key for decryption (0 = no encryption)
            copy: Reserved for future use (currently ignored)

        Returns:
            ResourceFile object (which IS a FileSegment representing entire file)

        Raises:
            FileNotFoundError: If file does not exist
        """
        path = Path(file_path)
        if not path.exists():
            msg = f'File not found: {file_path}'
            raise FileNotFoundError(msg)

        # Check if file is already open and reuse it
        canonical_path = str(path.resolve())
        existing = open_mmaps.get(canonical_path)

        if existing is not None and not existing._closed:
            # If same key, return existing instance
            if existing._xor_key == key:
                return existing
            # If different key, return a new segment with the key applied
            return existing.decrypt(key)

        # Create new resource and register it
        instance = cls(path, key)
        # Only track large files (memmaps) in the registry
        if isinstance(instance._mmap_array, np.memmap):
            open_mmaps[canonical_path] = instance

        return instance

    def _check_file_state(self) -> None:
        """
        Check if file reference is closed.

        Raises:
            OSError: If parent reference is closed
        """
        if self._closed:
            msg = f'File reference is closed: {self._file_path}'
            raise OSError(msg)

    def get_buffer(self, slice_chain: tuple[slice, ...] = ()) -> np.ndarray:
        """
        Return the underlying buffer view after validating file state.

        Applies the provided slice_chain to the underlying array to obtain
        the final view. Callers who retain the returned ndarray will hold
        a reference to the memmap.

        Args:
            slice_chain: Tuple of slices to apply sequentially

        Returns:
            NumPy array view of the sliced data
        """
        self._check_file_state()

        # Apply each slice in the chain sequentially
        final = self._mmap_array
        for slice_obj in slice_chain:
            final = final[slice_obj]
        return final

    def __enter__(self) -> Self:
        """Enter context manager - return self."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager - clean up resources."""
        self.close()

    def eject(self) -> None:
        """
        Eject memmap to a temporary file.

        Useful when the original file needs to be modified while keeping
        the data accessible through this ResourceFile instance.
        """
        if not isinstance(self._mmap_array, np.memmap):
            return

        # Write memmap to temporary file
        tmpfile = tempfile.NamedTemporaryFile(delete=False)
        self._mmap_array.tofile(tmpfile)
        tmpfile.flush()

        self._tmpfile = tmpfile
        # Remap to temporary file
        self._mmap_array = np.memmap(tmpfile.name, dtype=np.uint8, mode='r')

    def close(self) -> None:
        """Close resource file and release resources."""
        if self._closed:
            return

        # Remove from open_mmaps before cleanup
        open_mmaps.pop(str(self._file_path.resolve()), None)

        self._mmap_array = None
        if self._tmpfile is not None:
            Path(self._tmpfile.name).unlink(missing_ok=True)
            self._tmpfile = None

        self._closed = True

    def __del__(self) -> None:
        """Cleanup on garbage collection."""
        self.close()

    def __repr__(self) -> str:
        """String representation."""
        status = 'closed' if self._closed else 'open'
        return f'ResourceFile(file={self._file_path.name}, size={len(self)} bytes, {status})'


def read_file(file_path: str | Path, key: int = 0x00) -> bytes:
    """
    Read the contents of a file, optionally applying XOR decryption.

    Args:
        file_path: The path to the file to read
        key: The key to use for XOR decryption (0x00 means no decryption)

    Returns:
        The contents of the file as bytes
    """
    with ResourceFile.load(file_path, key=key, copy=False) as res:
        return bytes(res)


def write_file(file_path: str | Path, data: bytes, key: int = 0x00) -> int:
    """
    Write data to a file, optionally applying XOR encryption.

    If the file is currently open as a ResourceFile memmap, it will be
    ejected to a temporary file first to avoid conflicts.

    Uses efficient memory-mapped writes for large files.

    Args:
        file_path: The path to the file to write
        data: The data to write
        key: The key to use for XOR encryption (0x00 means no encryption)

    Returns:
        Number of bytes written
    """
    path = Path(file_path).resolve()

    # Eject any open memmap to avoid conflicts
    ref = open_mmaps.get(str(path))
    if ref is not None and ref._tmpfile is None:
        ref.eject()

    data_size = len(data)

    # Small files: write directly
    if data_size < io.DEFAULT_BUFFER_SIZE:
        data_array = np.frombuffer(data, dtype=np.uint8)
        if key != 0:
            data_array = data_array ^ key
        with path.open('wb') as f:
            return f.write(data_array.tobytes())

    # Large files: use memmap for efficient in-place XOR
    # Create writable memmap - numpy creates the file if shape is provided
    mmap = np.memmap(path, dtype=np.uint8, mode='w+', shape=(data_size,))
    try:
        # Write data directly to memmap
        mmap[:] = np.frombuffer(data, dtype=np.uint8)
        # XOR in-place if key provided
        if key != 0:
            mmap[:] ^= key
        mmap.flush()
    finally:
        del mmap  # Close memmap

    return data_size


def close_all_memmaps() -> None:
    """Close all open memory-mapped files."""
    for ref in list(open_mmaps.values()):
        ref.close()


__all__ = [
    'FileSegment',  # Memory-efficient file segment with slice chain
    'ResourceFile',  # Resource file for creating segments
    'close_all_memmaps',  # Close all open memory-mapped files
    'read_file',  # Read file with optional XOR decryption
    'write_file',  # Write file with optional XOR encryption
]

#!/usr/bin/env python3
"""
CS 4348 Project 3 - B-Tree Index File Manager

Commands:
    python3 project3.py create <index_file>
    python3 project3.py insert <index_file> <key> <value>
    python3 project3.py search <index_file> <key>
    python3 project3.py load <index_file> <csv_file>
    python3 project3.py print <index_file>
    python3 project3.py extract <index_file> <output_csv>

The index file is stored as 512-byte blocks. Block 0 is the header.
Every B-tree node occupies exactly one 512-byte block.
"""

import csv
import os
import sys
import tempfile
from typing import Callable, Optional, Tuple

BLOCK_SIZE = 512
MAGIC = b"4348PRJ3"
UINT64_SIZE = 8

# B-tree minimum degree t = 10.
# Therefore, max keys = 2t - 1 = 19 and max children = 2t = 20.
MIN_DEGREE = 10
MAX_KEYS = 2 * MIN_DEGREE - 1
MAX_CHILDREN = 2 * MIN_DEGREE
MIN_KEYS = MIN_DEGREE - 1

UINT64_MAX = (1 << 64) - 1


class ProjectError(Exception):
    """Raised for user-facing project errors."""


class Node:
    """Represents one B-tree node stored in one 512-byte block."""

    def __init__(
        self,
        block_id: int,
        parent: int = 0,
        num_keys: int = 0,
        keys: Optional[list[int]] = None,
        values: Optional[list[int]] = None,
        children: Optional[list[int]] = None,
    ) -> None:
        self.block_id = block_id
        self.parent = parent
        self.num_keys = num_keys
        self.keys = keys if keys is not None else [0] * MAX_KEYS
        self.values = values if values is not None else [0] * MAX_KEYS
        self.children = children if children is not None else [0] * MAX_CHILDREN

    def is_leaf(self) -> bool:
        # Because block 0 is the header block, zero is the null child pointer.
        return self.children[0] == 0

    @classmethod
    def from_block(cls, data: bytes) -> "Node":
        if len(data) != BLOCK_SIZE:
            raise ProjectError("Invalid node block size.")

        offset = 0
        block_id = bytes_to_u64(data[offset:offset + UINT64_SIZE])
        offset += UINT64_SIZE
        parent = bytes_to_u64(data[offset:offset + UINT64_SIZE])
        offset += UINT64_SIZE
        num_keys = bytes_to_u64(data[offset:offset + UINT64_SIZE])
        offset += UINT64_SIZE

        if num_keys > MAX_KEYS:
            raise ProjectError("Invalid index file: node has too many keys.")

        keys = []
        for _ in range(MAX_KEYS):
            keys.append(bytes_to_u64(data[offset:offset + UINT64_SIZE]))
            offset += UINT64_SIZE

        values = []
        for _ in range(MAX_KEYS):
            values.append(bytes_to_u64(data[offset:offset + UINT64_SIZE]))
            offset += UINT64_SIZE

        children = []
        for _ in range(MAX_CHILDREN):
            children.append(bytes_to_u64(data[offset:offset + UINT64_SIZE]))
            offset += UINT64_SIZE

        return cls(block_id, parent, num_keys, keys, values, children)

    def to_block(self) -> bytes:
        pieces = [
            u64_to_bytes(self.block_id),
            u64_to_bytes(self.parent),
            u64_to_bytes(self.num_keys),
        ]

        for key in self.keys:
            pieces.append(u64_to_bytes(key))
        for value in self.values:
            pieces.append(u64_to_bytes(value))
        for child in self.children:
            pieces.append(u64_to_bytes(child))

        data = b"".join(pieces)
        if len(data) > BLOCK_SIZE:
            raise ProjectError("Internal error: node is larger than one block.")
        return data + bytes(BLOCK_SIZE - len(data))


def u64_to_bytes(value: int) -> bytes:
    if value < 0 or value > UINT64_MAX:
        raise ProjectError(f"Value {value} is outside the unsigned 64-bit range.")
    return value.to_bytes(UINT64_SIZE, byteorder="big", signed=False)


def bytes_to_u64(data: bytes) -> int:
    if len(data) != UINT64_SIZE:
        raise ProjectError("Invalid integer field size.")
    return int.from_bytes(data, byteorder="big", signed=False)


def parse_u64(text: str, field_name: str) -> int:
    try:
        value = int(text, 10)
    except ValueError as exc:
        raise ProjectError(f"Invalid {field_name}: {text}") from exc

    if value < 0 or value > UINT64_MAX:
        raise ProjectError(f"Invalid {field_name}: must be between 0 and {UINT64_MAX}.")
    return value


class BTreeIndex:
    """File-backed B-tree index."""

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.file = None
        self.root_id = 0
        self.next_block_id = 1

    def __enter__(self) -> "BTreeIndex":
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    @staticmethod
    def create(filename: str) -> None:
        if os.path.exists(filename):
            raise ProjectError(f"Index file already exists: {filename}")

        with open(filename, "wb") as f:
            header = MAGIC + u64_to_bytes(0) + u64_to_bytes(1)
            header += bytes(BLOCK_SIZE - len(header))
            f.write(header)

    def open(self) -> None:
        if not os.path.exists(self.filename):
            raise ProjectError(f"Index file does not exist: {self.filename}")

        self.file = open(self.filename, "r+b")
        self._read_header()
        self._validate_file_size()

    def close(self) -> None:
        if self.file is not None:
            self.file.close()
            self.file = None

    def _validate_file_size(self) -> None:
        assert self.file is not None
        self.file.seek(0, os.SEEK_END)
        size = self.file.tell()

        if size < BLOCK_SIZE or size % BLOCK_SIZE != 0:
            raise ProjectError("Invalid index file: file size is not a whole number of blocks.")

        actual_blocks = size // BLOCK_SIZE
        if self.next_block_id > actual_blocks:
            raise ProjectError("Invalid index file: next block id is beyond the file size.")
        if self.root_id >= self.next_block_id:
            raise ProjectError("Invalid index file: root block id is invalid.")

    def _read_header(self) -> None:
        assert self.file is not None
        self.file.seek(0)
        data = self.file.read(BLOCK_SIZE)
        if len(data) != BLOCK_SIZE:
            raise ProjectError("Invalid index file: missing header block.")
        if data[:8] != MAGIC:
            raise ProjectError("Invalid index file: bad magic number.")

        self.root_id = bytes_to_u64(data[8:16])
        self.next_block_id = bytes_to_u64(data[16:24])

        if self.next_block_id < 1:
            raise ProjectError("Invalid index file: bad next block id.")

    def _write_header(self) -> None:
        assert self.file is not None
        self.file.seek(0)
        header = MAGIC + u64_to_bytes(self.root_id) + u64_to_bytes(self.next_block_id)
        header += bytes(BLOCK_SIZE - len(header))
        self.file.write(header)
        self.file.flush()

    def read_node(self, block_id: int) -> Node:
        assert self.file is not None
        if block_id == 0 or block_id >= self.next_block_id:
            raise ProjectError(f"Invalid node block id: {block_id}")

        self.file.seek(block_id * BLOCK_SIZE)
        data = self.file.read(BLOCK_SIZE)
        if len(data) != BLOCK_SIZE:
            raise ProjectError("Invalid index file: node block is missing or incomplete.")

        node = Node.from_block(data)
        if node.block_id != block_id:
            raise ProjectError("Invalid index file: node block id does not match its location.")
        return node

    def write_node(self, node: Node) -> None:
        assert self.file is not None
        if node.block_id == 0 or node.block_id >= self.next_block_id:
            raise ProjectError(f"Invalid node block id: {node.block_id}")

        self.file.seek(node.block_id * BLOCK_SIZE)
        self.file.write(node.to_block())
        self.file.flush()

    def allocate_node(self, parent: int = 0) -> Node:
        assert self.file is not None
        block_id = self.next_block_id
        self.next_block_id += 1
        self._write_header()

        node = Node(block_id=block_id, parent=parent)
        self.file.seek(block_id * BLOCK_SIZE)
        self.file.write(node.to_block())
        self.file.flush()
        return node

    def search(self, key: int) -> Optional[Tuple[int, int, int]]:
        """Return (node_id, slot_index, value) if found, otherwise None."""
        current_id = self.root_id

        while current_id != 0:
            node = self.read_node(current_id)
            i = 0
            while i < node.num_keys and key > node.keys[i]:
                i += 1

            if i < node.num_keys and key == node.keys[i]:
                return node.block_id, i, node.values[i]

            current_id = node.children[i]

        return None

    def insert(self, key: int, value: int) -> None:
        # Treat duplicate insertion as an update. This keeps the index one-to-one by key.
        existing = self.search(key)
        if existing is not None:
            node_id, slot, _old_value = existing
            node = self.read_node(node_id)
            node.values[slot] = value
            self.write_node(node)
            return

        if self.root_id == 0:
            root = self.allocate_node(parent=0)
            root.num_keys = 1
            root.keys[0] = key
            root.values[0] = value
            self.root_id = root.block_id
            self.write_node(root)
            self._write_header()
            return

        root = self.read_node(self.root_id)
        if root.num_keys == MAX_KEYS:
            new_root = self.allocate_node(parent=0)
            new_root.children[0] = root.block_id

            root.parent = new_root.block_id
            self.write_node(root)

            self.root_id = new_root.block_id
            self._write_header()

            self.split_child(new_root, 0, root)
            self.insert_nonfull(new_root.block_id, key, value)
        else:
            self.insert_nonfull(root.block_id, key, value)

    def split_child(self, parent: Node, index: int, child: Node) -> None:
        """Split parent.children[index], which must be full."""
        if child.num_keys != MAX_KEYS:
            raise ProjectError("Internal error: attempted to split a non-full child.")
        if parent.num_keys >= MAX_KEYS:
            raise ProjectError("Internal error: attempted to split into a full parent.")

        sibling = self.allocate_node(parent=parent.block_id)
        sibling.num_keys = MIN_KEYS

        median_key = child.keys[MIN_KEYS]
        median_value = child.values[MIN_KEYS]

        # Move the largest t - 1 keys/values from child into sibling.
        for j in range(MIN_KEYS):
            sibling.keys[j] = child.keys[j + MIN_DEGREE]
            sibling.values[j] = child.values[j + MIN_DEGREE]
            child.keys[j + MIN_DEGREE] = 0
            child.values[j + MIN_DEGREE] = 0

        child.keys[MIN_KEYS] = 0
        child.values[MIN_KEYS] = 0

        # Move the largest t child pointers if the child is internal.
        moved_child_ids = []
        if not child.is_leaf():
            for j in range(MIN_DEGREE):
                sibling.children[j] = child.children[j + MIN_DEGREE]
                moved_child_ids.append(sibling.children[j])
                child.children[j + MIN_DEGREE] = 0

        child.num_keys = MIN_KEYS

        # Shift parent child pointers right to make room for the new sibling.
        for j in range(parent.num_keys, index, -1):
            parent.children[j + 1] = parent.children[j]
        parent.children[index + 1] = sibling.block_id

        # Shift parent keys/values right to make room for the promoted median.
        for j in range(parent.num_keys - 1, index - 1, -1):
            parent.keys[j + 1] = parent.keys[j]
            parent.values[j + 1] = parent.values[j]

        parent.keys[index] = median_key
        parent.values[index] = median_value
        parent.num_keys += 1

        self.write_node(child)
        self.write_node(sibling)
        self.write_node(parent)

        # Update parent pointers for children moved to the sibling.
        for moved_id in moved_child_ids:
            if moved_id != 0:
                moved = self.read_node(moved_id)
                moved.parent = sibling.block_id
                self.write_node(moved)

    def insert_nonfull(self, node_id: int, key: int, value: int) -> None:
        node = self.read_node(node_id)
        i = node.num_keys - 1

        if node.is_leaf():
            while i >= 0 and key < node.keys[i]:
                node.keys[i + 1] = node.keys[i]
                node.values[i + 1] = node.values[i]
                i -= 1

            node.keys[i + 1] = key
            node.values[i + 1] = value
            node.num_keys += 1
            self.write_node(node)
            return

        while i >= 0 and key < node.keys[i]:
            i -= 1
        i += 1

        child = self.read_node(node.children[i])
        if child.num_keys == MAX_KEYS:
            self.split_child(node, i, child)
            node = self.read_node(node_id)

            if key > node.keys[i]:
                i += 1
            elif key == node.keys[i]:
                node.values[i] = value
                self.write_node(node)
                return

        self.insert_nonfull(node.children[i], key, value)

    def traverse_pairs(self, visit: Callable[[int, int], None]) -> None:
        if self.root_id == 0:
            return
        self._traverse_node(self.root_id, visit)

    def _traverse_node(self, node_id: int, visit: Callable[[int, int], None]) -> None:
        # This intentionally does not keep a stack of Node objects. It reads the
        # current node as needed, saves only scalar fields, and then releases it.
        node = self.read_node(node_id)
        num_keys = node.num_keys
        is_leaf = node.is_leaf()
        del node

        for i in range(num_keys):
            node = self.read_node(node_id)
            child_id = node.children[i]
            key = node.keys[i]
            value = node.values[i]
            del node

            if not is_leaf and child_id != 0:
                self._traverse_node(child_id, visit)
            visit(key, value)

        if not is_leaf:
            node = self.read_node(node_id)
            last_child_id = node.children[num_keys]
            del node
            if last_child_id != 0:
                self._traverse_node(last_child_id, visit)


def command_create(args: list[str]) -> None:
    if len(args) != 1:
        raise ProjectError("Usage: project3 create <index_file>")
    BTreeIndex.create(args[0])


def command_insert(args: list[str]) -> None:
    if len(args) != 3:
        raise ProjectError("Usage: project3 insert <index_file> <key> <value>")

    index_file = args[0]
    key = parse_u64(args[1], "key")
    value = parse_u64(args[2], "value")

    with BTreeIndex(index_file) as index:
        index.insert(key, value)


def command_search(args: list[str]) -> None:
    if len(args) != 2:
        raise ProjectError("Usage: project3 search <index_file> <key>")

    index_file = args[0]
    key = parse_u64(args[1], "key")

    with BTreeIndex(index_file) as index:
        result = index.search(key)

    if result is None:
        raise ProjectError(f"Key not found: {key}")

    _node_id, _slot, value = result
    print(f"{key},{value}")


def command_load(args: list[str]) -> None:
    if len(args) != 2:
        raise ProjectError("Usage: project3 load <index_file> <csv_file>")

    index_file = args[0]
    csv_file = args[1]

    if not os.path.exists(csv_file):
        raise ProjectError(f"CSV file does not exist: {csv_file}")

    with BTreeIndex(index_file) as index:
        with open(csv_file, "r", newline="") as f:
            reader = csv.reader(f)
            for line_number, row in enumerate(reader, start=1):
                if len(row) == 0 or all(cell.strip() == "" for cell in row):
                    continue
                if len(row) != 2:
                    raise ProjectError(f"Invalid CSV line {line_number}: expected key,value")

                key = parse_u64(row[0].strip(), f"key on line {line_number}")
                value = parse_u64(row[1].strip(), f"value on line {line_number}")
                index.insert(key, value)


def command_print(args: list[str]) -> None:
    if len(args) != 1:
        raise ProjectError("Usage: project3 print <index_file>")

    index_file = args[0]

    with BTreeIndex(index_file) as index:
        index.traverse_pairs(lambda key, value: print(f"{key},{value}"))


def command_extract(args: list[str]) -> None:
    if len(args) != 2:
        raise ProjectError("Usage: project3 extract <index_file> <output_csv>")

    index_file = args[0]
    output_file = args[1]

    if os.path.exists(output_file):
        raise ProjectError(f"Output file already exists: {output_file}")

    output_dir = os.path.dirname(os.path.abspath(output_file)) or "."
    fd, temp_path = tempfile.mkstemp(prefix="project3_extract_", suffix=".tmp", dir=output_dir)

    try:
        with os.fdopen(fd, "w", newline="") as f:
            writer = csv.writer(f, lineterminator="\n")

            with BTreeIndex(index_file) as index:
                index.traverse_pairs(lambda key, value: writer.writerow([key, value]))

        os.replace(temp_path, output_file)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def print_usage() -> None:
    print("Usage:", file=sys.stderr)
    print("  project3 create <index_file>", file=sys.stderr)
    print("  project3 insert <index_file> <key> <value>", file=sys.stderr)
    print("  project3 search <index_file> <key>", file=sys.stderr)
    print("  project3 load <index_file> <csv_file>", file=sys.stderr)
    print("  project3 print <index_file>", file=sys.stderr)
    print("  project3 extract <index_file> <output_csv>", file=sys.stderr)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print_usage()
        return 1

    command = argv[1]
    args = argv[2:]

    commands = {
        "create": command_create,
        "insert": command_insert,
        "search": command_search,
        "load": command_load,
        "print": command_print,
        "extract": command_extract,
    }

    if command not in commands:
        print_usage()
        print(f"ERROR: Unknown command: {command}", file=sys.stderr)
        return 1

    try:
        commands[command](args)
        return 0
    except ProjectError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

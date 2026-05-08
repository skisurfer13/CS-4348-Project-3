# Devlog

## May 08, 2026 - 6:37 PM

### What I Know
- The goal is to build a command-line Python program that creates and manages B-tree index files.
- The required commands are `create`, `insert`, `search`, `load`, `print`, and `extract`.
- The index file must use 512-byte blocks.
- Block 0 is the file header, which stores the magic number, the root block id, and the next available block id.
- Each B-tree node must fit inside one 512-byte block.
- The B-tree has minimum degree 10, so each node can store up to 19 key/value pairs and 20 child pointers.
- All integer fields in the file must be stored as 8-byte big-endian values.
- The implementation should not rely on external libraries or an IDE, so I am using only the Python standard library.

### Thoughts
- Ideally, this project would be developed over multiple sessions with several smaller commits.
- For this submission, I completed the implementation in one focused sitting because I had three finals this week, multiple project and assignment submissions, and prior experience implementing and studying B-trees in my Data Structures and Algorithms and Database Systems classes.
- Since I had already worked with B-tree concepts before, I was able to move directly from the project specification to the file-layout implementation.
- The devlog and commit history reflect this one-session development approach rather than a long multi-day implementation process.

### Plan
- Set up the project structure and prepare the main Python file.
- Define constants for the block size, magic number, B-tree degree, maximum number of keys, and maximum number of children.
- Implement helper functions for reading and writing 8-byte big-endian integers.
- Implement the index file header format.
- Implement a fixed-size B-tree node representation that matches the required block layout.
- Implement file-level operations for reading and writing nodes by block id.
- Implement `create` to initialize a valid empty index file.
- Implement `insert` using B-tree insertion with node splitting.
- Implement `search` to locate a key and print its key/value pair.
- Implement `load` to read key/value pairs from a CSV file and insert them into the index.
- Implement `print` using an in-order traversal so that all key/value pairs are printed in sorted order.
- Implement `extract` to write all key/value pairs to a new CSV file.
- Add error handling for invalid commands, missing files, invalid index files, invalid numbers, duplicate output files, and malformed CSV input.
- Test the program from the command line using the required commands.

### What I Did
- Created the main Python implementation file.
- Implemented the binary index-file layout using 512-byte blocks.
- Implemented the header block with the magic number, root block id, and next block id.
- Implemented B-tree nodes with block id, parent block id, number of keys, keys array, values array, and child pointer array.
- Implemented node serialization and deserialization so that nodes can be written to and read from disk.
- Implemented `create` so that a new empty index file is created only when the target file does not already exist.
- Implemented `insert` for both empty and non-empty trees.
- Implemented B-tree node splitting when a node becomes full.
- Implemented root splitting when the root is full.
- Implemented updating an existing key's value if the same key is inserted again.
- Implemented `search` to print the key/value pair when the key exists and an error message otherwise.
- Implemented `load` so that a CSV file can bulk-insert multiple key/value pairs.
- Implemented `print` to display all key/value pairs in sorted order.
- Implemented `extract` to save all key/value pairs to a new CSV file without overwriting an existing file.
- Added command-line argument parsing and command-specific validation.
- Added error messages for common invalid inputs and invalid file states.
- Tested the program with creating an index file, inserting values, searching for values, loading from a CSV file, printing the full tree contents, and extracting the contents to a CSV file.

### Problems
- The main challenge was making sure the on-disk node layout exactly matched the project specification.
- I had to be careful to keep the file header synchronized whenever the root block id or next available block id changed.
- B-tree splitting required careful handling because the median key/value pair moves upward while the left and right nodes keep the remaining entries.
- Parent and child block ids needed to be updated correctly after node splits.
- I also had to make sure that `extract` does not overwrite an existing file, since the specification says the file should remain unmodified if the target output file already exists.

### Testing
- Tested `create` with a new file and confirmed that it creates a valid empty index file.
- Tested `create` again with the same filename and confirmed that it fails instead of overwriting the existing file.
- Tested `insert` with multiple key/value pairs.
- Tested `search` for keys that exist and keys that do not exist.
- Tested enough inserts to force B-tree node splitting.
- Tested `load` with a CSV file containing comma-separated key/value pairs.
- Tested `print` to confirm that all pairs are displayed in sorted order.
- Tested `extract` to confirm that all pairs are saved to a CSV file.
- Tested `extract` again with an existing output filename and confirmed that it fails without modifying the file.

### Next Session
- No additional implementation session is planned because the full project was completed in this sitting.
- Before submission, I still need to make sure the repository contains the required files: `project3.py`, `devlog.md`, the project report and the GitHub link.


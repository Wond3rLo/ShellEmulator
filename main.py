
import tkinter as tk
import shlex
import argparse
import tomllib
import xml.etree.ElementTree as ET
import getpass
from pathlib import Path
import csv
import fnmatch  
import posixpath 

class ShellEmulator:
    # Accept configuration and command-line parameters
    def __init__(self, root, config):
        self.root = root
        self.config = config
        self.vfs = {}
        self.current_dir = ""  # Current directory inside the VFS
        self.previous_dir = ""  # Previous directory for cd -

        self.root.title(f"Shell Emulator - {Path(config['vfs_path']).name}")
        self.root.geometry("700x450")

        self.output = tk.Text(root, state="disabled")
        self.output.pack(fill="both", expand=True, padx=10, pady=10)

        self.command_entry = tk.Entry(root)
        self.command_entry.pack(fill="x", padx=10, pady=(0, 10))
        self.command_entry.bind("<Return>", self.run_command)

        # Run the startup script after the window opens
        self.root.after(100, self.load_vfs)
        self.root.after(200, self.run_startup_script)

    def load_vfs(self):
        vfs_path = Path(self.config["vfs_path"])

        if not vfs_path.exists():
            self.write_output(
                f"VFS error: file not found: {vfs_path}\n"
            )
            self.vfs = {}
            return

        self.vfs = {}

        try:
            with vfs_path.open("r", encoding="utf-8", newline="") as file:
                reader = csv.DictReader(file)

                for row in reader:
                    path = row["path"].strip("/")
                    item_type = row["type"].strip()
                    content = row["content"]

                    self.vfs[path] = {
                        "type": item_type,
                        "content": content
                    }

            # Ensure the virtual root always exists
            self.vfs.setdefault("", {"type": "dir", "content": ""})
            self.current_dir = ""
            self.previous_dir = ""

            self.write_output(
                f"VFS loaded: {len(self.vfs)} entries\n"
            )

        except (OSError, KeyError, csv.Error) as error:
            self.vfs = {}
            self.write_output(f"VFS error: {error}\n")

    # Save the current VFS to a CSV file
    def save_vfs(self, save_path):
        save_path = Path(save_path)

        try:
            save_path.parent.mkdir(parents=True, exist_ok=True)

            with save_path.open(
                "w", encoding="utf-8", newline=""
            ) as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=["path", "type", "content"]
                )
                writer.writeheader()

                for path, item in self.vfs.items():
                    writer.writerow({
                        "path": "/" + path if path else "/",
                        "type": item["type"],
                        "content": item["content"]
                    })

            self.write_output(f"VFS saved to {save_path}\n")
            return True

        except OSError as error:
            self.write_output(f"VFS save error: {error}\n")
            return False

    # Reset the VFS to its default empty state
    def init_vfs(self):
        self.vfs = {
            "": {
                "type": "dir",
                "content": ""
            }
        }
        self.current_dir = ""  # Return to the VFS root
        self.previous_dir = ""  # Reset previous directory

        if not self.save_vfs(self.config["vfs_path"]):
            return False

        self.write_output("VFS initialized\n")
        return True

    # Process commands entered by the user
    def run_command(self, event=None):
        command_text = self.command_entry.get()
        self.command_entry.delete(0, tk.END)

        self.write_output(f"> {command_text}\n")
        self.execute_command(command_text)

    # Resolve a user-supplied path inside the virtual filesystem
    def resolve_path(self, path):
        if path == "":
            path = self.current_dir
        elif path == "-":
            path = self.previous_dir
        elif not path.startswith("/"):
            path = posixpath.join(self.current_dir, path)

        normalized = posixpath.normpath("/" + path).strip("/")
        return normalized

    # Check whether a path exists and points to a directory
    def is_directory(self, path):
        item = self.vfs.get(path)
        return item is not None and item["type"] == "dir"

    # Return the direct children of a virtual directory
    def get_children(self, directory):
        prefix = directory + "/" if directory else ""
        children = []

        for path, item in self.vfs.items():
            if path == directory or not path.startswith(prefix):
                continue

            remainder = path[len(prefix):]
            if remainder and "/" not in remainder:
                children.append((remainder, path, item))

        return sorted(children, key=lambda child: (child[2]["type"] != "dir", child[0].lower()))

    # Implement ls using only the virtual filesystem
    def command_ls(self, arguments):
        show_all = "-a" in arguments
        long_format = "-l" in arguments
        paths = [arg for arg in arguments if not arg.startswith("-")]

        if len(paths) > 1:
            raise ValueError("Usage: ls [-a] [-l] [path]")

        target = self.resolve_path(paths[0] if paths else "")
        item = self.vfs.get(target)

        if item is None:
            raise ValueError(f"ls: cannot access '{paths[0] if paths else target}': no such file or directory")

        if item["type"] == "file":
            self.write_output(target + "\n")
            return

        children = self.get_children(target)
        if show_all:
            children = [(".", target, {"type": "dir", "content": ""}),
                        ("..", posixpath.dirname(target), {"type": "dir", "content": ""})] + children

        if not children:
            self.write_output("(empty directory)\n")
            return

        for name, child_path, child_item in children:
            if long_format:
                self.write_output(f"{child_item['type']:4} {child_path or '/'}\n")
            else:
                suffix = "/" if child_item["type"] == "dir" and name not in (".", "..") else ""
                self.write_output(f"{name}{suffix}\n")

    # Implement cd using virtual paths
    def command_cd(self, arguments):
        if len(arguments) > 1:
            raise ValueError("Usage: cd [path]")

        target_arg = arguments[0] if arguments else "/"
        target = self.resolve_path(target_arg)

        if not self.is_directory(target):
            raise ValueError(f"cd: '{target_arg}': no such directory")

        self.previous_dir = self.current_dir
        self.current_dir = target
        self.write_output(f"Current directory: /{self.current_dir}\n")

    # Implement echo
    def command_echo(self, arguments):
        self.write_output(" ".join(arguments) + "\n")
        return True

    # Print file lines in reverse order
    def command_tac(self, arguments):
        if not arguments:
            raise ValueError("Usage: tac <file> [file ...]")

        for file_path in arguments:
            target = self.resolve_path(file_path)
            item = self.vfs.get(target)

            if item is None or item["type"] != "file":
                raise ValueError(f"tac: '{file_path}': no such file")

            lines = item["content"].splitlines()
            self.write_output("\n".join(reversed(lines)) + ("\n" if lines else ""))

    # Search VFS entries by path and optional file-name pattern
    def command_find(self, arguments):
        if len(arguments) == 0:
            start_path = self.current_dir
            pattern = "*"
        elif len(arguments) == 1:
            start_path = self.resolve_path(arguments[0])
            pattern = "*"
        elif len(arguments) == 2 and arguments[0] == "-name":
            start_path = self.current_dir
            pattern = arguments[1]
        elif len(arguments) == 3 and arguments[1] == "-name":
            start_path = self.resolve_path(arguments[0])
            pattern = arguments[2]
        else:
            raise ValueError("Usage: find [path] [-name pattern]")

        if start_path not in self.vfs:
            raise ValueError(f"find: '{start_path}': no such path")
        if self.vfs[start_path]["type"] != "dir":
            raise ValueError(f"find: '{start_path}' is not a directory")

        prefix = start_path + "/" if start_path else ""
        matches = []
        for path in sorted(self.vfs):
            if path == start_path:
                continue
            if start_path and not path.startswith(prefix):
                continue
            name = path.rsplit("/", 1)[-1]
            if fnmatch.fnmatch(name, pattern):
                matches.append("/" + path)

        if matches:
            self.write_output("\n".join(matches) + "\n")
        else:
            self.write_output("No matches found.\n")

    # Execute a command and return whether it succeeded
    def execute_command(self, command_text):
        if not command_text.strip():
            return True

        try:
            parts = shlex.split(command_text)
        except ValueError as error:
            self.write_output(f"Error: {error}\n")
            self.log_command(command_text, "ERROR", str(error))
            return False

        command = parts[0]
        arguments = parts[1:]

        try:
            if command == "exit":
                self.log_command(command, "OK", "")
                self.root.destroy()
                return True

            elif command == "ls":  # UPDATED
                self.command_ls(arguments)  # NEW

            elif command == "cd":  # UPDATED
                self.command_cd(arguments)  # NEW

            elif command == "echo":  # NEW
                self.command_echo(arguments)

            elif command == "tac":  # NEW
                self.command_tac(arguments)

            elif command == "find":  # NEW
                self.command_find(arguments)

            # Save the VFS to the specified CSV file
            elif command == "vfs-save":
                if len(arguments) != 1:
                    error_message = "Usage: vfs-save <path>"
                    self.write_output(f"Error: {error_message}\n")
                    self.log_command(command, "ERROR", error_message)
                    return False

                success = self.save_vfs(arguments[0])
                self.log_command(
                    command,
                    "OK" if success else "ERROR",
                    "" if success else "Failed to save VFS"
                )
                return success

            # Reset the VFS to its default state
            elif command == "vfs-init":
                success = self.init_vfs()
                self.log_command(
                    command,
                    "OK" if success else "ERROR",
                    "" if success else "Failed to initialize VFS"
                )
                return success

            else:
                error_message = f"Unknown command '{command}'"
                self.write_output(f"Error: {error_message}\n")
                self.log_command(command, "ERROR", error_message)
                return False

            self.log_command(command, "OK", "")
            return True

        except Exception as error:
            self.write_output(f"Error: {error}\n")
            self.log_command(command, "ERROR", str(error))
            return False

    # Write command events to an XML log file
    def log_command(self, command, status, message):
        log_path = Path(self.config["log_path"])

        # Create the log directory if necessary
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Load an existing XML log or create a new one
        if log_path.exists():
            try:
                tree = ET.parse(log_path)
                root = tree.getroot()
            except ET.ParseError:
                root = ET.Element("log")
                tree = ET.ElementTree(root)
        else:
            root = ET.Element("log")
            tree = ET.ElementTree(root)

        # Record the username, command, result, and error message
        event = ET.SubElement(root, "event")
        ET.SubElement(event, "username").text = getpass.getuser()
        ET.SubElement(event, "command").text = command
        ET.SubElement(event, "status").text = status
        ET.SubElement(event, "message").text = message

        # Save the updated XML file
        ET.indent(tree, space="    ")
        tree.write(log_path, encoding="utf-8", xml_declaration=True)

    # Execute commands from the startup script
    def run_startup_script(self):
        script_path = Path(self.config["script_path"])

        if not script_path.exists():
            self.write_output(
                f"Startup script error: file not found: {script_path}\n"
            )
            return

        try:
            with script_path.open("r", encoding="utf-8") as script:
                for line_number, line in enumerate(script, start=1):
                    command_text = line.strip()

                    # Skip empty lines
                    if not command_text:
                        continue

                    # Display the command as if entered by the user
                    self.write_output(f"> {command_text}\n")

                    # Stop at the first failed command
                    if not self.execute_command(command_text):
                        self.write_output(
                            "Startup script stopped: "
                            f"error on line {line_number}.\n"
                        )
                        return

        except OSError as error:
            self.write_output(f"Startup script error: {error}\n")

    # Add text to the output area
    def write_output(self, text):
        self.output.config(state="normal")
        self.output.insert(tk.END, text)
        self.output.config(state="disabled")
        self.output.see(tk.END)


# Read command-line arguments
def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Shell emulator configuration"
    )

    parser.add_argument("--vfs", help="Path to the VFS file")
    parser.add_argument("--log", help="Path to the XML log file")
    parser.add_argument("--script", help="Path to the startup script")
    parser.add_argument(
        "--config",
        default="config.toml",
        help="Path to the TOML configuration file"
    )

    return parser.parse_args()


# Load TOML settings and apply command-line overrides
def load_config(args):
    config_path = Path(args.config)

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}"
        )

    with config_path.open("rb") as file:
        config = tomllib.load(file)

    # Fill in defaults for optional TOML settings
    config.setdefault("vfs_path", "virtual_fs.csv")
    config.setdefault("log_path", "shell_log.xml")
    config.setdefault("script_path", "startup.txt")

    # Command-line arguments override TOML values
    if args.vfs is not None:
        config["vfs_path"] = args.vfs

    if args.log is not None:
        config["log_path"] = args.log

    if args.script is not None:
        config["script_path"] = args.script

    return config


# Application entry point
def main():
    args = parse_arguments()

    try:
        config = load_config(args)
    except (OSError, tomllib.TOMLDecodeError) as error:
        print(f"Configuration error: {error}")
        return

    # Display the effective configuration for debugging
    print("Effective configuration:")
    print(f"VFS path: {config['vfs_path']}")
    print(f"Log path: {config['log_path']}")
    print(f"Startup script: {config['script_path']}")
    print(f"Config file: {args.config}")

    root = tk.Tk()
    app = ShellEmulator(root, config)
    root.mainloop()


if __name__ == "__main__":
    main()

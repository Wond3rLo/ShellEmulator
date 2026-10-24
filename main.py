
import tkinter as tk
import shlex
import argparse
import tomllib
import xml.etree.ElementTree as ET
import getpass
from pathlib import Path


class ShellEmulator:
    # Accept configuration and command-line parameters
    def __init__(self, root, config):
        self.root = root
        self.config = config

        self.root.title(f"Shell Emulator - {Path(config['vfs_path']).name}")
        self.root.geometry("700x450")

        self.output = tk.Text(root, state="disabled")
        self.output.pack(fill="both", expand=True, padx=10, pady=10)

        self.command_entry = tk.Entry(root)
        self.command_entry.pack(fill="x", padx=10, pady=(0, 10))
        self.command_entry.bind("<Return>", self.run_command)

        # Run the startup script after the window opens
        self.root.after(100, self.run_startup_script)

    # Process commands entered by the user
    def run_command(self, event=None):
        command_text = self.command_entry.get()
        self.command_entry.delete(0, tk.END)

        self.write_output(f"> {command_text}\n")
        self.execute_command(command_text)

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

            elif command == "ls":
                self.write_output(
                    f"Command: ls\nArguments: {arguments}\n"
                )

            elif command == "cd":
                self.write_output(
                    f"Command: cd\nArguments: {arguments}\n"
                )

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

    # NEW: Execute commands from the startup script
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

import tkinter as tk
import shlex

class ShellEmulator:
    def __init__(self, root):
        self.root = root

        #setting title and size
        self.root.title("Shell Emulator - virtual_fs.csv")
        self.root.geometry("700x450")

        #output and input
        self.output = tk.Text(root, state="disabled")
        self.output.pack(fill="both", expand=True, padx=10, pady=10)
        self.command_entry = tk.Entry(root)
        self.command_entry.pack(fill="x", padx=10, pady=(0, 10))
        self.command_entry.bind("<Return>", self.run_command)

    #creating space for command entry
    def run_command(self, event=None):
        command_text = self.command_entry.get()
        self.command_entry.delete(0, tk.END)
        self.write_output(f"> {command_text}\n")
        if not command_text.strip():
            return
        try:
            parts = shlex.split(command_text)
        except ValueError as error:
            self.write_output(f"Error: {error}\n")
            return
        command = parts[0]
        arguments = parts[1:]

        if command == "exit":
            self.root.destroy()
        elif command == "ls":
            self.write_output(f"Command: ls\nArguments: {arguments}\n")
        elif command == "cd":
            self.write_output(f"Command: cd\nArguments: {arguments}\n")
        else:
            self.write_output(f"Error: unknown command '{command}'\n")

    #adding text in the output
    def write_output(self, text):
        self.output.config(state="normal")
        self.output.insert(tk.END, text)
        self.output.config(state="disabled")
        self.output.see(tk.END)

root = tk.Tk()
app = ShellEmulator(root)
root.mainloop()
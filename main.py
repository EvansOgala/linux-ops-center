import tkinter as tk

from ui import LinuxOpsCenterApp


def main():
    root = tk.Tk()
    try:
        root.tk.call("wm", "class", root._w, "LinuxOpsCenter")
    except tk.TclError:
        pass
    LinuxOpsCenterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

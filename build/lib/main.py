#!/usr/bin/env python3

import tkinter as tk

from app import MainWindow


def main():
    root = tk.Tk()
    MainWindow(root)

    import sys
    import os

    root.lift()
    root.attributes("-topmost", True)
    root.after_idle(root.attributes, "-topmost", False)

    if sys.platform == "darwin":
        os.system(f'''/usr/bin/osascript -e 'tell application "System Events" to set frontmost of the first process whose unix id is {os.getpid()} to true' ''')

    root.mainloop()


if __name__ == "__main__":
    main()

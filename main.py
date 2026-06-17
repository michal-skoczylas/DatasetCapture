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
        os.system('''/usr/bin/osascript -e 'tell app "Finder" to set frontmost of process "Python" to true' ''')

    root.mainloop()


if __name__ == "__main__":
    main()

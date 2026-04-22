from __future__ import annotations

import tkinter as tk

from ui import PopulationApp


def main() -> None:
    root = tk.Tk()
    root.title("Population Evolution Simulator")
    root.geometry("1380x900")
    root.minsize(1180, 760)
    PopulationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

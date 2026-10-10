"""The application layer: what the tools do, with no UI toolkit in it.

Both the Tk window and the coming web window (#25) drive the tools through
here, so validation, background jobs, progress and result messages behave
the same whichever UI is in front.
"""

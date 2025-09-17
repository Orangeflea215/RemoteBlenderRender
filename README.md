Only requirements are that Python and PySide6 be installed (after installing Python, run pip install PySide6).

Run python qtRemoteRender.py, choose a blender file, optionally pack all resources and make all references local, connect to a remote machine using SSH and transfer the file, then specify your render options and hit render.

After the render is complete hit view render to pull the file to a local temp directory and open in the built-in image viewer (from PySide6 website).

Windows only.

![Main interface screenshot](/Screenshots/Main_Interface.png?raw=true "Main Interface")

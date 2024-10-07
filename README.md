AppLauncher
AppLauncher is a Python-based program that allows users to manage and launch their installed applications with a user-friendly graphical interface. The program provides a tray icon for easy access, allows custom attributes for programs, and offers features like adding, editing, deleting, and launching programs from a list.

Features
Program Management: Add, edit, delete, and manage programs using a simple GUI interface.
Search Functionality: Easily search for programs by name.
Tray Icon Support: Minimize the program to the system tray and access it from there.
Automatic Program Launching: Set specific programs to launch automatically on startup.
Program Attributes: Assign custom attributes (e.g., sys, autorun) to programs for additional functionality.
Log Files: Track program launches and errors with a rotating log system.
Console Control: Show or hide the console window, and prevent accidental closure.
Screenshot Functionality: Take and open screenshots with a single click.
Installation
Clone the Repository:

bash
Копіювати код
git clone https://github.com/yourusername/applauncher.git
cd applauncher
Install Required Libraries:

The project depends on several external libraries. Install them using pip:

bash
Копіювати код
pip install -r requirements.txt
The following key libraries are used:

tkinter - For the graphical interface.
psutil - To manage processes.
pystray - For system tray functionality.
Pillow - For handling images and screenshots.
Run the Program:

Once installed, you can start the application using:

bash
Копіювати код
python 11.py
Usage
Adding a Program:

Use the 'Add Program' option in the File menu to add a program to the launcher. You will be prompted to provide the program name, path, and optional attributes.
Launching a Program:

Double-click on any listed program to launch it.
Editing or Deleting Programs:

Right-click on a program to edit or delete it.
Search Programs:

Use the search bar at the top to filter programs by name.
Changing Interface Color:

Go to the 'Interface' menu to customize the background color.
System Tray:

Minimize the application to the tray, from where it can be restored or exited.
Configuration
The application uses a config.json file to store settings such as program attributes and interface colors. You can manually edit this file to customize behavior.

Example config.json
json
Копіювати код
{
  "programs_file": "programs.json",
  "attributes": {
    "sys": "command:some_command",
    "autorun": "file:path_to_file"
  },
  "color": "#FFFFFF"
}
Logging
AppLauncher logs its activities in launcher.log, with log rotation enabled to manage log size. Logs include information such as program launches, errors, and status updates.

Contributing
Contributions are welcome! Feel free to submit a pull request or open an issue if you have any suggestions or bug reports.

License
This project is licensed under the MIT License.

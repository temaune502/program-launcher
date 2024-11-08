Launcher Application
This is a Python-based launcher application that allows centralized management of various programs on your system. With a focus on automation and flexibility, it provides options to run, monitor, suspend, and control applications from a user-friendly interface.

Features
Launch and Manage Programs: Start and stop programs, track their running status, and manage specific attributes such as autorun and self-console mode.
Hidden Mode: Toggle between showing and hiding specific programs for a more organized interface.
Customizable Interface: Choose interface colors and adjust display settings for hidden programs to personalize your experience.
Hotkey Integration: Define global hotkeys for various actions, allowing fast access and control over frequently used commands.
Tray Icon Support: Minimize the application to the system tray with a quick-access menu for easy program management.
Client-Server Communication: Integrated with a client-server model to send and receive messages and execute remote commands.
Logging and Error Tracking: Logs all actions and errors in launcher.log for troubleshooting and auditing purposes.
Configuration
To configure the application:

Edit config.json:

Set client_name for client-server identification.
Adjust dev_mode, use_hotkey, and console_work to enable or disable specific features.
Set color for the interface color code (e.g., "#FFFFFF" for white).
Configure command hotkeys and commands dictionary for specific actions.
Program Attributes:

Programs can be assigned attributes such as:
sys: Essential system programs, which cannot be deleted.
autorun: Programs to automatically launch when the application starts.
hide: Programs to be hidden when in regular display mode.
Each program's attributes can be edited via the UI or directly in the configuration files.
Permissions and Restrictions:

Use use_black_list and use_white_list to control communication and command execution with specific clients.
Configure banned and white_list in config.json to allow or block clients based on client_name.
Usage
Run the application with:

bash
Копіювати код
python 26.py
Main Interface
Program List: Shows all programs with their statuses (running or stopped). Double-click on a program to start it.
Context Menu: Right-click a program in the list to access commands like start, stop, suspend, edit, or delete.
System Tray: Access controls directly from the system tray icon.
Console Mode
The application includes a console mode for command-line control (if console_work is enabled in config.json). Available commands include:

launch [program_name]: Start a specified program.
stop [program_name]: Stop a specified program.
help: Display a list of available commands and hotkeys.
disconnect_server: Disconnect from the server.
Hotkeys
Customize hotkeys for quick program launch, toggling visibility, or executing specific actions.
Configure hotkeys in config.json under the hotkeys section, linking keys to functions in the app.
Logging and Troubleshooting
The launcher.log file records important actions, errors, and system messages.
For troubleshooting:
Check if the required dependencies are installed.
Review log entries in launcher.log.
Verify config.json for any incorrect values or missing fields.
Dependencies
Ensure you have the following Python packages:

tkinter: For GUI elements
psutil: For process management
pystray: For system tray integration
Pillow (PIL): For image handling
keyboard: For hotkey integration
To install dependencies, run:

bash
Копіювати код
pip install -r requirements.txt
License
This project is licensed under the MIT License. See LICENSE for more information.

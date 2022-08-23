import os
from pathlib import Path
import bpy
import tempfile

bl_info = {
    "name": "Open with IDE",
    "author": "Andrew Stevenson",
    "version": (0, 1),
    "blender": (3, 0, 0),
    "location": "Text editor",
    # "description": "Adds a new Mesh Object",
    "warning": "",
    "doc_url": "",
    "category": "Text Editor",
}


class IDEPreferences(bpy.types.AddonPreferences):
    bl_idname: str = __name__

    ide_command: bpy.props.StringProperty(
        name="IDE command",
        description="The command to run to open the ide, use {file} to mean the temp file that is saved and opened",
        default="code {file}",
    )

    def draw(self, context):
        layout: bpy.types.UILayout = self.layout
        layout.prop(self, "ide_command")


def get_prefs() -> IDEPreferences:
    return bpy.context.preferences.addons[__name__].preferences


file = None
op = None


def update_text_timer():
    """Run every half a second, and if the blender text has been modified, save it to the file,\
    else if the ide has saved a new version of the file, load that"""
    global file
    global op

    if not op.bl_text_data:
        return update_text_timer.redraw_interval

    try:
        new_text = op.bl_text_data.as_string()
    except ReferenceError:
        op.finished = True
        return None
    if op.bl_text != new_text:
        with open(file, "w") as f:
            f.write(new_text)
            op.bl_text = new_text
        # print("different!")
        op.file_modify_time = os.path.getmtime(file)

    if op.file_modify_time != os.path.getmtime(file):
        op.bl_text_data.clear()
        with open(file, "r") as f:
            op.bl_text_data.write(f.read())
        op.bl_text = op.bl_text_data.as_string()
        op.file_modify_time = os.path.getmtime(file)
        # print("changed!")

    return update_text_timer.redraw_interval


update_text_timer.redraw_interval = None


class IDE_OT_open_with_ide(bpy.types.Operator):
    bl_idname = "ide.open_with_ide"
    bl_label = "Open with IDE"

    @classmethod
    def poll(cls, context):
        text_data = context.space_data.text
        return context.area.type == "TEXT_EDITOR" and text_data

    @property
    def bl_text_data(self) -> bpy.types.Text:
        return self.space_data.text

    def invoke(self, context, event):
        global file
        global op

        # if called when another instance of the operator is already running, stop it.
        if file:
            op.finished = True
            return {"FINISHED"}
        op = self

        # Create a temporary file for the IDE to edit.
        file = tempfile.mkstemp(text=True, suffix=".py", prefix="bl_ide_temp_")
        os.close(file[0])
        file = Path(file[1])

        # Set initial vars
        self.space_data = context.space_data
        self.bl_text = self.bl_text_data.as_string()
        self.finished = False
        self.file_modify_time = os.path.getmtime(file)

        with open(file, "w") as f:
            f.write(self.bl_text)

        # Run the ide command, and start the file checking timer
        os.system(get_prefs().ide_command.replace("{file}", str(file)))
        update_text_timer.redraw_interval = .5
        bpy.app.timers.register(update_text_timer, first_interval=1)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):

        global file
        if event.type in {"ESC"} or self.finished:
            if bpy.app.timers.is_registered:
                try:
                    bpy.app.timers.unregister(update_text_timer)
                except ValueError:
                    pass
            os.remove(str(file))
            file = None
            return {"FINISHED"}
        return {"PASS_THROUGH"}


def header_draw(self, context):
    """Add a button to the header of the text editor"""
    layout: bpy.types.UILayout = self.layout
    global file
    layout.operator(IDE_OT_open_with_ide.bl_idname, text="", icon="GREASEPENCIL", depress=file is not None)


classes = [
    IDE_OT_open_with_ide,
    IDEPreferences,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TEXT_HT_header.append(header_draw)


def unregister():
    if bpy.app.timers.is_registered(update_text_timer):
        bpy.app.timers.unregister(update_text_timer)
    bpy.types.TEXT_HT_header.remove(header_draw)
    for cls in classes:
        bpy.utils.unregister_class(cls)

    for file in Path(tempfile.gettempdir()).iterdir():
        if file.name.startswith("bl_ide_temp_"):
            os.remove(file)

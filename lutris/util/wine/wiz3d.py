"""wiz3D, stereo 3D for Direct3D 9 games, placed in a Wine prefix"""

import os
import stat
import string
from gettext import gettext as _

from lutris.util import system
from lutris.util.wine.dll_manager import DLLManager

WIZ3D_DIR = "/usr/lib/wiz3d"
# The DXVK of the same system: it is the build that presents into the whole window
DXVK_DIR = "/usr/lib/dxvk"
DXVK_FOLDERS = {"x64": "wine64", "x86": "wine32"}
# The proxy takes the place of Direct3D 9, the wrapper and the output plug-in sit beside it, where
# the proxy looks for them (next to its own file), and the real Direct3D 9 is d3d9_real.dll.
WRAPPER_FILES = ("S3DWrapperD3D9.dll", "S3DAPI.dll", "ZLOg.dll")
DATA_FILES = ("wiz3D_Config.xml", "BaseProfile.xml", "OutputMethods")
REAL_DLL = "d3d9_real.dll"

# The pictures a game may draw itself, as DXVK's dxvk.stereoInput names them (stereo-layer's Layout names): the
# frame packings of H.264 Table D-8 and Matroska StereoMode, and the anaglyphs; DXVK unpacks each one to full side by
# side, left eye first, when presenting.
NATIVE_LAYOUTS = (
    ("sideBySide", _("Side by side")),
    ("sideBySideQuincunx", _("Side by side, quincunx")),
    ("topAndBottom", _("Top and bottom")),
    ("rows", _("Rows (line interleaved)")),
    ("columns", _("Columns")),
    ("checkerboard", _("Checkerboard")),
    ("frameSequential", _("Frame sequential (alternate frames)")),
    ("anaglyphRedCyan", _("Anaglyph, red and cyan")),
    ("anaglyphGreenMagenta", _("Anaglyph, green and magenta")),
    ("anaglyphAmberBlue", _("Anaglyph, amber and blue")),
)


def dxvk_config(layout, right_first, config=None):
    """DXVK_CONFIG with the stereo input added to what is already there"""
    ours = "dxvk.stereoInput = %s; dxvk.stereoInputRightFirst = %s" % (layout, "True" if right_first else "False")
    return ours if not config else config.rstrip("; ") + "; " + ours


def windows_path(prefix, path):
    """The Unix path as Wine names it to Windows code: through the drive of the prefix that holds it (the
    longest folder, the lowest letter, as Wine's own lookup does), or as \\\\?\\unix\\... when no drive does,
    which Wine takes everywhere a path goes. Nothing here needs the Z: drive."""
    path = os.path.abspath(path)
    drives = {}
    for letter in string.ascii_lowercase:
        try:
            info = os.stat(os.path.join(prefix, "dosdevices", letter + ":"))
        except OSError:
            continue
        drives.setdefault((info.st_dev, info.st_ino), letter)
    folder = path
    while True:
        try:
            info = os.stat(folder)
            if stat.S_ISDIR(info.st_mode) and (info.st_dev, info.st_ino) in drives:
                rest = path[len(folder):].lstrip("/")
                return drives[(info.st_dev, info.st_ino)].upper() + ":\\" + rest.replace("/", "\\")
        except OSError:
            pass
        if folder == "/":
            break
        folder = os.path.dirname(folder)
    return "\\\\?\\unix" + path.replace("/", "\\")


class Wiz3DManager(DLLManager):
    """Puts wiz3D's Direct3D 9 proxy in the prefix, in front of the system's DXVK.

    Everything is a symbolic link to the system's copy, as DXVK's files are, so nothing is copied and
    turning the component off removes exactly what it made. It must run after the DXVK manager, which
    puts DXVK's own d3d9.dll back when the component is turned off."""

    name = "wiz3d"
    human_name = "wiz3D"
    managed_dlls = ("d3d9",)
    archs = {32: "x86", 64: "x64"}  # the folders of the system's copy
    releases_url = NotImplemented

    @property
    def base_dir(self):
        return WIZ3D_DIR

    @property
    def path(self):
        return WIZ3D_DIR

    @property
    def versions(self):
        return ["system"] if system.path_exists(WIZ3D_DIR) else []

    @property
    def version(self):
        return "system" if system.path_exists(WIZ3D_DIR) else None

    @staticmethod
    def get_dxvk_dll(arch):
        return os.path.join(DXVK_DIR, DXVK_FOLDERS[arch], "d3d9.dll.so")

    def archs_in_use(self):
        """The architectures of the prefix, with the ones the packages have no files for left out"""
        wanted = ["x64", "x86"] if self.wine_arch == "win64" else ["x86"]
        return [arch for arch in wanted if self.has_files(arch)]

    def has_files(self, arch):
        return system.path_exists(os.path.join(WIZ3D_DIR, arch, "d3d9.dll")) and system.path_exists(self.get_dxvk_dll(arch))

    def is_available(self):
        """True if wiz3D and the system's DXVK have files for the prefix's main architecture"""
        return self.has_files("x64" if self.wine_arch == "win64" else "x86")

    def can_enable(self):
        return self.is_available()

    def get_enabling_dll_overrides(self):
        return {"d3d9": "n"}

    @staticmethod
    def is_managed_dll(dll_path):
        """Check if a given DLL path is a link made by this component"""
        return os.path.islink(dll_path) and os.readlink(dll_path).startswith((WIZ3D_DIR + "/", DXVK_DIR + "/"))

    def _link(self, source, target):
        if os.path.lexists(target):
            os.remove(target)
        system.create_symlink(source, target)

    def enable(self):
        archs = self.archs_in_use()
        for system_dir, arch, _dll in self._iter_dlls():
            if arch not in archs:
                continue
            # DXVK's own d3d9.dll is replaced by the proxy; the real one is the system's DXVK
            self._link(self.get_dxvk_dll(arch), os.path.join(system_dir, REAL_DLL))
            for name in ("d3d9.dll",) + WRAPPER_FILES + DATA_FILES:
                self._link(os.path.join(WIZ3D_DIR, arch, name), os.path.join(system_dir, name))

    def disable(self):
        for system_dir, _arch, _dll in self._iter_dlls():
            proxy, real = os.path.join(system_dir, "d3d9.dll"), os.path.join(system_dir, REAL_DLL)
            if self.is_managed_dll(real):
                # The real Direct3D 9 takes its name back, so the prefix never lacks a d3d9.dll; the DXVK
                # manager relinks it to the version the game uses when that is another one.
                if self.is_managed_dll(proxy) or not os.path.lexists(proxy):
                    if os.path.lexists(proxy):
                        os.remove(proxy)
                    os.rename(real, proxy)
                else:
                    os.remove(real)
            for name in WRAPPER_FILES + DATA_FILES:
                path = os.path.join(system_dir, name)
                if self.is_managed_dll(path):
                    os.remove(path)

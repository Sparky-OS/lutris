import os
import tempfile
import unittest
from unittest import mock

from lutris.util import stereo_games
from lutris.util.wine import dxvk, wiz3d
from lutris.util.wine.dxvk import DXVKManager
from lutris.util.wine.wiz3d import Wiz3DManager

README = """
- **Excluded (Native SBS/TAB):** *Crysis 2*, *Trine 1*, *Two Worlds II*.
Some other line with *emphasis* in it.
- **Excluded (Native SBS/TAB):** *DOOM 3: BFG Edition*.
"""


def tree(root):
    """Every file and link under root, with the link targets"""
    result = {}
    for folder, dirs, files in os.walk(root):
        for name in dirs + files:
            path = os.path.join(folder, name)
            result[os.path.relpath(path, root)] = os.readlink(path) if os.path.islink(path) else "file"
    return result


class TestWiz3DManager(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = self.temp.name
        self.wiz3d_dir = os.path.join(root, "wiz3d")
        self.dxvk_dir = os.path.join(root, "dxvk")
        for arch, folder in (("x64", "wine64"), ("x86", "wine32")):
            os.makedirs(os.path.join(self.wiz3d_dir, arch, "OutputMethods"))
            for name in ("d3d9.dll", "S3DWrapperD3D9.dll", "S3DAPI.dll", "ZLOg.dll", "wiz3D_Config.xml", "BaseProfile.xml"):
                open(os.path.join(self.wiz3d_dir, arch, name), "w", encoding="utf-8").close()
            os.makedirs(os.path.join(self.dxvk_dir, folder))
            open(os.path.join(self.dxvk_dir, folder, "d3d9.dll.so"), "w", encoding="utf-8").close()
        self.prefix = os.path.join(root, "prefix")
        for folder in ("system32", "syswow64"):
            os.makedirs(os.path.join(self.prefix, "drive_c", "windows", folder))
            # what the DXVK manager leaves: a link to a DXVK of the Lutris runtime
            os.symlink("/runtime/dxvk/v2/%s/d3d9.dll" % folder, os.path.join(self.prefix, "drive_c", "windows", folder, "d3d9.dll"))
        patches = (
            mock.patch.object(wiz3d, "WIZ3D_DIR", self.wiz3d_dir),
            mock.patch.object(wiz3d, "DXVK_DIR", self.dxvk_dir),
        )
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_enable_puts_the_proxy_in_front_of_the_system_dxvk(self):
        Wiz3DManager(self.prefix).enable()
        system32 = os.path.join(self.prefix, "drive_c", "windows", "system32")
        self.assertEqual(os.readlink(os.path.join(system32, "d3d9.dll")), os.path.join(self.wiz3d_dir, "x64", "d3d9.dll"))
        self.assertEqual(os.readlink(os.path.join(system32, "d3d9_real.dll")), os.path.join(self.dxvk_dir, "wine64", "d3d9.dll.so"))
        syswow64 = os.path.join(self.prefix, "drive_c", "windows", "syswow64")
        self.assertEqual(os.readlink(os.path.join(syswow64, "d3d9_real.dll")), os.path.join(self.dxvk_dir, "wine32", "d3d9.dll.so"))
        self.assertTrue(os.path.islink(os.path.join(system32, "OutputMethods")))

    def test_disable_removes_what_enable_made_and_nothing_else(self):
        before = tree(self.prefix)
        manager = Wiz3DManager(self.prefix)
        manager.enable()
        self.assertNotEqual(tree(self.prefix), before)
        manager.disable()
        # only DXVK's own d3d9.dll was replaced; the DXVK manager puts it back
        after = tree(self.prefix)
        del before["drive_c/windows/system32/d3d9.dll"]
        del before["drive_c/windows/syswow64/d3d9.dll"]
        self.assertEqual(after, before)

    def test_architectures_without_files_are_left_out(self):
        os.remove(os.path.join(self.dxvk_dir, "wine32", "d3d9.dll.so"))
        manager = Wiz3DManager(self.prefix)
        self.assertEqual(manager.archs_in_use(), ["x64"])
        manager.enable()
        self.assertFalse(os.path.lexists(os.path.join(self.prefix, "drive_c", "windows", "syswow64", "d3d9_real.dll")))

    def test_not_available_without_the_packages(self):
        os.remove(os.path.join(self.wiz3d_dir, "x64", "d3d9.dll"))
        self.assertFalse(Wiz3DManager(self.prefix).is_available())


class TestSystemDXVK(unittest.TestCase):
    def test_system_version_names_the_dll_so_files(self):
        manager = DXVKManager("/prefix", version=dxvk.SYSTEM_VERSION)
        self.assertEqual(manager.path, dxvk.SYSTEM_DIR)
        self.assertEqual(manager.get_dll_path("x64", "d3d9"), "/usr/lib/dxvk/wine64/d3d9.dll.so")
        self.assertEqual(manager.get_dll_path("x32", "dxgi"), "/usr/lib/dxvk/wine32/dxgi.dll.so")
        self.assertFalse(manager.is_recommended_version(dxvk.SYSTEM_VERSION))


class TestStereoGames(unittest.TestCase):
    def test_parse_list(self):
        self.assertEqual(
            stereo_games.parse_list(README), {"crysis 2", "trine 1", "two worlds ii", "doom 3: bfg edition"}
        )

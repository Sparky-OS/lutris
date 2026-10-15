"""DXVK helper module"""

import os
import shutil

from lutris.util import system
from lutris.util.graphics import vkquery
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.wine.dll_manager import DLLManager

REQUIRED_VULKAN_API_VERSION = vkquery.vk_make_version(1, 3, 0)

# The DXVK of the system, as Debian packages it: a folder for each architecture, the DLLs named *.dll.so
SYSTEM_VERSION = "system"
SYSTEM_DIR = "/usr/lib/dxvk"
SYSTEM_FOLDERS = {"x64": "wine64", "x32": "wine32"}


class DXVKManager(DLLManager):
    name = "dxvk"
    human_name = "DXVK"
    managed_dlls = ("dxgi", "d3d11", "d3d10core", "d3d9", "d3d8")
    releases_url = "https://api.github.com/repos/lutris/dxvk/releases"

    @property
    def versions(self):
        versions = super().versions
        if os.path.isdir(os.path.join(SYSTEM_DIR, SYSTEM_FOLDERS["x64"])):
            versions.append(SYSTEM_VERSION)
        return versions

    @property
    def path(self):
        if self._version == SYSTEM_VERSION:
            return SYSTEM_DIR
        return super().path

    def is_recommended_version(self, version):
        # The system's DXVK is there to be chosen, not to be the default
        if version == SYSTEM_VERSION:
            return False
        return self._is_recommended_downloaded_version(version)

    def get_dll_path(self, arch, dll_name):
        if self._version == SYSTEM_VERSION:
            return os.path.join(SYSTEM_DIR, SYSTEM_FOLDERS[arch], "%s.dll.so" % dll_name)
        return super().get_dll_path(arch, dll_name)

    def enable_dll(self, system_dir, arch, dll_path):
        """The system's files are named d3d9.dll.so; the link in the prefix is d3d9.dll, as for every version"""
        if self._version != SYSTEM_VERSION:
            return super().enable_dll(system_dir, arch, dll_path)
        dll = os.path.basename(dll_path)[: -len(".so")]
        if not system.path_exists(dll_path):
            return self.disable_dll(system_dir, arch, dll[: -len(".dll")])
        wine_dll_path = os.path.join(system_dir, dll)
        if system.path_exists(wine_dll_path):
            if not self.is_managed_dll(wine_dll_path) and not os.path.islink(wine_dll_path):
                shutil.move(wine_dll_path, wine_dll_path + ".orig")
            else:
                os.remove(wine_dll_path)
        system.create_symlink(dll_path, wine_dll_path)

    def can_enable(self):
        if os.environ.get("LUTRIS_NO_VKQUERY"):
            return True
        return LINUX_SYSTEM.is_vulkan_supported()

    def _is_recommended_downloaded_version(self, version):
        # DXVK 2.x and later require Vulkan 1.3, so if that is lacking
        # we default to 1.x.
        if os.environ.get("LUTRIS_NO_VKQUERY"):
            return True
        vulkan_api_version = vkquery.get_expected_api_version()
        if vulkan_api_version and vulkan_api_version < REQUIRED_VULKAN_API_VERSION:
            return version.startswith("v1.")
        return super().is_recommended_version(version)

    @staticmethod
    def is_managed_dll(dll_path):
        """Check if a given DLL path is provided by the component

        Very basic check to see if a dll contains the string "dxvk".
        """
        try:
            with open(dll_path, "rb") as file:
                prev_block_end = b""
                while True:
                    block = file.read(2 * 1024 * 1024)  # 2 MiB
                    if not block:
                        break
                    if b"dxvk" in prev_block_end + block[:4]:
                        return True
                    if b"dxvk" in block:
                        return True

                    prev_block_end = block[-4:]
        except OSError:
            pass
        return False

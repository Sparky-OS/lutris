import os
import tempfile
import unittest

from lutris.util.wine import wow64

PE32 = b"MZ" + bytes(0x3A) + (0x40).to_bytes(4, "little") + b"PE\0\0" + (0x14C).to_bytes(2, "little") + bytes(20)
PE64 = PE32.replace((0x14C).to_bytes(2, "little"), (0x8664).to_bytes(2, "little"))
NE = b"MZ" + bytes(0x3A) + (0x40).to_bytes(4, "little") + b"NE" + bytes(20)

# What Wine printed for a 16-bit program in a 64-bit prefix (SimCity Classic's setup, Wine 10.0)
WINEVDM_OUTPUT = """00dc:err:environ:init_peb starting L"C:\\\\windows\\\\syswow64\\\\winevdm.exe" in experimental wow64 mode
00dc:err:module:loader_init "krnl386.exe16" failed to initialize, aborting
00dc:err:module:loader_init Initializing dlls for L"C:\\\\windows\\\\syswow64\\\\winevdm.exe" failed, status c0000005
"""


class TestExeKind(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def write(self, name, data):
        path = os.path.join(self.temp.name, name)
        with open(path, "wb") as exe:
            exe.write(data)
        return path

    def test_kinds_from_the_header(self):
        self.assertEqual(wow64.exe_kind(self.write("a.exe", PE32)), "win32")
        self.assertEqual(wow64.exe_kind(self.write("b.exe", PE64)), "win64")
        self.assertEqual(wow64.exe_kind(self.write("c.exe", NE)), "win16")
        self.assertEqual(wow64.exe_kind(self.write("d.exe", b"MZ" + bytes(0x3E) + bytes(8))), "dos")
        self.assertIsNone(wow64.exe_kind(self.write("e.exe", b"not a program")))
        self.assertIsNone(wow64.exe_kind(os.path.join(self.temp.name, "missing.exe")))
        self.assertIsNone(wow64.exe_kind(None))


class TestFailedInWow64(unittest.TestCase):
    def test_a_16_bit_program_fails_by_its_kind(self):
        self.assertIn("16-bit", wow64.failed_in_wow64("win16", 0, 100, ""))

    def test_wines_words_are_evidence_whatever_the_status(self):
        reason = wow64.failed_in_wow64("win32", 0, 200, WINEVDM_OUTPUT)
        self.assertIn("krnl386.exe16", reason)

    def test_the_mode_line_alone_is_not_evidence(self):
        self.assertIsNone(wow64.failed_in_wow64("win32", 0, 2, WINEVDM_OUTPUT.splitlines()[0]))

    def test_a_quick_bad_status_is_evidence(self):
        self.assertIn("status 5", wow64.failed_in_wow64("win32", 5, 3, ""))

    def test_a_quick_clean_end_is_not(self):
        self.assertIsNone(wow64.failed_in_wow64("win32", 0, 2, ""))

    def test_a_long_run_is_not(self):
        self.assertIsNone(wow64.failed_in_wow64("win32", 5, 600, ""))

    def test_a_64_bit_program_never_is(self):
        self.assertIsNone(wow64.failed_in_wow64("win64", 5, 1, WINEVDM_OUTPUT))

    def test_the_fallback_prefix_is_beside_the_prefix(self):
        self.assertEqual(wow64.fallback_prefix("/games/wine/old/"), "/games/wine/old-win32")


if __name__ == "__main__":
    unittest.main()

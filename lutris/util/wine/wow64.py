"""Whether a 32-bit game ran in a 64-bit prefix, from the evidence a run leaves

Wine runs a 32-bit program in a 64-bit prefix in its WoW64 mode, which cannot run a 16-bit
program at all and leaves some older games crashing. A 32-bit prefix beside the 64-bit one
runs them. The run counts as failed on evidence only: a 16-bit program, Wine's own words about
the mode in the output, or an end within a few seconds with a status that is not 0. A quick
end with status 0 and nothing said is the game's own doing and is not one."""

import os
from typing import Optional

# Seconds within which an end with a bad status counts as a failure
FAILURE_SECONDS = 30

# What Wine prints when the mode cannot run a program or the program dies in it: the 16-bit
# loader, the exception dispatcher. Each one in the output is evidence by itself.
WOW64_EVIDENCE = (
    "Bad EXE format",
    'winevdm.exe" failed',
    'krnl386.exe16" failed to initialize',
    "failed to initialize, aborting",
    "unable to dispatch exception",
    "Exception frame is not in stack limits",
    "Unhandled exception",
    "unhandled page fault",
    "stack overflow",
)


def exe_kind(path: Optional[str]) -> Optional[str]:
    """What a program is, from its own header: 'win16' (an NE program), 'win32', 'win64',
    'dos' (MZ with nothing newer behind it), or None for a file that is not a Windows program."""
    if not path:
        return None
    try:
        with open(path, "rb") as exe:
            head = exe.read(0x40)
            if head[:2] != b"MZ" or len(head) < 0x40:
                return None
            exe.seek(int.from_bytes(head[0x3C:0x40], "little"))
            signature = exe.read(6)
    except (OSError, ValueError):
        return None
    if signature[:2] == b"NE":
        return "win16"
    if signature[:4] == b"PE\0\0":
        return {0x14C: "win32", 0x8664: "win64", 0xAA64: "win64"}.get(int.from_bytes(signature[4:6], "little"))
    return "dos"


def failed_in_wow64(kind: Optional[str], status: Optional[int], seconds: float, output: str) -> Optional[str]:
    """Why a run of a 32-bit (or 16-bit) program in a 64-bit prefix counts as failed, or None"""
    if kind not in ("win16", "win32", "dos"):
        return None
    if kind == "win16":
        return "it is a 16-bit program, which the 64-bit prefix (Wine's WoW64 mode) does not run"
    said = [line for line in output.splitlines() if any(word.lower() in line.lower() for word in WOW64_EVIDENCE)]
    if said:
        return 'Wine said "%s"' % said[0].strip()[:160]
    if status not in (None, 0) and seconds < FAILURE_SECONDS:
        return "it ended after %d seconds with status %d" % (seconds, status)
    return None


def fallback_prefix(prefix: str) -> str:
    """The 32-bit prefix that stands in for a 64-bit one: a sibling folder named after it"""
    return prefix.rstrip(os.sep) + "-win32"

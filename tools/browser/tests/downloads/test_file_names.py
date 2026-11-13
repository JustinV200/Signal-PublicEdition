"""Download file names: the page's suggestion never leaves the folder or overwrites a file."""

import pytest

from browser_tool.downloads import reserve_path, safe_file_name


@pytest.mark.parametrize(
    ("suggested", "expected"),
    [
        ("lab 3.ipynb", "lab 3.ipynb"),
        ("Résumé.pdf", "Résumé.pdf"),
        ("../../etc/passwd", "_.._etc_passwd"),
        (r"..\..\Windows\win.ini", "_.._Windows_win.ini"),
        (r"C:\Users\x\evil.exe", "C__Users_x_evil.exe"),
        ("..", "download"),
        (" . ", "download"),
        ("", "download"),
        (".hidden", "hidden"),
        ("trailing.  ", "trailing"),
        ('a<b>c:d"e|f?g*h', "a_b_c_d_e_f_g_h"),
        ("tab\there\x00.txt", "tab_here_.txt"),
        ("file.txt:stream", "file.txt_stream"),
        ("CON", "_CON"),
        ("con.txt", "_con.txt"),
        ("Nul .tar.gz", "_Nul .tar.gz"),
        ("COM1.ipynb", "_COM1.ipynb"),
        ("lpt9", "_lpt9"),
        ("COM\u00b2.txt", "_COM\u00b2.txt"),
        ("CONSOLE.txt", "CONSOLE.txt"),
        ("a‮fdp.exe", "a_fdp.exe"),
        ("lab​⁦.pdf﻿", "lab__.pdf_"),
        ("c1\x85.csv", "c1_.csv"),
        ("site.url", "site.url.download"),
        ("Share.SCF", "Share.SCF.download"),
        ("x.lnk", "x.lnk.download"),
        ("lib.Library-ms", "lib.Library-ms.download"),
        ("s.searchConnector-ms", "s.searchConnector-ms.download"),
        ("data.xlsx", "data.xlsx"),
        ("a" * 300 + ".ipynb", "a" * 114 + ".ipynb"),
    ],
)
def test_safe_file_name(suggested, expected):
    assert safe_file_name(suggested) == expected


def test_reserve_path_never_overwrites_and_stays_in_the_folder(tmp_path):
    folder = tmp_path / "downloads"
    first = reserve_path(folder, "lab.ipynb")
    first.write_text("keep me")
    second = reserve_path(folder, "lab.ipynb")
    third = reserve_path(folder, "lab.ipynb")
    assert [first.name, second.name, third.name] == ["lab.ipynb", "lab (1).ipynb", "lab (2).ipynb"]
    assert first.read_text() == "keep me"
    assert {path.parent for path in (first, second, third)} == {folder}
    with pytest.raises(ValueError):
        reserve_path(folder, "../escape.txt")

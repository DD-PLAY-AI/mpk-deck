from pathlib import Path

from mpk_deck.core.program_finder import InstalledProgram, list_installed_programs


def test_list_installed_programs_resolves_shortcuts_via_injected_resolver(tmp_path):
    programs_dir = tmp_path / "Programs"
    programs_dir.mkdir()
    (programs_dir / "Notepad++.lnk").write_bytes(b"")

    def resolver(lnk_path: Path) -> str:
        assert lnk_path.name == "Notepad++.lnk"
        return "C:/Program Files/Notepad++/notepad++.exe"

    result = list_installed_programs(search_dirs=[programs_dir], resolver=resolver)

    assert result == [InstalledProgram(name="Notepad++", path="C:/Program Files/Notepad++/notepad++.exe")]


def test_list_installed_programs_skips_unresolvable_shortcuts(tmp_path):
    programs_dir = tmp_path / "Programs"
    programs_dir.mkdir()
    (programs_dir / "Broken.lnk").write_bytes(b"")

    result = list_installed_programs(search_dirs=[programs_dir], resolver=lambda path: None)

    assert result == []


def test_list_installed_programs_scans_nested_folders(tmp_path):
    nested = tmp_path / "Programs" / "Accessories"
    nested.mkdir(parents=True)
    (nested / "Calculator.lnk").write_bytes(b"")

    result = list_installed_programs(search_dirs=[tmp_path / "Programs"], resolver=lambda path: "C:/calc.exe")

    assert result == [InstalledProgram(name="Calculator", path="C:/calc.exe")]


def test_list_installed_programs_dedupes_by_name_first_dir_wins(tmp_path):
    dir_a = tmp_path / "A"
    dir_b = tmp_path / "B"
    dir_a.mkdir()
    dir_b.mkdir()
    (dir_a / "App.lnk").write_bytes(b"")
    (dir_b / "App.lnk").write_bytes(b"")

    def resolver(lnk_path: Path) -> str:
        return "from-A" if "A" in lnk_path.parts else "from-B"

    result = list_installed_programs(search_dirs=[dir_a, dir_b], resolver=resolver)

    assert result == [InstalledProgram(name="App", path="from-A")]


def test_list_installed_programs_sorts_case_insensitively(tmp_path):
    programs_dir = tmp_path / "Programs"
    programs_dir.mkdir()
    (programs_dir / "zeta.lnk").write_bytes(b"")
    (programs_dir / "Alpha.lnk").write_bytes(b"")

    result = list_installed_programs(search_dirs=[programs_dir], resolver=lambda path: "x.exe")

    assert [p.name for p in result] == ["Alpha", "zeta"]


def test_list_installed_programs_missing_dir_is_skipped(tmp_path):
    result = list_installed_programs(search_dirs=[tmp_path / "does-not-exist"], resolver=lambda path: "x.exe")

    assert result == []

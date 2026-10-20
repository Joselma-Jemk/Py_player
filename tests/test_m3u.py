from pyplayer.api.m3u import read_playlist_file, write_m3u


def test_read_m3u_relative_absolute_and_urls(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"x")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.mkv").write_bytes(b"x")
    playlist = tmp_path / "list.m3u"
    playlist.write_text(
        "#EXTM3U\n#EXTINF:10,a\na.mp4\nsub\\b.mkv\n" + str(tmp_path / "a.mp4") + "\nhttp://x/y.mp4\nabsent.mp4\nnote.txt\n",
        encoding="utf-8")
    name, paths = read_playlist_file(playlist)
    assert name == "list"
    assert [p.name for p in paths] == ["a.mp4", "b.mkv", "a.mp4"]


def test_read_pls_and_file_urls(tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    pls = tmp_path / "l.pls"
    pls.write_text(f"[playlist]\nFile1={tmp_path / 'a.mp3'}\nTitle1=a\nNumberOfEntries=1\n", encoding="utf-8")
    assert [p.name for p in read_playlist_file(pls)[1]] == ["a.mp3"]
    m3u = tmp_path / "u.m3u"
    m3u.write_text(f"{(tmp_path / 'a.mp3').as_uri()}\n", encoding="utf-8")        # URL bien formée, tout système
    assert [p.name for p in read_playlist_file(m3u)[1]] == ["a.mp3"]
    m3u.write_text(f"file://{(tmp_path / 'a.mp3').as_posix()}\n", encoding="utf-8")  # « file://C:/x » mal formé mais courant
    assert [p.name for p in read_playlist_file(m3u)[1]] == ["a.mp3"]


def test_write_m3u_format(tmp_path):
    out = tmp_path / "o.m3u8"
    write_m3u([(tmp_path / "a.mp4", "A é", 65_000), (tmp_path / "b.mp4", "B", 0)], out)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "#EXTM3U" and lines[1] == "#EXTINF:65,A é" and lines[3] == "#EXTINF:-1,B"


def test_read_m3u_latin1_fallback(tmp_path):
    (tmp_path / "é.mp4").write_bytes(b"x")
    playlist = tmp_path / "l.m3u"
    playlist.write_bytes("é.mp4\n".encode("cp1252"))
    assert [p.name for p in read_playlist_file(playlist)[1]] == ["é.mp4"]

"""Which finds should a shell actually *show*? (M4: manifest over segments.)

Real HLS pages hand you the playlist *and* its fragments — a dozen `seg-N.ts`
rows around the one `master.m3u8` that matters, plus DASH's `.m4s` equivalents.
The rule lives here, in the engine, so every shell hides the same things for the
same reason, and the reason travels with the answer instead of being a silent
disappearance.

Nothing else is ever hidden: the shells still own confidence (what you are
watching, the strongest sighting). This only judges *shape*.
"""
from suravidl_engine.classify import rank

HLS = "https://cdn.example/hls/master.m3u8"
SEG = ["https://cdn.example/hls/seg-1.ts", "https://cdn.example/hls/seg-2.ts"]


def test_fragments_of_a_seen_playlist_are_hidden_and_say_why():
    out = rank([SEG[0], HLS, SEG[1]])
    by = {i["url"]: i for i in out["items"]}
    assert by[HLS]["kind"] == "manifest" and not by[HLS]["hidden"]
    for s in SEG:
        assert by[s]["hidden"], f"{s} should be hidden"
        assert "master.m3u8" in by[s]["reason"], by[s]["reason"]
    assert out["hidden"] == 2


def test_fragments_with_no_playlist_stay_visible_but_admit_what_they_are():
    out = rank(SEG)
    assert out["hidden"] == 0
    assert all(i["kind"] == "segment" for i in out["items"])
    assert all("playlist" in i["reason"] for i in out["items"])


def test_a_playlist_on_another_host_hides_nothing():
    out = rank(["https://a.example/seg.ts", "https://b.example/master.m3u8"])
    assert out["hidden"] == 0


def test_ordinary_media_is_left_alone():
    out = rank(["https://cdn.example/clip.mp4", "https://cdn.example/song.m4a"])
    assert out["hidden"] == 0
    assert all(i["kind"] == "media" for i in out["items"])


def test_a_dash_manifest_hides_its_own_fragments():
    out = rank(["https://cdn.example/d/stream.mpd",
                "https://cdn.example/d/chunk-1.m4s"])
    by = {i["url"]: i for i in out["items"]}
    assert by["https://cdn.example/d/chunk-1.m4s"]["hidden"]
    assert by["https://cdn.example/d/stream.mpd"]["kind"] == "manifest"


def test_an_extension_less_manifest_still_counts_as_one():
    out = rank(["https://cdn.example/dash/manifest?id=7",
                "https://cdn.example/dash/x.m4s"])
    assert out["hidden"] == 1


def test_an_empty_list_is_an_empty_answer():
    assert rank([]) == {"items": [], "hidden": 0}


def test_a_query_string_is_not_a_name():
    """An honest `.mp4` whose query mentions a playlist is a video — and it must
    not hide a fragment on its host by pretending to be a playlist."""
    odd = "https://cdn.example/clip.mp4?origin=playlist"
    out = rank([odd, "https://cdn.example/seg-9.ts"])
    by = {i["url"]: i for i in out["items"]}
    assert by[odd]["kind"] == "media"
    assert out["hidden"] == 0


def test_two_playlists_on_one_host_attribute_fragments_to_the_nearer_one():
    """An ad's playlist and the film's share a host; the reason must name the
    playlist the fragment actually belongs to, not whichever came last."""
    out = rank(["https://cdn.example/ads/spots.m3u8",
                "https://cdn.example/film/master.m3u8",
                "https://cdn.example/film/seg-1.ts"])
    by = {i["url"]: i for i in out["items"]}
    assert by["https://cdn.example/film/seg-1.ts"]["reason"] == "part of master.m3u8"

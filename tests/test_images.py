"""generate_image: figure-mode + asset-mode; quota propagation; isolation."""
from __future__ import annotations

import pytest

from co_scientist_local.backends.base import NotFound
from co_scientist_local.image_gen import QuotaExceeded
from co_scientist_local.state import State
from co_scientist_local.tools import figures, images, papers


def _setup(state):
    papers.create_paper(state, title="My paper")
    return "my-paper"


# ──────────────────────────────────────────────────────────────────────────────
# figure mode
# ──────────────────────────────────────────────────────────────────────────────


def test_generate_image_as_figure_uploads_blob_and_registers_doc(state, backend, image_gen):
    slug = _setup(state)
    res = images.generate_image(
        state, slug,
        prompt="Phylogenetic tree of Pueraria species",
        figure_number=1,
        aspect_ratio="4:3",
    )
    assert res["mode"] == "figure"
    assert res["figure_number"] == 1
    # The blob in Storage carries the fake PNG bytes
    blob = backend.get_blob(res["blob_path"])
    assert blob == b"\x89PNG_FAKE"
    # The figure doc exists and points to the same blob
    fig = figures.get_figure(state, slug, 1)
    assert fig["blob_path"] == res["blob_path"]
    # Generator received the right args
    assert image_gen.calls[0]["prompt"] == "Phylogenetic tree of Pueraria species"
    assert image_gen.calls[0]["aspect_ratio"] == "4:3"


def test_generate_image_figure_default_caption_is_prompt_prefix(state):
    slug = _setup(state)
    long_prompt = "a" * 500
    images.generate_image(state, slug, prompt=long_prompt, figure_number=1)
    fig = figures.get_figure(state, slug, 1)
    assert fig["caption"] == "a" * 200


def test_generate_image_figure_caption_override(state):
    slug = _setup(state)
    images.generate_image(state, slug, prompt="anything",
                          figure_number=1, caption="custom caption")
    fig = figures.get_figure(state, slug, 1)
    assert fig["caption"] == "custom caption"


# ──────────────────────────────────────────────────────────────────────────────
# asset mode
# ──────────────────────────────────────────────────────────────────────────────


def test_generate_image_as_asset(state, backend):
    slug = _setup(state)
    res = images.generate_image(state, slug, prompt="Hypothesis schematic")
    assert res["mode"] == "asset"
    assert res["asset_id"]
    assert res["blob_path"].startswith(f"projects/p-alice/papers/{slug}/assets/")
    assert backend.get_blob(res["blob_path"]) == b"\x89PNG_FAKE"


def test_generate_image_asset_with_explicit_filename(state, backend):
    slug = _setup(state)
    res = images.generate_image(state, slug, prompt="x",
                                asset_filename="hypothesis.png")
    assert res["blob_path"] == f"projects/p-alice/papers/{slug}/assets/hypothesis.png"


def test_list_assets_sorted_newest_first(state):
    slug = _setup(state)
    images.generate_image(state, slug, prompt="A", asset_filename="a.png")
    images.generate_image(state, slug, prompt="B", asset_filename="b.png")
    listed = images.list_assets(state, slug)
    assert [a["filename"] for a in listed] == ["b.png", "a.png"]


def test_delete_asset(state, backend):
    slug = _setup(state)
    res = images.generate_image(state, slug, prompt="x", asset_filename="x.png")
    assert images.delete_asset(state, slug, "x.png") is True
    assert backend.get_blob(res["blob_path"]) is None
    assert images.delete_asset(state, slug, "x.png") is False  # idempotent


def test_delete_asset_by_asset_id(state):
    slug = _setup(state)
    res = images.generate_image(state, slug, prompt="x")
    assert images.delete_asset(state, slug, res["asset_id"]) is True


# ──────────────────────────────────────────────────────────────────────────────
# error paths
# ──────────────────────────────────────────────────────────────────────────────


def test_generate_image_propagates_quota_exceeded(state, image_gen):
    slug = _setup(state)
    image_gen.trigger_quota_exceeded()
    with pytest.raises(QuotaExceeded):
        images.generate_image(state, slug, prompt="x")


def test_generate_image_requires_prompt(state):
    slug = _setup(state)
    with pytest.raises(ValueError, match="prompt is required"):
        images.generate_image(state, slug, prompt="")


def test_generate_image_missing_paper(state):
    with pytest.raises(NotFound):
        images.generate_image(state, "ghost", prompt="x")


def test_generate_image_requires_configured_generator(backend):
    """A State with no image_gen injected must raise a clear error."""
    state_no_gen = State(project_id="p-alice", owner_uid="alice", backend=backend)
    papers.create_paper(state_no_gen, title="P")
    with pytest.raises(RuntimeError, match="no image generator configured"):
        images.generate_image(state_no_gen, "p", prompt="x")


# ──────────────────────────────────────────────────────────────────────────────
# isolation
# ──────────────────────────────────────────────────────────────────────────────


def test_assets_isolation_between_users(state, other_state):
    slug = _setup(state)
    images.generate_image(state, slug, prompt="alice's image")
    # Bob can't see alice's paper or its assets
    with pytest.raises(NotFound):
        images.list_assets(other_state, slug)

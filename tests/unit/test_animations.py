"""Tests for animation registry, Walker, Particles, and Page Turn."""
import pytest
import time
import displayio
from pico_reader.animations import ANIMATION_NAMES, load_animation
from pico_reader.animations.walker import (
    Animation as WalkerAnimation,
    _frame_for_wpm,
    _x_for_progress,
    SPRITE_W,
    DISPLAY_W,
    Y_POS,
)
from pico_reader.animations.particles import (
    Animation as ParticlesAnimation,
    DISPLAY_H,
    DISPLAY_W as P_DISPLAY_W,
    MARGIN,
    NUM_PARTICLES,
    _pseudo_x,
)
from pico_reader.animations.page_turn import (
    Animation as PageTurnAnimation,
    WORDS_PER_PAGE,
    FLASH_TICKS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeFont:
    pass


class FakeSkin:
    def __init__(self):
        self._smallfont = FakeFont()
        self._highlight = 0x00ff00

    def get_highlight_color(self):
        return self._highlight


class FakeDisplay:
    def __init__(self):
        self.skin = FakeSkin()
        self._smallfont = FakeFont()


class FakeState:
    def __init__(self, wpm=200):
        self.wpm = wpm


class FakeBook:
    def __init__(self, line_num=0, book_len=1000, word_idx=0):
        self.line_num = line_num
        self.book_len = book_len
        self.word_idx = word_idx


class FakeStateWithStats:
    """State that has book_stats.words_read for page_turn."""
    def __init__(self, wpm=200, words_read=0):
        self.wpm = wpm
        self.book_stats = type('obj', (object,), {'words_read': words_read})()


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------

class TestAnimationRegistry:
    def test_animation_names_list(self):
        assert ANIMATION_NAMES == ['off', 'walker', 'particles', 'page_turn']

    def test_load_off_returns_none(self):
        assert load_animation('off') is None

    def test_load_unknown_returns_none(self):
        assert load_animation('nonexistent') is None

    def test_load_walker(self):
        anim = load_animation('walker')
        assert anim is not None
        assert isinstance(anim, WalkerAnimation)

    def test_load_particles(self):
        anim = load_animation('particles')
        assert anim is not None
        assert isinstance(anim, ParticlesAnimation)

    def test_load_page_turn(self):
        anim = load_animation('page_turn')
        assert anim is not None
        assert isinstance(anim, PageTurnAnimation)


# ---------------------------------------------------------------------------
# Walker: position tests
# ---------------------------------------------------------------------------

class TestWalkerPosition:
    def test_x_at_zero_progress(self):
        """Walker at line 0/1000 -> x = 0."""
        assert _x_for_progress(0.0) == 0

    def test_x_at_half_progress(self):
        """Walker at line 500/1000 -> x ~ 77."""
        x = _x_for_progress(0.5)
        assert x == int(0.5 * (DISPLAY_W - SPRITE_W))
        assert x == 77

    def test_x_at_full_progress(self):
        """Walker at line 1000/1000 -> x = 155."""
        x = _x_for_progress(1.0)
        assert x == DISPLAY_W - SPRITE_W
        assert x == 155


# ---------------------------------------------------------------------------
# Walker: frame selection tests
# ---------------------------------------------------------------------------

class TestWalkerFrames:
    def test_wpm_100_walk_frames(self):
        """WPM 100 -> frames 0-1 (walk)."""
        f0 = _frame_for_wpm(100, 0)
        f1 = _frame_for_wpm(100, 1)
        assert f0 == 0
        assert f1 == 1

    def test_wpm_150_walk_frames(self):
        """WPM exactly 150 -> still walk (0-1)."""
        f0 = _frame_for_wpm(150, 0)
        f1 = _frame_for_wpm(150, 1)
        assert f0 == 0
        assert f1 == 1

    def test_wpm_200_jog_frames(self):
        """WPM 200 -> frames 2-3 (jog)."""
        f0 = _frame_for_wpm(200, 0)
        f1 = _frame_for_wpm(200, 1)
        assert f0 == 2
        assert f1 == 3

    def test_wpm_300_jog_frames(self):
        """WPM exactly 300 -> still jog (2-3)."""
        f0 = _frame_for_wpm(300, 0)
        f1 = _frame_for_wpm(300, 1)
        assert f0 == 2
        assert f1 == 3

    def test_wpm_400_run_frames(self):
        """WPM 400 -> frames 4-5 (run)."""
        f0 = _frame_for_wpm(400, 0)
        f1 = _frame_for_wpm(400, 1)
        assert f0 == 4
        assert f1 == 5

    def test_alternation(self):
        """Frames alternate each tick."""
        frames = [_frame_for_wpm(200, t) for t in range(6)]
        assert frames == [2, 3, 2, 3, 2, 3]


# ---------------------------------------------------------------------------
# Walker: build and tick integration
# ---------------------------------------------------------------------------

class TestWalkerBuildTick:
    def test_build_returns_one_tilegrid(self):
        anim = WalkerAnimation()
        elems = anim.build(FakeDisplay())
        assert len(elems) == 1
        assert isinstance(elems[0], displayio.TileGrid)

    def test_tilegrid_y_position(self):
        anim = WalkerAnimation()
        elems = anim.build(FakeDisplay())
        assert elems[0].y == Y_POS

    def test_tick_updates_position(self):
        anim = WalkerAnimation()
        elems = anim.build(FakeDisplay())
        tg = elems[0]
        state = FakeState(wpm=200)
        book = FakeBook(line_num=500, book_len=1000)
        anim.tick(state, book, FakeDisplay())
        assert tg.x == 77

    def test_tick_updates_frame(self):
        anim = WalkerAnimation()
        anim.build(FakeDisplay())
        state = FakeState(wpm=400)
        book = FakeBook()
        anim.tick(state, book, FakeDisplay())
        # After one tick (tick_count=1, odd), frame should be 5
        assert anim._tg[0] == 5

    def test_destroy_clears_refs(self):
        anim = WalkerAnimation()
        anim.build(FakeDisplay())
        anim.destroy()
        assert anim._tg is None
        assert anim._palette is None


# ---------------------------------------------------------------------------
# Particles: wrapping tests
# ---------------------------------------------------------------------------

class TestParticleWrapping:
    def test_particle_at_bottom_wraps_to_top(self):
        """Particle at y=127 wraps to y=0 after tick."""
        anim = ParticlesAnimation()
        anim.build(FakeDisplay())
        # Force a particle to bottom edge
        anim._grids[0].y = DISPLAY_H - 1  # y=127
        state = FakeState()
        book = FakeBook()
        anim.tick(state, book, FakeDisplay())
        # y was 127, +1 = 128 which >= DISPLAY_H, so wrap to 0
        assert anim._grids[0].y == 0

    def test_particle_not_at_bottom_drifts_down(self):
        """Particle not at bottom just drifts 1px."""
        anim = ParticlesAnimation()
        anim.build(FakeDisplay())
        anim._grids[0].y = 50
        state = FakeState()
        book = FakeBook()
        anim.tick(state, book, FakeDisplay())
        assert anim._grids[0].y == 51


# ---------------------------------------------------------------------------
# Particles: bounds tests
# ---------------------------------------------------------------------------

class TestParticleBounds:
    def test_particles_stay_in_bounds(self):
        """All particles x in [0, 160) and y in [0, 128) after build."""
        anim = ParticlesAnimation()
        anim.build(FakeDisplay())
        for tg in anim._grids:
            assert 0 <= tg.x < P_DISPLAY_W
            assert 0 <= tg.y < DISPLAY_H

    def test_build_creates_four_particles(self):
        anim = ParticlesAnimation()
        elems = anim.build(FakeDisplay())
        assert len(elems) == NUM_PARTICLES
        assert len(anim._grids) == NUM_PARTICLES

    def test_pseudo_x_left_margin(self):
        """Even particle IDs use left margin (0..MARGIN-1)."""
        for seed in [0.0, 1.5, 100.7]:
            x = _pseudo_x(seed, 0)
            assert 0 <= x < MARGIN

    def test_pseudo_x_right_margin(self):
        """Odd particle IDs use right margin."""
        for seed in [0.0, 1.5, 100.7]:
            x = _pseudo_x(seed, 1)
            assert P_DISPLAY_W - MARGIN <= x < P_DISPLAY_W

    def test_destroy_clears_refs(self):
        anim = ParticlesAnimation()
        anim.build(FakeDisplay())
        anim.destroy()
        assert anim._grids == []
        assert anim._palettes == []


# ---------------------------------------------------------------------------
# Page Turn: page counting
# ---------------------------------------------------------------------------

class TestPageCounting:
    def test_page_count_zero_words(self):
        """0 words read -> pg 1."""
        page = 0 // WORDS_PER_PAGE + 1
        assert page == 1

    def test_page_count_249_words(self):
        """249 words -> still pg 1."""
        page = 249 // WORDS_PER_PAGE + 1
        assert page == 1

    def test_page_count_250_words(self):
        """250 words -> pg 2."""
        page = 250 // WORDS_PER_PAGE + 1
        assert page == 2

    def test_page_count_500_words(self):
        """500 words -> pg 3."""
        page = 500 // WORDS_PER_PAGE + 1
        assert page == 3


# ---------------------------------------------------------------------------
# Page Turn: flash behavior
# ---------------------------------------------------------------------------

class TestPageFlash:
    def test_page_increment_triggers_flash(self):
        """When page changes, flash_ticks should be set to 3."""
        anim = PageTurnAnimation()
        anim.build(FakeDisplay())
        state = FakeStateWithStats(words_read=0)
        book = FakeBook()

        # First tick at page 1 -- no change since _current_page starts at 1
        anim.tick(state, book, FakeDisplay())
        assert anim._flash_remaining == 0

        # Move to page 2
        state.book_stats.words_read = 250
        anim.tick(state, book, FakeDisplay())
        assert anim._current_page == 2
        assert anim._flash_remaining == FLASH_TICKS - 1  # decremented once this tick

    def test_flash_counts_down(self):
        """Flash remaining decrements each tick."""
        anim = PageTurnAnimation()
        anim.build(FakeDisplay())
        state = FakeStateWithStats(words_read=0)
        book = FakeBook()
        disp = FakeDisplay()

        # Trigger page change
        state.book_stats.words_read = 250
        anim.tick(state, book, disp)
        # flash_remaining was set to 3, then decremented to 2
        assert anim._flash_remaining == 2

        anim.tick(state, book, disp)
        assert anim._flash_remaining == 1

        anim.tick(state, book, disp)
        assert anim._flash_remaining == 0

        # After flash ends, color should be normal
        anim.tick(state, book, disp)
        assert anim._flash_remaining == 0
        assert anim._label.color == anim._normal_color

    def test_flash_uses_highlight_color(self):
        """During flash, label color should be highlight."""
        anim = PageTurnAnimation()
        disp = FakeDisplay()
        anim.build(disp)
        state = FakeStateWithStats(words_read=250)
        book = FakeBook()

        anim.tick(state, book, disp)
        # Should be flashing -- color is highlight
        assert anim._label.color == disp.skin.get_highlight_color()

    def test_build_returns_one_label(self):
        anim = PageTurnAnimation()
        elems = anim.build(FakeDisplay())
        assert len(elems) == 1

    def test_label_text_initial(self):
        anim = PageTurnAnimation()
        anim.build(FakeDisplay())
        assert anim._label.text == 'pg 1'

    def test_label_text_updates_on_page_change(self):
        anim = PageTurnAnimation()
        anim.build(FakeDisplay())
        state = FakeStateWithStats(words_read=500)
        book = FakeBook()
        anim.tick(state, book, FakeDisplay())
        assert anim._label.text == 'pg 3'

    def test_destroy_clears_refs(self):
        anim = PageTurnAnimation()
        anim.build(FakeDisplay())
        anim.destroy()
        assert anim._label is None


# ---------------------------------------------------------------------------
# Page Turn: fallback without book_stats
# ---------------------------------------------------------------------------

class TestPageTurnFallback:
    def test_uses_line_estimate_without_book_stats(self):
        """Without book_stats, estimates words from line_num * 10 + word_idx."""
        anim = PageTurnAnimation()
        anim.build(FakeDisplay())
        state = FakeState(wpm=200)  # no book_stats attribute
        book = FakeBook(line_num=25, word_idx=0)  # ~250 words
        anim.tick(state, book, FakeDisplay())
        assert anim._current_page == 2

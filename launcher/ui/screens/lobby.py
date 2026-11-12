"""Who plays, and as whom: a card for each player here (and, online, one for the partner). A
player joins with any button on their controller, or Enter, and picks a character with left and
right. An available character shows their portrait, from the player's own disc; one whose disc
isn't attached shows an empty frame and the disc that unlocks them. Online, the host's room code is
on the partner's card. This draws a frame of it: the app's lobby keeps the players and their input."""

import pygame

from ..theme import DIM, GOLD, GREEN, INK, shorten, wrap

HEAD = (8, 6, 464, 22)
CARD_Y, CARD_H = 34, 200
FRAME_W, FRAME_H = 66, 98
SIDE_GAP = 6
# Each character's portrait (the Saturn two have the PlayStation pair's)
PORTRAITS = ("alucard", "richter", "maria", "maria", "maria", "richter")


def portrait(m, character):
    """The character's portrait (Tucker, 2026-11-11: as it is, no tint)."""
    return m.theme.pictures[PORTRAITS[character]]


def draw_lobby(m, heading, about, cards, partner, footer):
    """cards: [{"title", "joined", "device", "ready", "character", "name", "playable", "note",
    "needs", "controls"}]. partner: None, or (lines, connected, code or None). footer: (pad text,
    keyboard text)."""
    t, s = m.theme, m.s
    m.begin("Press a button to join", about)
    m.window(HEAD)
    t.text(s, heading, HEAD[0] + 8, HEAD[1] + 7, GOLD)
    if about:
        t.text_right(s, shorten(about, 38), HEAD[0] + HEAD[2] - 8, HEAD[1] + 7, DIM)
    n = len(cards) + (1 if partner else 0)
    gap = 8
    w = (464 - gap * (n - 1)) // n
    for k in range(n):
        x = 8 + k * (w + gap)
        box = pygame.Rect(x, CARD_Y, w, CARD_H)
        m.window(box)
        if k < len(cards):
            card(m, box, cards[k])
        else:
            partner_card(m, box, *partner)
    m.footer(*footer)
    m.show()


def card(m, box, c):
    t, s, cx = m.theme, m.s, box.centerx
    t.text_centre(s, c["title"], cx, box.y + 7, GOLD if c["joined"] else DIM)
    if not c["joined"]:
        for k, line in enumerate(("Press any button", "on a controller", "", "(or Enter:", "the keyboard)")):
            t.text_centre(s, line, cx, box.y + 60 + k * 11, DIM)
        return
    t.text_centre(s, shorten(c["device"], (box.w - 12) // 8), cx, box.y + 19, DIM)
    frame = pygame.Rect(0, 0, FRAME_W, FRAME_H)
    frame.midtop = (cx, box.y + 32)
    # The carousel (issue 252): the characters either side, dimmed, where the card has room
    if not c["ready"] and box.w >= 3 * FRAME_W + 2 * SIDE_GAP + 12:
        for (other, playable), dx in zip(c.get("neighbours", ()), (-1, 1)):
            side = frame.move(dx * (FRAME_W + SIDE_GAP), 0)
            pygame.draw.rect(s, (0, 0, 16), side)
            if playable:
                picture = portrait(m, other)
                s.blit(picture, picture.get_rect(center=side.center))
            veil = pygame.Surface(side.size, pygame.SRCALPHA)
            veil.fill((0, 0, 16, 150))
            s.blit(veil, side)
            pygame.draw.rect(s, DIM, side, 1)
    pygame.draw.rect(s, (0, 0, 16), frame)
    pygame.draw.rect(s, GREEN if c["ready"] else INK, frame, 1)
    if c["playable"]:
        picture = portrait(m, c["character"])
        s.blit(picture, picture.get_rect(center=frame.center))
    y = frame.bottom + 6
    name = shorten(c["name"], (box.w - 36) // 8)
    t.text_centre(s, name, cx, y, INK if c["playable"] else DIM)
    if not c["ready"]:  # the arrows: left and right change it
        half = len(name) * 4
        t.text(s, "{<}", cx - half - 14, y)
        t.text(s, "{>}", cx + half + 6, y)
    y += 12
    if c.get("version"):  # up and down: their versions
        version = shorten(c["version"], (box.w - 36) // 8)
        t.text_centre(s, version, cx, y, GOLD if c["playable"] else DIM)
        if not c["ready"] and c.get("versions", 1) > 1:
            half = len(version) * 4
            t.text(s, "{^}", cx - half - 14, y)
            t.text(s, "{v}", cx + half + 6, y)
        y += 12
    if c["playable"]:
        for line in wrap(c["note"], (box.w - 12) // 8)[:1] if c["note"] else []:
            t.text_centre(s, line, cx, y, DIM)
            y += 10
        t.text_centre(s, shorten(c["controls"], (box.w - 12) // 8), cx, box.bottom - 30, INK if c["shortcuts"] else DIM)
    else:
        for line in wrap(c["needs"], (box.w - 12) // 8)[:4]:
            t.text_centre(s, line, cx, y, DIM)
            y += 10
    if c["ready"]:
        t.text_centre(s, "Ready!", cx, box.bottom - 16, GREEN)
    elif c["playable"]:
        t.text_centre(s, "{x} when ready" if m.device == "pad" else "Enter when ready", cx, box.bottom - 16, DIM)
    else:
        t.text_centre(s, "{x} attach it" if m.device == "pad" else "Enter: attach it", cx, box.bottom - 16, INK)


def partner_card(m, box, lines, connected, code):
    t, s, cx = m.theme, m.s, box.centerx
    t.text_centre(s, "Your partner", cx, box.y + 7, GOLD)
    y = box.y + 30
    if code and not connected:
        t.text_centre(s, "Room code", cx, y, DIM)
        t.text_big(s, code, cx, y + 14, GOLD)
        y += 42
    for line in lines:
        for part in wrap(line, (box.w - 12) // 8):
            t.text_centre(s, part, cx, y, GREEN if connected and y < box.y + 50 else INK)
            y += 11

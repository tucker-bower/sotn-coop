"""What to test for a change (AGENTS.md, Testing; D179).

Every test belongs to one or more CATEGORIES, by its name or the module it's in. A small change runs
only the categories it touches:

    run.py -c richter             # every Richter test (not the full-only ones)
    run.py --changed              # the categories this branch's changed files touch (PATHS below)

EVERYDAY is the PR gate (run.py with no tests named): the tests that have caught a bug, plus one or
two quick ones per category. A test joins it only when it covers something no gate test does, and
leaves it once run.py --history shows it hasn't failed alone in a long while. --full runs
everything, before a release.
"""

import re

# category: (what it covers, a regex any of its test names matches, or the test modules it holds)
CATEGORIES = {
    "richter": ("Richter as a player: moves, relics, gear, his overlay", r"richter", ()),
    "maria": ("Maria as a player: moves, relics, gear, her overlay", r"maria", ()),
    "alucard": ("Alucard-only checks: his HUD, gear, damage", r"alucard", ()),
    "combat": ("Damage, gear, sub-weapons, familiars, spells, poison",
               r"damage_rate|poison|offhand|subweapon|crashes|familiar|spell|relics_|vlad_|telescope|hand_items|"
               r"partner_(attack|dagger|swing|fist)|librarian", ()),
    "bosses": ("Boss fights, pulls, aggro, boss rush", r"boss|aggro", ("session_bossrush",)),
    "cutscenes": ("Story scenes, the prologue, scene pulls and skips", r"scene|prologue|death_waits|ending_", ()),
    "progression": ("Shared XP, items, relics, gold, map, saves, castles",
                    r"shared_xp|relic_shared|items_and|finds_|gold|map_shared|exactly_once|live_despawn|"
                    r"live_object|rules_xp|drop_enemy|level_up|castle_|joint_save|save_room|resume_from|"
                    r"red_door|guest_opens|test_castle", ("session_progress",)),
    "traversal": ("Teleports, doors, room edges, respawn, the crawl, bat carry, movement",
                  r"teleport|respawn|crawl|edges_|door_gap|walk_|inverted_rooms|elevator|bat_carry|camera|"
                  r"movement|mist_step|relic_gates|loader_|in_the_castle|secret_wall|map_marker", ("session_travel",)),
    "rooms": ("Shared rooms and the partner's body: authority and guest, targeting, puppets",
              r"guest_|shared_|partner_|targeting|puppet|presence|in_and_out|snapshot|body_|same_character|"
              r"music_mute|rolling_states|mixed_party|pickup_|unpause|pad_quiet|crashwatch|fairy|no_effect|"
              r"hand_over|death_fades",
              ("session_shared", "scenarios_m13")),
    "network": ("Online play: connecting, lag and loss, versions",
                r"online|netplay|link_|stale_link|soak", ("session_online", "session_m9", "spec_test")),
    "rules": ("The castle's rules", r"rules_|_off_by_default", ("session_rules",)),
    "pvp": ("PvP", r"pvp", ("session_m15",)),
    "launcher": ("The app: menus, settings, reports, the UI flows", r"launcher_|ui_|char_select|report_state|report_f9|solo_continue", ()),
    "mods": ("Other mods' discs: the randomizer, editor hacks, the patcher", r"mod_|patcher_|rando", ()),
    "inverted": ("The inverted castle", r"inverted|final_boss|shaft|crawl_r", ("session_inverted",)),
    "widescreen": ("Widescreen views (design/M19)", r"widescreen", ("scenarios_widescreen", "session_widescreen")),
}

# Source file (a prefix of its path) -> the categories a change there touches. A file not listed
# touches none: run the categories by hand, or the gate. Test files touch their own tests (--changed
# adds every test in a changed harness/session_*.py or scenarios*.py).
PATHS = {
    "characters/richter-ps1/": ("richter",),
    "characters/maria-dx/": ("maria",),
    "characters/maria-ultimate/": ("maria",),
    "characters/maria-saturn/": ("maria",),
    "launcher/saturn_maria.py": ("maria", "launcher"),
    "launcher/saturn_maria_sounds.py": ("maria", "launcher"),
    "launcher/saturn_richter.py": ("richter", "launcher"),
    "characters/": ("richter", "maria"),
    "module/character.c": ("richter", "maria"),
    "module/widescreen": ("widescreen",),
    "module/offhand.c": ("richter", "maria", "combat"),
    "module/weapons.c": ("richter", "maria", "combat"),
    "module/spells.c": ("combat",),
    "module/familiar.c": ("combat",),
    "module/mist.c": ("richter", "maria"),
    "module/portrait.c": ("richter", "maria"),
    "module/boss.c": ("bosses",),
    "module/progress.c": ("progression", "rules"),
    "module/collectibles.c": ("progression", "mods"),
    "module/flag_gated.c": ("progression",),
    "module/arrive.c": ("traversal", "cutscenes", "bosses"),
    "module/carry.c": ("traversal",),
    "module/partner.c": ("rooms",),
    "module/sprites.c": ("rooms",),
    "module/vram.c": ("rooms", "richter", "maria"),
    "module/solid.c": ("rooms", "traversal"),
    "module/shared.c": ("rooms", "bosses"),
    "module/pvp.c": ("pvp",),
    "module/message.c": ("launcher",),
    "module/link.h": ("rooms", "progression", "traversal", "network"),  # the mailbox: link_layout checks the host's copy
    "module/": ("rooms", "progression", "traversal"),  # coop.c, boot.c and the rest: the core
    "patches/sotn-decomp": ("rooms", "progression", "traversal", "richter", "maria"),
    "patches/swanstation": ("network", "launcher"),
    "link/": ("network",),
    "launcher/rules.py": ("rules", "launcher"),
    "launcher/": ("launcher",),
    "patcher/": ("mods",),
    "launcher/library.py": ("mods", "launcher"),
    "android/": ("launcher",),
}

# The PR gate (run.py with no tests named): the tests that have caught a bug alone (run.py --history),
# and the few quick ones kept so every category has a check (2026-11-17: the suite was cut to them, D212).
EVERYDAY = {
    # other characters and their gear
    "bat_carry_alucard", "boss_arena_edge_richter_and_maria", "boss_life_up_once_alucard_and_richter", "damage_rate_richter", "shared_room_elevator_richter_and_alucard", "shared_room_lift_on_lag_alucard_and_richter",
    "familiar_faerie_potion_richter", "familiar_graphics_maria", "hit_shows_its_number_maria",
    "in_the_castle_maria", "in_the_castle_richter", "level_up_stats_maria", "maria_owl_with_a_weapon_in_hand",
    "maria_scene_richter_on_the_throne", "mist_step_never_stuck_maria",
    "partner_body_alucard_and_saturn_maria", "partner_graphics_stay_in_their_bank_richter_and_maria",
    "relic_gates_maria", "relic_gates_richter", "relics_alucard", "richter_backflips_turn",
    "richter_left_hand_keeps_his_graphics", "saturn_maria_beasts", "shaft_orb_unseen_richter",
    "stage_palettes_maria", "ultimate_richter_in_the_castle",
    # bosses and cutscenes
    "boss_trio_authority_changes", "boss_trio_partner_locked_out", "online_boss_rush",
    "scene_skips_once_both_players_ask", "ui_online_boss_rush", "launcher_streamer", "map_shows_the_teleport_prompt",
    # progression
    "castle_solo_play", "exactly_once_partition", "gold_pooled", "map_shared", "red_door_guest_copy_in_place",
    "relic_shared", "save_room_real", "widescreen_red_door_comes_back",
    # traversal
    "bat_carry_rider_hangs_in_the_bats_game", "bat_carry_through_a_door_still_a_bat",
    "inverted_teleport_into", "loader_in_game", "teleport_partner_busy", "walk_entrance_rooms",
    # network
    "launcher_link_errors", "link_backlog", "link_connect", "link_layout", "link_malformed", "link_portmap",
    "link_spec_conformance", "online_connect_codes", "online_in_process", "online_partner_leaves",
    "online_version_mismatch", "ui_online", "netplay_partner_on_time_alucard_and_richter", "netplay_room_enemies_steady_on_lag",
    # rules and pvp
    "pvp_death", "pvp_off", "pvp_spawn_protection", "rules_reach_the_game",
    # launcher and mods
    "launcher_castles", "launcher_crash_window", "launcher_library", "launcher_one_folder", "launcher_report",
    "launcher_rules", "launcher_screens_fit", "launcher_settings", "launcher_ship_lists", "launcher_ui",
    "launcher_update", "patcher_layer", "patcher_modded", "patcher_round_trip",
    "ui_couch", "ui_menus", "ui_randomizer", "ui_startup",
    # rooms and widescreen
    "char_select_session", "guest_gets_hurt", "guest_takes_heart", "mixed_soak_short", "no_effect_on_play",
    "partner_body_follows", "partner_vram_banks_draw", "shared_same_enemies", "targeting_nearer_player",
    "widescreen_stage_windows_every_stage",
}



def of(name, module):
    """The categories a test is in."""
    return [c for c, (_, pattern, modules) in CATEGORIES.items() if re.search(pattern, name) or module in modules]


def for_paths(paths):
    """{category: [the changed files that touch it]}, and the test modules changed."""
    touched, modules = {}, set()
    for p in paths:
        if p.startswith("harness/") and p.endswith(".py"):
            modules.add(p[len("harness/"):-3])
            continue
        prefix = max((k for k in PATHS if p.startswith(k)), key=len, default=None)
        for c in PATHS.get(prefix, ()):
            touched.setdefault(c, []).append(p)
    return touched, modules

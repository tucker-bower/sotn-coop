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
    "cutscenes": ("Story scenes, the prologue, scene pulls and skips", r"scene|prologue|death_waits", ()),
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
    "launcher": ("The app: menus, settings, reports, the UI flows", r"launcher_|ui_|char_select|report_state|solo_continue", ()),
    "mods": ("Other mods' discs: the randomizer, editor hacks, the patcher", r"mod_|patcher_|rando", ("session_mods",)),
    "inverted": ("The inverted castle", r"inverted|final_boss|shaft|crawl_r", ("session_inverted",)),
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

# The PR gate (run.py with no tests named), by category. The first of each group caught a bug
# (run.py --history); "+" marks the quick ones kept so every category has a check.
EVERYDAY = {
    # richter, maria, alucard, combat
    "alucard_health_bar_richter", "alucard_health_bar_maria", "poison_hits_richter", "poison_hits_maria",
    "damage_rate_alucard", "damage_rate_richter", "damage_rate_maria", "offhand_frame_palettes_richter",
    "offhand_one_attack_at_a_time_richter", "partner_fist_drawn_richter", "telescope_richter", "telescope_maria",
    "librarian_shop_alucard", "librarian_shop_richter", "relics_alucard", "door_gap_richter_walks_through",
    "unpause_with_empty_hands_maria_and_alucard", "partner_casts_a_spell_this_game_never_learnt",
    "in_the_castle_richter", "in_the_castle_maria", "relic_gates_richter", "relic_gates_maria",  # +
    "level_up_richter", "level_up_maria", "subweapons_richter", "subweapons_maria",  # +
    "boss_arena_edge_richter_and_maria", "report_hold_pauses_the_game", "familiar_faerie_potion_richter",  # #188 #192 #200
    "maria_owl_with_a_weapon_in_hand", "maria_scene_richter_on_the_throne", "familiar_graphics_maria",  # #203 #209 #208
    "shaft_orb_unseen_richter", "richter_blade_dash_damage",  # #189 #190
    "richter_left_hand_keeps_his_graphics", "stage_palettes_maria", "maria_run_into_a_step",  # #195 #206 #172
    "level_up_stats_maria", "hit_shows_its_number_maria",  # #171
    "offhand_crouching_swings_low_richter", "pause_menu_portrait_maria",  # +
    "ultimate_maria_subweapons", "partner_body_maria_and_ultimate_maria",  # + other mods' characters (D180)
    "saturn_maria_beasts", "partner_body_alucard_and_saturn_maria",  # + Saturn Maria (D181)
    "ultimate_richter_in_the_castle", "partner_body_alucard_and_ultimate_richter",  # + Ultimate Richter (D184)
    # bosses, cutscenes
    "boss_aggro_switches", "boss_dead_stays_down", "boss_both_hit_one_death", "mixed_party_boss",
    "edges_boss_pull_mid_door", "keep_scene_alucard_and_richter", "keep_scene_richter_and_maria",
    "boss_pulls_partner_in", "online_boss_rush", "scene_skips_once_both_players_ask",  # +
    "prologue_crawl_skips_on_start", "scene_pull_ignores_a_partner_mid_load",  # +
    # progression
    "items_and_maxups_shared", "online_joint_save", "test_castles_bundled",
    "relic_shared", "gold_pooled", "map_shared", "finds_caught_up_after_reconnect", "exactly_once_partition",  # +
    "save_room_real", "castle_solo_play", "red_door_guest_copy_in_place",  # +
    # traversal
    "bat_carry_alucard", "bat_carry_richter", "bat_carry_through_a_door", "bat_carry_is_slower",
    "bat_carry_jump_drops_off", "bat_carry_landing_drops_off", "bat_carry_a_hit_drops_off",
    "bat_carry_form_change_drops_off", "camera_limit_follows_the_guest", "edges_both_through_one_door_into_enemies",
    "teleport_partner_busy", "respawn_at_partner", "inverted_teleport_into", "walk_entrance_rooms",  # +
    "loader_in_game",  # +
    # rooms
    "guest_hits_count", "guest_scenery_matches_solo", "guest_sees_warg_death", "music_mute_in_shop",
    "puppet_same_room_only", "rolling_states_stay_cheap", "pickup_icon_matches_for_both_players",
    "no_effect_on_play", "char_select_session", "mixed_soak_short",
    "shared_same_enemies", "guest_gets_hurt", "guest_takes_heart", "targeting_nearer_player",  # +
    "partner_body_follows", "partner_status", "partner_hit_alucard",  # +
    # network
    "link_spec_conformance", "netplay_gate_alucard_and_richter", "ui_online", "ui_online_boss_rush",
    "edges_in_and_out_among_enemies_online",
    "online_connect_codes", "online_version_mismatch", "online_partner_leaves", "online_mtu_and_loss",  # +
    "online_in_process", "online_randomizer_seed_mismatch", "link_connect", "link_portmap",  # +
    "link_malformed", "link_layout",  # a packet that stopped the host's frame (2026-11-10); the mailbox's two copies
    # rules, pvp
    "rules_no_air_jumps", "rules_no_growth", "rules_no_offhand", "rules_damage_taken_richter", "pvp_familiar",
    "rules_reach_the_game", "rules_host_tells_joiner", "rules_richter_defense", "rules_damage_taken",  # +
    "pvp_off", "pvp_death", "pvp_spawn_protection",  # +
    # launcher, mods
    "launcher_characters", "ui_characters", "ui_couch", "ui_solo", "ui_startup", "ui_randomizer",
    "patcher_round_trip",
    "launcher_android_disc", "launcher_audio", "launcher_castles", "launcher_crash_window",  # +
    "launcher_report", "launcher_rules", "launcher_settings", "launcher_ship_lists", "ui_menus",  # +
    "launcher_link_errors",  # + the link failing never stops the game (D191)
    "launcher_ui", "launcher_gameart", "launcher_gamesound",  # + the menus in the game's style, and its art and sound from the disc (D192)
    "launcher_library", "patcher_modded",  # + game discs with several mods (D195)
    "patcher_layer", "rando_start_room_lycanthrope_spr26te",  # +
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

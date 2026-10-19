-- Cross-emulator check in PCSX-Redux, headless (scripts/redux_check.sh runs it with -cli -8mb).
-- Same route as harness/savestates.py + scenarios.heartbeat_8mb, driven by RAM pokes and pad overrides:
-- boot -> new game -> skip prologue -> castle entrance -> Bat Card on -> warp -> module heartbeat.
-- Prints one RESULT line and quits with 0 (pass) or 1 (fail).
local ffi = require("ffi")
local mem = ffi.cast("uint8_t*", PCSX.getMemPtr())
local pad = PCSX.SIO0.slots[1].pads[1]
local B = PCSX.CONSTS.PAD.BUTTON
local SYM = COOP_SYMBOLS -- injected by redux_check.sh
local out = io.open(COOP_RESULT_PATH, "w") -- Windows stdout doesn't reach WSL, so log to a file
local function log(s) out:write(s .. "\n"); out:flush() end

local function u32(a) return ffi.cast("uint32_t*", mem + bit.band(a, 0x7FFFFF))[0] end
local function w32(a, v) ffi.cast("uint32_t*", mem + bit.band(a, 0x7FFFFF))[0] = v end
local function w8(a, v) mem[bit.band(a, 0x7FFFFF)] = v end

local vsync, phase, t0 = 0, 1, 0
local status_copy
local beat0
local function finish(ok, msg)
    log(string.format("RESULT %s vsync=%d phase=%d gs=%d stage=0x%x %s", ok and "PASS" or "FAIL", vsync, phase,
        u32(SYM.g_GameState), u32(SYM.g_StageId), msg))
    PCSX.quit(ok and 0 or 1)
end
local function press(button, at, now) -- hold `button` for 2 vsyncs starting at `at`
    if now == at then pad.setOverride(button) elseif now == at + 2 then pad.clearOverride(button) end
end

-- New game inputs, as in savestates.new_game (vsync offsets)
local script = { { B.START, 1800 }, { B.CROSS, 2162 }, { B.CROSS, 2464 }, { B.CROSS, 2586 }, { B.START, 2608 } }

local phases = {
    function(n) -- 1: menus until prologue gameplay
        for _, s in ipairs(script) do press(s[1], s[2], n) end
        if u32(SYM.g_StageId) == 0x1F and u32(SYM.g_GameState) == 2 then log("prologue at vsync " .. n); return true end
        if n > 20000 then finish(false, "never reached the prologue") end
    end,
    function(n) -- 2: skip prologue (Game_PrologueEnd), wait for castle entrance gameplay
        if n - t0 == 600 then w32(SYM.g_GameState, 7); w32(SYM.g_GameStep, 0) end
        if n - t0 > 600 and u32(SYM.g_StageId) == 0x41 and u32(SYM.g_GameState) == 2 then log("entrance at vsync " .. n); return true end
        if n - t0 > 15000 then finish(false, "never reached the castle entrance") end
    end,
    function(n) -- 3: Bat Card on, warp to the Alchemy Lab keeping status (savestates.warp)
        if n - t0 == 600 then
            w8(SYM.g_Status + 18, 3)
            status_copy = ffi.new("uint8_t[?]", 0x334)
            ffi.copy(status_copy, mem + bit.band(SYM.g_Status, 0x7FFFFF), 0x334)
            w32(SYM.g_LoadOvlIdx, 0x0C); w32(SYM.g_StageId, 0x0C); w32(SYM.g_GameState, 4); w32(SYM.g_GameStep, 2)
        elseif status_copy and u32(SYM.g_GameStep) > 10 and u32(SYM.g_GameState) == 4 then
            ffi.copy(mem + bit.band(SYM.g_Status, 0x7FFFFF), status_copy, 0x334); status_copy = nil
        elseif n - t0 > 602 and not status_copy and u32(SYM.g_GameState) == 2 then log("warped at vsync " .. n); return true end
        if n - t0 > 5000 then finish(false, "warp never finished") end
    end,
    function(n) -- 4: module resident and ticking
        if n - t0 == 300 then
            if u32(SYM.g_Coop) ~= 0x504F4F43 then finish(false, string.format("module not resident (magic %08x)", u32(SYM.g_Coop))) end
            beat0 = u32(SYM.g_Coop + 8)
        elseif n - t0 == 900 then
            local beats = u32(SYM.g_Coop + 8) - beat0
            finish(beats >= 590 and beats <= 600, string.format("heartbeat +%d over 600 vsyncs", beats))
        end
    end,
}

Listener = PCSX.Events.createEventListener("GPU::Vsync", function()
    vsync = vsync + 1
    if phases[phase](vsync) then phase = phase + 1; t0 = vsync end
end)

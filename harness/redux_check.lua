-- Cross-emulator check in PCSX-Redux, headless (scripts/redux_check.sh runs it with -cli -8mb).
-- Same route as harness/savestates.py + scenarios.loader_*, driven by RAM pokes and pad overrides:
-- boot -> module resident at the title screen -> new game -> skip prologue -> castle entrance
-- -> module heartbeat still ticking once per game frame.
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
local beat0, timer0
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
    function(n) -- 1: menus until prologue gameplay; the module must be resident by the title screen
        for _, s in ipairs(script) do press(s[1], s[2], n) end
        if n == 1790 then
            if u32(SYM.g_CoopLink) ~= 0x504F4F43 then
                finish(false, string.format("module not resident at the title (magic %08x)", u32(SYM.g_CoopLink)))
            end
            log(string.format("title: module resident, heartbeat %d, g_Timer %d", u32(SYM.g_CoopLink + 8), u32(SYM.g_Timer)))
        end
        if u32(SYM.g_StageId) == 0x1F and u32(SYM.g_GameState) == 2 then log("prologue at vsync " .. n); return true end
        if n > 20000 then finish(false, "never reached the prologue") end
    end,
    function(n) -- 2: skip prologue (Game_PrologueEnd), wait for castle entrance gameplay
        if n - t0 == 600 then w32(SYM.g_GameState, 7); w32(SYM.g_GameStep, 0) end
        if n - t0 > 600 and u32(SYM.g_StageId) == 0x41 and u32(SYM.g_GameState) == 2 then log("entrance at vsync " .. n); return true end
        if n - t0 > 15000 then finish(false, "never reached the castle entrance") end
    end,
    function(n) -- 3: the heartbeat ticks once per game frame (g_Timer)
        if n - t0 == 300 then
            beat0, timer0 = u32(SYM.g_CoopLink + 8), u32(SYM.g_Timer)
        elseif n - t0 == 900 then
            local beats, frames = u32(SYM.g_CoopLink + 8) - beat0, u32(SYM.g_Timer) - timer0
            local left, top = u32(SYM.g_Tilemap + 0x2C), u32(SYM.g_Tilemap + 0x30)
            local engine = u32(SYM.g_GameEngineStep)
            finish(beats == frames and beats >= 290 and engine == 1 and (left ~= 0 or top ~= 0),
                string.format("heartbeat +%d over %d game frames, engine %d, room %d,%d", beats, frames, engine, left, top))
        end
    end,
}

Listener = PCSX.Events.createEventListener("GPU::Vsync", function()
    vsync = vsync + 1
    if phases[phase](vsync) then phase = phase + 1; t0 = vsync end
end)

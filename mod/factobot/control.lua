-- factobot game bridge.
--
-- The daemon calls `/factobot <method> <json params>` over RCON. Each call
-- prints exactly one JSON line: {"ok":true,"result":...,"tick":N} or
-- {"ok":false,"error":"...","code":"...","tick":N}, where `code` is set for
-- errors the caller caused (`rejected`, `bad_request`). An agent method's
-- line also has `hud` (agent.lua). `/factobot-dev <lua>`
-- runs arbitrary Lua for the harness's debug channel. Only RCON may call
-- either; players get an error. Agent methods live in agent.lua.

local agent = require("agent")
local milestones = require("milestones")

local methods = {}
for name, method in pairs(agent.methods) do
  methods[name] = method
end

function methods.status()
  return {
    tick = game.tick,
    tick_paused = game.tick_paused,
    speed = game.speed,
    game_version = script.active_mods["base"],
    mod_version = script.active_mods["factobot"],
    connected_players = #game.connected_players,
  }
end

-- 32-bit FNV-1a, folded into an order-independent sum so the hash does not
-- depend on the order find_entities returns.
local FNV_PRIME = 16777619
local function fnv1a(text)
  local hash = 2166136261
  for i = 1, #text do
    hash = bit32.bxor(hash, text:byte(i))
    -- Multiply modulo 2^32 in two halves so doubles stay exact.
    hash = (
      bit32.band(hash, 0xffff) * FNV_PRIME
      + bit32.band(bit32.rshift(hash, 16) * FNV_PRIME, 0xffff) * 0x10000
    ) % 0x100000000
  end
  return hash
end

local function entity_fingerprint(entity)
  local parts = {
    entity.name,
    string.format("%.4f,%.4f", entity.position.x, entity.position.y),
    tostring(entity.direction),
    entity.force.name,
  }
  if entity.type == "resource" then
    parts[#parts + 1] = tostring(entity.amount)
  end
  return table.concat(parts, "|")
end

-- Deterministic fingerprint of every entity on the main surface, returned
-- with the tick it was taken at. Same seed and same inputs at the same ticks
-- must give the same hash.
function methods.world_hash()
  local surface = game.surfaces[1]
  local sum = 0
  local count = 0
  for _, entity in pairs(surface.find_entities()) do
    sum = (sum + fnv1a(entity_fingerprint(entity))) % 0x100000000
    count = count + 1
  end
  return { tick = game.tick, entities = count, hash = string.format("%08x", sum) }
end

-- Every player is a spectator: the harness's camera and viewer clients, and
-- anyone who joins through `fac watch`. The agent is a character with no
-- player, so no player needs a body. Without one a player can't build, mine
-- or touch an inventory, so connecting never changes the world, whatever
-- name a client joins under.
--
-- A spectator can still send input actions (queue research, chat, run
-- console commands, change entity settings), so every player also goes into
-- a permission group that allows only looking around (decision 38). The
-- daemon reaches the game over RCON, which no permission group limits.
local SPECTATOR_GROUP = "factobot-spectators"
local SPECTATOR_ACTIONS = {
  "start_walking", -- moves the spectator camera
  "remote_view_surface",
  "remote_view_entity",
  "spectator_change_surface",
  "toggle_show_entity_info",
  "open_production_gui",
  "open_bonus_gui",
  "open_achievements_gui",
  "open_trains_gui",
  "open_logistics_gui",
  "open_global_electric_network_gui",
}

-- Creates the group, or resets an existing one to exactly the allow-list.
local function spectator_group()
  local group = game.permissions.get_group(SPECTATOR_GROUP)
    or game.permissions.create_group(SPECTATOR_GROUP)
  ---@cast group LuaPermissionGroup
  for _, action in pairs(defines.input_action) do
    group.set_allows_action(action, false)
  end
  for _, name in ipairs(SPECTATOR_ACTIONS) do
    group.set_allows_action(defines.input_action[name], true)
  end
  return group
end

local function make_spectator(player)
  if not player then
    return
  end
  local body = player.character or player.cutscene_character
  player.set_controller({ type = defines.controllers.spectator })
  if body and body.valid then
    body.destroy()
  end
  local group = game.permissions.get_group(SPECTATOR_GROUP) or spectator_group()
  group.add_player(player)
end

script.on_event(defines.events.on_player_joined_game, function(event)
  make_spectator(game.get_player(event.player_index))
end)

-- Freeplay sets up the world when the first player is created: it builds
-- the crash site wreck, charts the starting area and plays an intro. That
-- would make the world depend on whether a camera, a viewer or the agent
-- joined first, so the benchmark (decision 27) turns the wreck and intro off
-- and charts the same starting area itself when the map is created. The
-- wreck's items still go to the player's inventory.
local CHART_RADIUS = 200 -- freeplay's default chart distance

local function configure_freeplay()
  local freeplay = remote.interfaces["freeplay"]
  if not freeplay then
    return
  end
  remote.call("freeplay", "set_skip_intro", true)
  remote.call("freeplay", "set_disable_crashsite", true)
end

local function reveal_start()
  local force = game.forces["player"]
  local surface = game.surfaces[1]
  agent.reveal_start(surface, force, force.get_spawn_position(surface), CHART_RADIUS)
end

script.on_init(function()
  configure_freeplay()
  reveal_start()
  agent.ensure_body()
  milestones.init()
  spectator_group()
end)
-- Runs when a save made with another mod version loads (bump info.json's
-- version with any change to `storage`). A save from before the agent had a
-- body gets one, with the starting area explored. Milestones migrate first,
-- so the crafts migrate_crafts credits count on top of their baseline.
script.on_configuration_changed(function()
  configure_freeplay()
  milestones.migrate()
  if storage.agent == nil then
    reveal_start()
  elseif storage.agent.crafts.queue == nil then
    agent.migrate_crafts()
  end
  agent.ensure_body()
  local group = spectator_group()
  for _, player in pairs(game.players) do
    group.add_player(player)
  end
end)
-- Milestones look at the statistics before the agent credits the crafts
-- that finished on the previous tick (milestones.lua says why).
script.on_event(defines.events.on_tick, function(event)
  milestones.on_tick(event)
  agent.on_tick()
end)
script.on_event(defines.events.on_script_path_request_finished, agent.on_path)
script.on_event(defines.events.on_rocket_launched, milestones.on_rocket_launched)

-- Science and rocket milestones for the harness (dev socket only).
methods.milestones = milestones.report

-- Whether a player of this name is connected (the daemon waits on this
-- after launching a camera or viewer client).
function methods.player_connected(params)
  local player = game.get_player(params.name)
  return player ~= nil and player.connected
end

-- What a camera's screenshots leave out: every panel of the camera's own GUI.
local CAMERA_HIDDEN = {
  "show_alert_gui",
  "show_controller_gui",
  "show_crafting_queue",
  "show_entity_tooltip",
  "show_hotkey_suggestions",
  "show_map_view_options",
  "show_minimap",
  "show_pins_gui",
  "show_quickbar",
  "show_research_info",
  "show_shortcut_bar",
  "show_side_menu",
  "show_surface_list",
  "show_tool_bar",
  "update_entity_selection",
}

-- Tile coordinates over a screenshot (decision 78): a line along the tile
-- edges every `step` tiles and "x,y" at each crossing, drawn for the camera
-- alone so no spectator sees it. The lines of the last screenshot go first:
-- the camera renders the picture after this call returns, so they stay
-- until the next one.
local GRID_LINE = { 1, 1, 1, 0.22 }
local GRID_TEXT = { 1, 1, 1, 0.9 }

local function draw_grid(camera, position, params)
  for _, object in pairs(storage.screen_grid or {}) do
    if object.valid then
      object.destroy()
    end
  end
  storage.screen_grid = {}
  local step = params.grid
  if not step then
    return
  end
  local drawn = storage.screen_grid
  local half_width = params.width / (64 * params.zoom)
  local half_height = params.height / (64 * params.zoom)
  local left, right = position.x - half_width, position.x + half_width
  local top, bottom = position.y - half_height, position.y + half_height
  local surface = camera.surface
  local players = { camera }
  for x = math.ceil(left / step) * step, right, step do
    drawn[#drawn + 1] = rendering.draw_line({
      surface = surface,
      from = { x, top },
      to = { x, bottom },
      color = GRID_LINE,
      width = 1,
      players = players,
    })
    for y = math.ceil(top / step) * step, bottom, step do
      drawn[#drawn + 1] = rendering.draw_text({
        surface = surface,
        text = string.format("%d,%d", x, y),
        target = { x + 0.1, y },
        color = GRID_TEXT,
        scale = 1.2,
        scale_with_zoom = true,
        players = players,
      })
    end
  end
  for y = math.ceil(top / step) * step, bottom, step do
    drawn[#drawn + 1] = rendering.draw_line({
      surface = surface,
      from = { left, y },
      to = { right, y },
      color = GRID_LINE,
      width = 1,
      players = players,
    })
  end
end

-- Render a PNG with the daemon's camera client (the dev `screenshot` and the
-- agent's `screen`; the daemon waits for the file). It is centred on
-- {x, y}, or on the agent's body when they are left out, and taken at the
-- surface's own daytime unless `daytime` overrides it. Warning icons (no
-- power, unplugged, no fuel, ...) are drawn with the GUI, so the shot keeps
-- the GUI and the camera hides every panel of its own, and its console.
-- `grid` lays tile coordinates over it every that many tiles.
function methods.screenshot(params)
  local camera = game.get_player(params.player)
  if not (camera and camera.connected) then
    error({ code = "unavailable", message = "the camera is not connected" }, 0)
  end
  local position = params.x and { x = params.x, y = params.y } or agent.body_position()
  local view = camera.game_view_settings
  for _, setting in ipairs(CAMERA_HIDDEN) do
    view[setting] = false
  end
  camera.clear_console()
  draw_grid(camera, position, params)
  game.take_screenshot({
    player = camera,
    position = position,
    resolution = { params.width, params.height },
    zoom = params.zoom,
    path = params.path,
    show_gui = true,
    show_entity_info = true,
    daytime = params.daytime,
    force_render = true,
  })
  return { center = { x = position.x, y = position.y } }
end

local function reply(payload)
  payload.tick = game.tick
  rcon.print(helpers.table_to_json(payload))
end

local function from_rcon_only(command)
  if command.player_index ~= nil then
    local player = game.get_player(command.player_index)
    if player then
      player.print("factobot: this command is for the daemon only")
    end
    return false
  end
  return true
end

commands.add_command("factobot", "factobot daemon interface (RCON only)", function(command)
  if not from_rcon_only(command) then
    return
  end

  local name, raw_params = (command.parameter or ""):match("^(%S+)%s*(.*)$")
  local method = name and methods[name]
  if not method then
    reply({ ok = false, error = "unknown mod method: " .. tostring(name) })
    return
  end

  local params = {}
  if raw_params ~= "" and raw_params ~= "null" then
    local decoded = helpers.json_to_table(raw_params)
    if type(decoded) ~= "table" then
      reply({ ok = false, code = "bad_request", error = "params must be a JSON object" })
      return
    end
    params = decoded
  end

  -- `fac ... --wait` starts its job with hud = "defer" and polls it with
  -- hud = "skip", so only the answer it prints says the warnings (protocol.md).
  local hud_mode = params.hud
  if hud_mode ~= nil and hud_mode ~= "defer" and hud_mode ~= "skip" then
    reply({ ok = false, code = "bad_request", error = 'hud must be "defer" or "skip"' })
    return
  end
  params.hud = nil

  local ok, result = pcall(method, params)
  -- Agent methods carry the HUD, whether they worked or not. A start that
  -- failed is printed as it is, so it does not defer.
  local hud = nil
  if agent.methods[name] and hud_mode ~= "skip" then
    hud = agent.hud(ok and hud_mode == "defer")
  end
  if ok then
    reply({ ok = true, result = result, hud = hud })
  elseif type(result) == "table" then
    reply({ ok = false, code = result.code, error = result.message, hud = hud })
  else
    reply({ ok = false, error = tostring(result), hud = hud })
  end
end)

-- JSON cannot carry game objects (LuaEntity, LuaSurface, ...) or functions:
-- table_to_json drops them silently. Describe them as text instead.
local function encodable(value)
  if type(value) == "userdata" or type(value) == "function" then
    return tostring(value)
  end
  return value
end

commands.add_command("factobot-dev", "factobot harness debug channel (RCON only)", function(command)
  if not from_rcon_only(command) then
    return
  end

  local code = command.parameter or ""
  -- Try it as an expression first so `game.tick` returns a value.
  local chunk = load("return " .. code, "=factobot-dev", "t")
  if not chunk then
    local err
    chunk, err = load(code, "=factobot-dev", "t")
    if not chunk then
      reply({ ok = false, error = "syntax error: " .. tostring(err) })
      return
    end
  end

  local ok, result = pcall(chunk)
  if ok then
    reply({ ok = true, result = encodable(result) })
  else
    reply({ ok = false, error = tostring(result) })
  end
end)

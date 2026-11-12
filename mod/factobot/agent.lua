-- The agent's body and its actions (decisions 30 to 37, 39 to 41 and 49 to 56).
--
-- The agent is a `character` entity with no player attached. Its actions run
-- as jobs in game time: `walk`, `mine` and `place_line` use the body, so a
-- new one cancels the running one, and `craft` goes into the character's own
-- hand-craft queue. Placing, inserting, taking and rotating are instant, as
-- for a player. The engine enforces walking speed, reach, mining speed, craft
-- times and what machines accept; this file starts actions, steers along
-- paths, checks build reach and keeps score.

local milestones = require("milestones")

local M = {}

local CHUNK = 32
local CHART_CHUNK_RADIUS = 2 -- a player's character reveals 5x5 chunks
local WAYPOINT_REACHED = 0.3
local ARRIVED = 0.25 -- steps are 0.15 tiles, so steering always closes to this
local PROGRESS = 0.05 -- getting this much nearer the waypoint is progress
local STUCK_TICKS = 120
-- The pathfinder can end a route on a tile centre the body can't quite
-- stand on (probed: one beside a huge rock), and steering then circles it
-- for ever. A waypoint this near that the body gets no nearer to for
-- SETTLE_TICKS counts as reached.
local NEAR_ENOUGH = 0.5
local SETTLE_TICKS = 30
local STUCK = "stuck: no progress for 2 seconds"
local PATH_TIMEOUT_TICKS = 600 -- the pathfinder answers well within this for allowed walks
local WALK_MAX_DISTANCE = 500
local MAX_KEPT_JOBS = 100
local OBSERVE_RADIUS = 10
local OBSERVE_MAX_RADIUS = 32
local OBSERVE_MAX_ENTITIES = 50
local MINE_MAX_COUNT = 1000
local CRAFT_MAX_COUNT = 1000
local WALK_MAX_WITHIN = 10
-- Mined with the shorter resource reach, as the engine does (probed).
local NATURAL = { resource = true, tree = true, ["simple-entity"] = true }
-- Fish are mined from the water's edge with interaction reach, as buildings
-- are (probed: the engine mines a fish 9.5 tiles from its box but not 10.5).
local FISH = "fish"

-- Errors the agent caused carry a code the daemon passes on.
local function fail(code, message)
  error({ code = code, message = message }, 0)
end

local function reject(message)
  fail("rejected", message)
end

local function bad_params(message)
  fail("bad_request", message)
end

local function round(value)
  return math.floor(value * 100 + 0.5) / 100
end

local function point(position)
  return { x = round(position.x), y = round(position.y) }
end

local function distance(a, b)
  local dx, dy = a.x - b.x, a.y - b.y
  return math.sqrt(dx * dx + dy * dy)
end

local function number_param(params, key, default, min, max)
  local value = params[key]
  if value == nil then
    if default == nil then
      bad_params(key .. " is required")
    end
    return default
  end
  if type(value) ~= "number" or value ~= value or value < min or value > max then
    bad_params(string.format("%s must be a number from %s to %s", key, min, max))
  end
  return value
end

local function position_param(params)
  local x = number_param(params, "x", nil, -1e6, 1e6)
  local y = number_param(params, "y", nil, -1e6, 1e6)
  return { x = x, y = y }
end

-- Body -----------------------------------------------------------------------

local function state()
  storage.agent = storage.agent
    or {
      jobs = {},
      next_job = 1,
      oldest_job = 1,
      craft_jobs = {}, -- running craft job ids, in queue order
      crafts = { queue = {}, completed = 0 }, -- queue as last seen, head first
      explored = {},
    }
  return storage.agent
end

---@return LuaEntity
local function body()
  local character = state().character
  if not (character and character.valid) then
    fail("unavailable", "the agent has no body")
  end
  ---@cast character LuaEntity
  return character
end

-- Where the body stands: the centre of the agent's screenshots (decision 67).
function M.body_position()
  return body().position
end

-- Mark chunks between two chunk positions as explored: the agent's map
-- queries see them. The headless server builds no chart of its own when no
-- client is connected (probed: `force.chart` leaves `is_chunk_charted`
-- false), so the mod keeps the explored set. It still charts the area for
-- any viewer that is watching.
local function reveal(surface, force, left, top, right, bottom)
  local explored = state().explored
  for cx = left, right do
    for cy = top, bottom do
      explored[cx .. "," .. cy] = { x = cx, y = cy }
    end
  end
  force.chart(
    surface,
    { { left * CHUNK, top * CHUNK }, { (right + 1) * CHUNK - 1, (bottom + 1) * CHUNK - 1 } }
  )
end

-- Reveal the area a freeplay player starts with (tiles around a point).
function M.reveal_start(surface, force, origin, radius)
  reveal(
    surface,
    force,
    math.floor((origin.x - radius) / CHUNK),
    math.floor((origin.y - radius) / CHUNK),
    math.floor((origin.x + radius) / CHUNK),
    math.floor((origin.y + radius) / CHUNK)
  )
end

-- A player's character reveals the 5x5 chunks around it, and the game
-- generates the terrain there.
local function chart_around(character)
  local cx = math.floor(character.position.x / CHUNK)
  local cy = math.floor(character.position.y / CHUNK)
  local s = state()
  if s.chunk and s.chunk.x == cx and s.chunk.y == cy then
    return
  end
  s.chunk = { x = cx, y = cy }
  local surface = character.surface
  surface.request_to_generate_chunks(character.position, CHART_CHUNK_RADIUS)
  surface.force_generate_chunk_requests()
  reveal(
    surface,
    character.force,
    cx - CHART_CHUNK_RADIUS,
    cy - CHART_CHUNK_RADIUS,
    cx + CHART_CHUNK_RADIUS,
    cy + CHART_CHUNK_RADIUS
  )
end

-- Jobs -----------------------------------------------------------------------

local function new_job(kind, fields)
  local s = state()
  local job = fields
  job.id = s.next_job
  job.kind = kind
  job.state = "running"
  job.started_tick = game.tick
  s.next_job = s.next_job + 1
  s.jobs[job.id] = job
  -- Keep the latest jobs only; a job still running stays until it ends.
  while s.next_job - s.oldest_job > MAX_KEPT_JOBS do
    local old = s.jobs[s.oldest_job]
    if old and old.state == "running" then
      break
    end
    s.jobs[s.oldest_job] = nil
    s.oldest_job = s.oldest_job + 1
  end
  return job
end

local function finish(job, final_state, fields)
  job.state = final_state
  job.ended_tick = game.tick
  for key, value in pairs(fields or {}) do
    job[key] = value
  end
  local s = state()
  if s.body_job == job.id then
    s.body_job = nil
  end
end

-- Create the body at the spawn point with freeplay's starting items, once.
function M.ensure_body()
  local s = state()
  if s.character and s.character.valid then
    return
  end
  local surface = game.surfaces[1]
  local force = game.forces["player"]
  local spawn = force.get_spawn_position(surface)
  local position = surface.find_non_colliding_position("character", spawn, 10, 0.5) or spawn
  local character =
    surface.create_entity({ name = "character", position = position, force = force })
  if not character then
    error("could not create the agent's character")
  end
  local items = remote.interfaces["freeplay"] and remote.call("freeplay", "get_created_items") or {}
  for name, count in pairs(items) do
    character.insert({ name = name, count = count })
  end
  s.character = character
  s.chunk = nil
  -- A new body has an empty craft queue. Crafts the old one had queued were
  -- never made: they must not be counted as finished, and their jobs end
  -- now, or later craft jobs would wait behind them forever.
  s.crafts.queue = {}
  for _, id in ipairs(s.craft_jobs) do
    local job = s.jobs[id]
    if job and job.state == "running" then
      finish(job, "failed", { error = "the body was lost before the craft finished" })
    end
  end
  s.craft_jobs = {}
  chart_around(character)
end

local function stop_body(character)
  character.walking_state = { walking = false, direction = defines.direction.north }
  character.mining_state = { mining = false }
end

-- Cancel the walk or mine job using the body, if any. Returns the job it
-- stopped, as {id, kind}, for the job that takes the body to show.
local function release_body(character, reason)
  local s = state()
  local job = s.body_job and s.jobs[s.body_job]
  local cut
  if job and job.state == "running" then
    if job.kind == "mine" then
      job.mined = M.mined_so_far(character, job)
      job.entity = nil
    end
    finish(job, "cancelled", { error = reason })
    cut = { id = job.id, kind = job.kind }
  end
  s.body_job = nil
  stop_body(character)
  return cut
end

-- The queue as a list of {recipe, count}, head first.
local function queue_snapshot(character)
  local list = {}
  for _, entry in pairs(character.crafting_queue or {}) do
    list[#list + 1] = { recipe = entry.recipe, count = entry.count }
  end
  return list
end

local function total_crafts(queue)
  local total = 0
  for _, entry in ipairs(queue) do
    total = total + entry.count
  end
  return total
end

-- How many crafts a running craft job still waits for, its own included,
-- and the tick it should be done on: what is left of the craft in hand
-- plus the craft time of every craft queued up to its own at the
-- character's crafting speed, with the tick the engine leaves between
-- crafts and the tick on which the job sees the last one finish. Crafts
-- that finished since on_tick last counted are left out.
local function craft_progress(job)
  local s = state()
  local character = s.character
  local ahead = job.done_at - s.crafts.completed
  if not (character and character.valid) then
    return math.max(ahead, 0), nil
  end
  local queue = queue_snapshot(character)
  ahead = math.max(ahead - (total_crafts(s.crafts.queue) - total_crafts(queue)), 0)
  local speed = 1
    + character.character_crafting_speed_modifier
    + character.force.manual_crafting_speed_modifier
  local ticks, left = 0, ahead
  for index, entry in ipairs(queue) do
    if left == 0 then
      break
    end
    local crafts = math.min(entry.count, left)
    local each = prototypes.recipe[entry.recipe].energy * 60 / speed
    ticks = ticks + crafts * (each + 1)
    if index == 1 then
      ticks = ticks - character.crafting_queue_progress * each
    end
    left = left - crafts
  end
  return ahead, game.tick + math.ceil(ticks) + 1
end

-- Position of the line's tile at a 1-based index. One past the far end is
-- the far end itself, so a line with spacing ends where it was asked to.
local function line_tile(job, index)
  local along = math.abs(job.step.x + job.step.y) * (index - 1)
  if along >= math.abs(job.to.x - job.from.x) + math.abs(job.to.y - job.from.y) then
    return job.to
  end
  return {
    x = job.from.x + job.step.x * (index - 1),
    y = job.from.y + job.step.y * (index - 1),
  }
end

-- How far a place_line job got, in words.
local function line_progress(job)
  local text = string.format("placed %d of %d", job.next_index - 1, job.tiles)
  if job.next_index <= job.tiles then
    local next_tile = line_tile(job, job.next_index)
    text = text .. string.format("; the next goes at %s, %s", next_tile.x, next_tile.y)
  end
  return text
end

-- End a place_line job once the walk beside the line has ended. With every
-- building down it is done, and says how far short of the last one the body
-- stopped if the walk didn't get beside it; otherwise it failed, saying why
-- and how far it got.
local function end_line(character, job, outcome)
  stop_body(character)
  if job.next_index <= job.tiles then
    if outcome == "arrived" then
      outcome = "the walk beside the line ended out of build reach of the next one"
    end
    finish(job, "failed", { error = string.format("%s; %s", outcome, line_progress(job)) })
  elseif outcome == "arrived" then
    finish(job, "done")
  else
    local away = distance(character.position, line_tile(job, job.tiles))
    finish(job, "done", {
      stopped_short = string.format("%s; you are %.1f tiles from the last one", outcome, away),
    })
  end
end

-- What a job looks like to the agent.
local function describe(job)
  local view = {
    id = job.id,
    kind = job.kind,
    state = job.state,
    started_tick = job.started_tick,
    ended_tick = job.ended_tick,
    error = job.error,
    -- The walk, mine or line this job stopped when it took the body.
    cut_short = job.cut_short,
  }
  if job.kind == "walk" then
    view.target = job.target
    view.position = job.position
    view.distance_walked = job.walked and round(job.walked)
  elseif job.kind == "mine" then
    view.target = { name = job.target_name, position = job.target_position }
    view.count = job.count
    view.mined = job.mined
  elseif job.kind == "craft" then
    view.recipe = job.recipe
    view.count = job.count
    view.used = job.used
    if job.state == "running" then
      view.crafts_ahead, view.eta_tick = craft_progress(job)
    else
      view.crafts_ahead = 0
    end
  elseif job.kind == "place_line" then
    view.item = job.item
    view.from = job.from
    view.to = line_tile(job, job.tiles)
    view.direction = job.facing_name
    view.tiles = job.tiles
    view.placed = job.placed
    view.already_there = job.already_there
    if job.next_index <= job.tiles then
      view.next = line_tile(job, job.next_index)
    end
    view.position = job.position
    view.distance_walked = round(job.walked)
    view.stopped_short = job.stopped_short
  end
  return view
end

-- Walking --------------------------------------------------------------------

-- The eight directions a player can walk, by sector of the angle from east,
-- clockwise (the map's y axis points south).
local SECTORS = {
  defines.direction.east,
  defines.direction.southeast,
  defines.direction.south,
  defines.direction.southwest,
  defines.direction.west,
  defines.direction.northwest,
  defines.direction.north,
  defines.direction.northeast,
}

local function direction_towards(from, to)
  local angle = math.atan2(to.y - from.y, to.x - from.x)
  local sector = math.floor(angle / (math.pi / 4) + 0.5) % 8
  return SECTORS[sector + 1]
end

local function generate_route_chunks(surface, from, to)
  local steps = math.max(1, math.ceil(distance(from, to) / CHUNK))
  for i = 0, steps do
    local t = i / steps
    surface.request_to_generate_chunks(
      { from.x + (to.x - from.x) * t, from.y + (to.y - from.y) * t },
      1
    )
  end
  surface.force_generate_chunk_requests()
end

local function request_route(character, job)
  local surface = character.surface
  generate_route_chunks(surface, character.position, job.target)
  local prototype = character.prototype
  job.path_request = surface.request_path({
    bounding_box = prototype.collision_box,
    collision_mask = prototype.collision_mask,
    start = character.position,
    goal = job.target,
    force = character.force,
    radius = job.within,
    entity_to_ignore = character,
    can_open_gates = true,
    -- Not prefer_straight_paths: on open ground it gave a 75-tile route
    -- for a 38-tile walk (diagonal first, then straight back).
    pathfind_flags = { cache = false, no_break = true },
  })
end

local function walk(params)
  local character = body()
  local target = position_param(params)
  local within = number_param(params, "within", 1, 0, WALK_MAX_WITHIN)
  local away = distance(character.position, target)
  if away > WALK_MAX_DISTANCE then
    reject(
      string.format(
        "that is %.0f tiles away; one walk goes at most %d tiles",
        away,
        WALK_MAX_DISTANCE
      )
    )
  end
  local cut = release_body(character, "replaced by a new walk")
  local job = new_job("walk", { target = target, within = within, walked = 0 })
  job.cut_short = cut
  state().body_job = job.id
  request_route(character, job)
  return describe(job)
end

-- Move the body one tick along the job's route. Returns nil while it is
-- still on the way, "arrived" within `within` of the target or at the end of
-- the route, or why it stopped.
local function steer(character, job)
  local path = job.path
  if not path then
    if game.tick - job.started_tick > PATH_TIMEOUT_TICKS then
      return "no path: the pathfinder gave no route in 10 seconds"
    end
    return nil -- waiting for the pathfinder
  end
  local position = character.position
  if job.last_position then
    job.walked = job.walked + distance(position, job.last_position)
  end
  job.last_position = { x = position.x, y = position.y }
  job.position = point(position)
  if distance(position, job.target) <= job.within then
    stop_body(character)
    return "arrived"
  end

  local waypoint = path[job.waypoint]
  local last = job.waypoint == #path
  while not last and distance(position, waypoint) < WAYPOINT_REACHED do
    job.waypoint = job.waypoint + 1
    job.closest = nil
    waypoint = path[job.waypoint]
    last = job.waypoint == #path
  end
  local away = distance(position, waypoint)
  if last and away < ARRIVED then
    stop_body(character)
    return "arrived"
  end

  -- Progress is getting nearer the waypoint, so walking round and round one
  -- isn't progress.
  if away < (job.closest or math.huge) - PROGRESS then
    job.closest = away
    job.progress_tick = game.tick
  else
    local held = game.tick - job.progress_tick
    if away < NEAR_ENOUGH and held >= SETTLE_TICKS then
      if last then
        stop_body(character)
        return "arrived"
      end
      job.waypoint = job.waypoint + 1
      job.closest = nil
      waypoint = path[job.waypoint]
    elseif held > STUCK_TICKS then
      stop_body(character)
      return STUCK
    end
  end

  local direction = direction_towards(position, waypoint)
  if direction ~= job.direction then
    job.direction = direction
    character.walking_state = { walking = true, direction = direction }
  end
  return nil
end

local function step_walk(character, job)
  local outcome = steer(character, job)
  if outcome == "arrived" then
    finish(job, "done")
  elseif outcome == STUCK then
    local away = distance(character.position, job.target)
    finish(job, "failed", { error = string.format("%s, %.1f tiles from the target", STUCK, away) })
  elseif outcome then
    finish(job, "failed", { error = outcome })
  end
end

-- Why the pathfinder found no route, as near as the mod can tell. The
-- pathfinder only says it failed, so the mod flood-fills the tiles where it
-- would route the character, from the agent and from the target: those
-- where the character fits standing at the tile's centre (probed: the
-- pathfinder won't route between two inserters, poles or furnaces standing
-- side by side, though the character fits between them), plus a diagonal
-- step between two obstacles that meet at a corner where the character fits
-- at the corner point (probed on 2.1.24: the pathfinder steps between walls,
-- poles, inserters and pipes that way, not between iron chests). A fill that
-- runs out of tiles before ENCLOSED_MAX_TILES is closed in.
local ENCLOSED_MAX_TILES = 1600
local NEIGHBOURS = { { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }
local DIAGONALS = { { 1, 1 }, { 1, -1 }, { -1, 1 }, { -1, -1 } }

-- What stops the character standing at a point: an entity it collides
-- with, "water" (any tile it can't walk on), or nil when it fits there.
local function in_the_way(character, layers, p)
  local box = character.prototype.collision_box
  local area = {
    { p.x + box.left_top.x, p.y + box.left_top.y },
    { p.x + box.right_bottom.x, p.y + box.right_bottom.y },
  }
  local surface = character.surface
  for _, other in pairs(surface.find_entities_filtered({ area = area, collision_mask = layers })) do
    if other ~= character then
      return other
    end
  end
  if surface.count_tiles_filtered({ area = area, collision_mask = layers }) > 0 then
    return "water"
  end
  return nil
end

local function tile_centre(i, j)
  return { x = i + 0.5, y = j + 0.5 }
end

-- Whether a point lies on the explored map, where the agent can see what
-- stands; the fills below read nothing beyond it.
local function on_map(p)
  return state().explored[math.floor(p.x / CHUNK) .. "," .. math.floor(p.y / CHUNK)] ~= nil
end

-- Flood-fill from the free tile nearest a position. Returns whether the
-- room there is closed, how many tiles it has, what bounds it and the set
-- of its tiles keyed "i,j"; nothing when no tile next to the position is
-- free. A room that reaches unexplored map isn't known to be closed.
local function room_around(character, layers, from)
  local candidates = {}
  for di = -1, 1 do
    for dj = -1, 1 do
      local i, j = math.floor(from.x) + di, math.floor(from.y) + dj
      candidates[#candidates + 1] = { i, j, distance(from, tile_centre(i, j)) }
    end
  end
  table.sort(candidates, function(a, b)
    return a[3] < b[3]
  end)
  local start
  for _, candidate in ipairs(candidates) do
    local p = tile_centre(candidate[1], candidate[2])
    if not start and on_map(p) and not in_the_way(character, layers, p) then
      start = { candidate[1], candidate[2] }
    end
  end
  if not start then
    return nil
  end
  local seen = { [start[1] .. "," .. start[2]] = true }
  local free = { [start[1] .. "," .. start[2]] = true }
  local blocked = {}
  local stack, tiles, bounds = { start }, 0, {}
  -- Look at a tile not seen yet; false when it is off the explored map.
  local function visit(i, j)
    local key = i .. "," .. j
    seen[key] = true
    local p = tile_centre(i, j)
    if not on_map(p) then
      return false
    end
    local what = in_the_way(character, layers, p)
    if what then
      blocked[key] = true
      bounds[#bounds + 1] = { what = what, at = p }
    else
      free[key] = true
      stack[#stack + 1] = { i, j }
    end
    return true
  end
  while #stack > 0 do
    local cell = table.remove(stack)
    tiles = tiles + 1
    if tiles > ENCLOSED_MAX_TILES then
      return false
    end
    local ci, cj = cell[1], cell[2]
    for _, step in ipairs(NEIGHBOURS) do
      local i, j = ci + step[1], cj + step[2]
      if not seen[i .. "," .. j] and not visit(i, j) then
        return false
      end
    end
    -- With either tile beside a diagonal step free, the steps above get
    -- there; with both blocked only the corner point between them can.
    for _, step in ipairs(DIAGONALS) do
      local i, j = ci + step[1], cj + step[2]
      if
        not seen[i .. "," .. j]
        and blocked[i .. "," .. cj]
        and blocked[ci .. "," .. j]
        and not in_the_way(character, layers, { x = math.max(i, ci), y = math.max(j, cj) })
        and not visit(i, j)
      then
        return false
      end
    end
  end
  return true, tiles, bounds, free
end

-- What is in the way, in words: "water", or a name and position.
local function obstacle(what, at)
  if what == "water" then
    return string.format("water at %s, %s", round(at.x), round(at.y))
  end
  return string.format("%s at %s, %s", what.name, round(what.position.x), round(what.position.y))
end

local function is_own(character, entity)
  return entity.force.name == character.force.name and entity.type ~= "character"
end

-- Whether `mine` would take a thing bounding a room: rocks, trees and the
-- agent's own buildings, not water, cliffs or other forces' buildings.
local function mineable(character, what)
  return what ~= "water"
    and (NATURAL[what.type] or is_own(character, what))
    and what.prototype.mineable_properties.minable
end

-- The thing bounding a room nearest to a point, of those `keep` accepts
-- when given.
local function nearest_bound(bounds, to, keep)
  local best, best_away
  for _, bound in ipairs(bounds) do
    local away = distance(bound.what == "water" and bound.at or bound.what.position, to)
    if (not keep or keep(bound.what)) and (not best_away or away < best_away) then
      best, best_away = obstacle(bound.what, bound.at), away
    end
  end
  return best
end

-- Whether the water at a tile is one body with water bounding a room: the
-- fill runs through water on the explored map from the tile until it meets
-- the room's free tiles, or gives up past ENCLOSED_MAX_TILES.
local function water_touches(character, layers, from, free)
  local start = { math.floor(from.x), math.floor(from.y) }
  local seen = { [start[1] .. "," .. start[2]] = true }
  local stack, tiles = { start }, 0
  while #stack > 0 do
    local cell = table.remove(stack)
    tiles = tiles + 1
    if tiles > ENCLOSED_MAX_TILES then
      return false
    end
    for _, step in ipairs(NEIGHBOURS) do
      local i, j = cell[1] + step[1], cell[2] + step[2]
      local key = i .. "," .. j
      if free[key] then
        return true
      end
      if not seen[key] then
        seen[key] = true
        local p = tile_centre(i, j)
        if on_map(p) and in_the_way(character, layers, p) == "water" then
          stack[#stack + 1] = { i, j }
        end
      end
    end
  end
  return false
end

-- The collision layers the character walks into.
local function walk_layers(character)
  local layers = {}
  for layer in pairs(character.prototype.collision_mask.layers) do
    layers[#layers + 1] = layer
  end
  return layers
end

-- `line` says the route is a place_line job's walk to beside the line's far
-- end, a point the mod picked, so the advice names that walk, not a target.
-- `unfinished` says belts are still to come, so the advice may be about the
-- line itself; once it is all down, changing the line no longer helps.
local function no_path_reason(character, target, line, unfinished)
  local layers = walk_layers(character)
  local here = character.position
  local closed, room, bounds, free = room_around(character, layers, here)
  -- What stands at the target shows only on the explored map, as on a
  -- player's map view.
  local explored = on_map(target)
  local inside = explored and in_the_way(character, layers, target)
  if closed then
    -- A target in the agent's own room, or in something bounding it, needs
    -- no way out.
    local reachable = free and free[math.floor(target.x) .. "," .. math.floor(target.y)]
    if inside == "water" and not reachable then
      reachable = water_touches(character, layers, target, free)
    elseif inside and not reachable then
      for _, bound in ipairs(bounds or {}) do
        if bound.what == inside then
          reachable = true
          break
        end
      end
    end
    if not reachable then
      local way_out = nearest_bound(bounds, target, function(what)
        return mineable(character, what)
      end)
      if way_out then
        return string.format(
          "no path: you are enclosed; no walkable route leaves your position (about %d tiles of room). Mine a way out, such as the %s",
          room or 0,
          way_out
        )
      end
      return string.format(
        "no path: you are enclosed; no walkable route leaves your position (about %d tiles of room), closed in by things you can't mine, such as the %s",
        room or 0,
        nearest_bound(bounds, target)
      )
    end
  end
  if inside and line then
    local reason =
      string.format("no path: the walk beside the line ends in %s", obstacle(inside, target))
    if unfinished then
      reason = reason .. "; clear it, or end the line short of it"
    end
    return reason
  end
  if inside then
    return string.format(
      "no path: the target is in %s; walk to a point beside it, or walk with a larger within",
      obstacle(inside, target)
    )
  end
  if closed then
    return "no path: nothing walkable reaches that point"
  end
  if not explored then
    return "no path: nothing walkable reaches that point"
  end
  closed, room, bounds = room_around(character, layers, target)
  if closed then
    return string.format(
      "no path: %s is enclosed; nothing walkable reaches it, blocked by %s",
      line and "the end of the walk beside the line" or "the target",
      nearest_bound(bounds, here)
    )
  end
  return "no path: nothing walkable reaches that point"
end

-- Whether a building just placed may have cut the room around it in two:
-- it stops the character, and the free tiles in the ring around its
-- footprint aren't one unbroken arc, so it joins up obstacles. A path that
-- crossed its footprint can go round it otherwise. Only then is the agent's
-- room filled, which takes far longer (about 65 ms for 1600 tiles).
local function may_cut_room(character, layers, entity)
  local blocks = false
  local walks_into = character.prototype.collision_mask.layers
  for layer in pairs(entity.prototype.collision_mask.layers) do
    blocks = blocks or walks_into[layer] ~= nil
  end
  if not blocks then
    return false
  end
  local box = entity.bounding_box
  local left, top = math.floor(box.left_top.x), math.floor(box.left_top.y)
  local right, bottom = math.ceil(box.right_bottom.x) - 1, math.ceil(box.right_bottom.y) - 1
  -- The ring of tiles around the footprint, clockwise from its top left.
  local ring = {}
  for i = left - 1, right + 1 do
    ring[#ring + 1] = { i, top - 1 }
  end
  for j = top, bottom + 1 do
    ring[#ring + 1] = { right + 1, j }
  end
  for i = right, left - 1, -1 do
    ring[#ring + 1] = { i, bottom + 1 }
  end
  for j = bottom, top, -1 do
    ring[#ring + 1] = { left - 1, j }
  end
  local free = {}
  for k, cell in ipairs(ring) do
    free[k] = not in_the_way(character, layers, tile_centre(cell[1], cell[2]))
  end
  local arcs = 0
  for k = 1, #ring do
    if free[k] and not free[k == 1 and #ring or k - 1] then
      arcs = arcs + 1
    end
  end
  return arcs > 1
end

-- Why the agent can't walk anywhere now that a building is down, if that
-- building closed the room it stands in: the fill `walk` explains a missing
-- route with (decision 51) finds no way out, and the building is one of
-- the room's walls.
local function enclosed_by(character, entity)
  local layers = walk_layers(character)
  if not may_cut_room(character, layers, entity) then
    return nil
  end
  local closed, room, bounds = room_around(character, layers, character.position)
  if not (closed and bounds) then
    return nil
  end
  for _, bound in ipairs(bounds) do
    if bound.what == entity then
      return string.format(
        "you are enclosed: no walkable route leaves your position now (about %d tiles of room); mine this %s, or another building around you, to get out",
        room,
        entity.name
      )
    end
  end
  return nil
end

function M.on_path(event)
  local s = state()
  local job
  for _, candidate in pairs(s.jobs) do
    if candidate.path_request == event.id then
      job = candidate
      break
    end
  end
  if not (job and job.state == "running") then
    return
  end
  job.path_request = nil
  local character = s.character
  if not (character and character.valid) then
    return
  end
  if event.try_again_later then
    request_route(character, job)
    return
  end
  if not event.path then
    local line = job.kind == "place_line"
    local reason = no_path_reason(character, job.target, line, line and job.next_index <= job.tiles)
    if job.kind == "place_line" then
      end_line(character, job, reason)
    else
      finish(job, "failed", { error = reason })
    end
    return
  end
  local path = {}
  for i, waypoint in ipairs(event.path) do
    path[i] = { x = waypoint.position.x, y = waypoint.position.y }
  end
  job.path = path
  job.waypoint = 1
  job.closest = nil
  job.progress_tick = game.tick
end

-- Mining ---------------------------------------------------------------------

local function products_of(entity)
  if entity.type == "item-entity" then
    return { entity.stack.name }
  end
  local names = {}
  for _, product in pairs(entity.prototype.mineable_properties.products or {}) do
    if product.type == "item" then
      names[#names + 1] = product.name
    end
  end
  return names
end

local function item_counts(character, names)
  local counts = {}
  for _, name in ipairs(names) do
    counts[name] = character.get_item_count(name)
  end
  return counts
end

-- Items gained from a mine job so far, as a list of {name, count}.
function M.mined_so_far(character, job)
  local mined = {}
  for name, before in pairs(job.items_before) do
    local gained = character.get_item_count(name) - before
    if gained > 0 then
      mined[#mined + 1] = { name = name, count = gained }
    end
  end
  table.sort(mined, function(a, b)
    return a.name < b.name
  end)
  return mined
end

-- Distance from a point to the nearest point of an entity's bounding box.
local function distance_to_box(position, entity)
  local box = entity.bounding_box
  local dx = math.max(box.left_top.x - position.x, 0, position.x - box.right_bottom.x)
  local dy = math.max(box.left_top.y - position.y, 0, position.y - box.right_bottom.y)
  return math.sqrt(dx * dx + dy * dy)
end

-- The point of a box nearest to a position.
local function nearest_in_box(position, box)
  return {
    x = math.min(math.max(position.x, box.left_top.x), box.right_bottom.x),
    y = math.min(math.max(position.y, box.left_top.y), box.right_bottom.y),
  }
end

-- How far inside reach the suggested standing point is, so a walk ending
-- within its default 1 tile of it still reaches.
local REACH_MARGIN = 1.5

-- Where the agent is, and the nearest point to stand on to reach `nearest`
-- (the target's point nearest the agent): on the straight line from it to
-- the agent, `REACH_MARGIN` inside `reach`. Only geometry: the point may be
-- in a building or water.
local function reach_hint(character, nearest, reach)
  local here = character.position
  local away = distance(here, nearest)
  local keep = math.max(reach - REACH_MARGIN, 0) / away
  return string.format(
    "; you are at %.1f, %.1f; from %.1f, %.1f you could reach it",
    here.x,
    here.y,
    nearest.x + (here.x - nearest.x) * keep,
    nearest.y + (here.y - nearest.y) * keep
  )
end

-- Reject an entity out of reach, measured to its bounding box; `limit`
-- says which reach ("you can reach", "mining reaches").
local function reject_out_of_reach(character, entity, reach, limit)
  local here = character.position
  reject(
    string.format(
      "%s is %.2f tiles away; %s %.1f tiles",
      entity.name,
      distance_to_box(here, entity),
      limit,
      reach
    ) .. reach_hint(character, nearest_in_box(here, entity.bounding_box), reach)
  )
end

-- The entity a player's cursor would pick at a point, other than the agent.
-- A playerless character mines its selected entity whatever `mining_state`
-- says (found when an `insert` during a mine job made it mine the furnace it
-- had selected), so the selection goes back to what it was.
local function entity_at(character, position)
  local previous = character.selected
  character.update_selected_entity(position)
  local entity = character.selected
  character.selected = previous
  if entity == character then
    return nil
  end
  return entity
end

-- How far past reach a clicked point can be while the building under it is
-- still in reach: the point can be anywhere in the selection box, and reach
-- is measured to the box's near side. So the margin is the longest
-- selection-box diagonal of anything buildable. It depends only on the
-- prototypes, so every game computes the same value.
local select_margin
local function largest_building_span()
  if not select_margin then
    select_margin = 0
    for _, item in pairs(prototypes.item) do
      local placed = item.place_result
      if placed then
        local box = placed.selection_box
        select_margin = math.max(select_margin, distance(box.left_top, box.right_bottom))
      end
    end
  end
  return select_margin
end

-- Reject a point beyond reach before selecting anything there, so a far-off
-- point reveals nothing about what is there.
local function check_point_reach(character, target)
  local reach = character.reach_distance
  local away = distance(character.position, target)
  if away > reach + largest_building_span() then
    reject(
      string.format("that point is %.2f tiles away; you can reach %.1f tiles", away, reach)
        .. reach_hint(character, target, reach)
    )
  end
end

local function mine(params)
  local character = body()
  local target = position_param(params)
  local count = math.floor(number_param(params, "count", 1, 1, MINE_MAX_COUNT))
  check_point_reach(character, target)
  local entity = entity_at(character, target)
  if not entity then
    reject(string.format("nothing to mine at %.2f, %.2f", target.x, target.y))
  end
  ---@cast entity LuaEntity
  local natural = NATURAL[entity.type]
  local fish = entity.type == FISH
  if not (natural or fish or entity.type == "item-entity" or is_own(character, entity)) then
    reject(entity.name .. " can't be mined by hand")
  end
  local mineable = entity.prototype.mineable_properties
  local category = entity.type == "resource" and entity.prototype.resource_category
  local hand_categories = character.prototype.resource_categories or {}
  if
    not mineable.minable
    or mineable.required_fluid
    or (category and not hand_categories[category])
  then
    -- Crude oil is a fluid resource. A player pumps it with a pumpjack;
    -- the character's mining categories don't include it (decision 66).
    if entity.name == "crude-oil" then
      reject(
        "crude-oil can't be mined by hand; place a pumpjack on the well (it pumps crude into a pipe)"
      )
    end
    reject(entity.name .. " can't be mined by hand")
  end
  if natural then
    -- The engine measures mining reach from the character to the target's
    -- collision box, with the same distance for ore, trees and rocks (probed).
    local reach = character.resource_reach_distance
    if distance_to_box(character.position, entity) > reach then
      reject_out_of_reach(character, entity, reach, "mining reaches")
    end
  elseif not character.can_reach_entity(entity) then
    -- Buildings, fish and items on the ground: the engine's own reach
    -- check, to the bounding box (probed: it also stops mining beyond it).
    reject_out_of_reach(character, entity, character.reach_distance, "you can reach")
  end

  local cut = release_body(character, "replaced by mining")
  local job = new_job("mine", {
    target_name = entity.name,
    target_position = point(entity.position),
    count = entity.type == "resource" and count or nil,
    entity = entity,
    start_amount = entity.type == "resource" and entity.amount or nil,
    items_before = item_counts(character, products_of(entity)),
    product = products_of(entity)[1],
  })
  job.cut_short = cut
  state().body_job = job.id
  character.selected = entity
  character.mining_state = { mining = true, position = entity.position }
  return describe(job)
end

local function end_mine(character, job, final_state, err)
  stop_body(character)
  job.entity = nil
  finish(job, final_state, { mined = M.mined_so_far(character, job), error = err })
end

local function step_mine(character, job)
  local entity = job.entity
  if not entity.valid then
    end_mine(character, job, "done")
  elseif job.start_amount and job.start_amount - entity.amount >= job.count then
    end_mine(character, job, "done")
  elseif job.product and not character.can_insert({ name = job.product, count = 1 }) then
    end_mine(character, job, "failed", "inventory full")
  elseif entity.type == FISH and not character.mining_state.mining then
    -- Fish swim (probed: a new fish drifts for a second or so), and the
    -- engine stops mining one that leaves reach.
    end_mine(character, job, "failed", "the fish swam out of reach")
  else
    job.mined = M.mined_so_far(character, job)
  end
end

-- Buildings and machines -----------------------------------------------------
--
-- Placing, inserting, taking and rotating are instant for a player, so they
-- are here too: they return a result, not a job.

local DIRECTIONS = {
  north = defines.direction.north,
  east = defines.direction.east,
  south = defines.direction.south,
  west = defines.direction.west,
}
-- Names for every direction an entity can face, diagonals included; `place`
-- takes only the four in DIRECTIONS.
local DIRECTION_NAMES = {}
for name, value in pairs(defines.direction) do
  DIRECTION_NAMES[value] = name
end
local STATUS_NAMES = {}
for name, value in pairs(defines.entity_status) do
  STATUS_NAMES[value] = name
end
-- An entity's status as the icon over it shows it, or nil. The engine says
-- `no_power` both for a machine on a network whose generators can't run it
-- and for one connected to no generator: in no pole's supply area, or on
-- poles with no generator. Probed on 2.1.24, a player sees a red lightning
-- icon over the first and a plug icon over the second, so the second gets
-- the engine's name for a generator that isn't plugged in.
local function status_name(entity)
  local status = entity.status
  if status == defines.entity_status.no_power and not entity.is_connected_to_electric_network() then
    return "not_plugged_in_electric_network"
  end
  return status and STATUS_NAMES[status]
end
local SILO_STATUS_NAMES = {}
for name, value in pairs(defines.rocket_silo_status) do
  SILO_STATUS_NAMES[value] = name
end
-- Entity types that have a recipe.
local CRAFTERS = { ["assembling-machine"] = true, furnace = true, ["rocket-silo"] = true }
-- Inventories `take` empties when no item is named: what a machine made.
local OUTPUTS = { chest = true, crafter_output = true, burnt_result = true }
local TRANSFER_MAX_COUNT = 100000

---@return string
local function string_param(params, key)
  local value = params[key]
  if type(value) ~= "string" or value == "" then
    bad_params(key .. " must be a name")
  end
  return value
end

-- A fluid is not an item: a player pipes crude oil, petroleum and water,
-- and never carries them (decision 66).
local function reject_unless_item(name)
  if prototypes.item[name] then
    return
  end
  if prototypes.fluid[name] then
    reject(
      name
        .. " is a fluid; it moves through pipes. fac inspect shows a machine's fluids and pipes_to"
    )
  end
  reject("there is no item called " .. name)
end

---@return string?
local function optional_string_param(params, key)
  if params[key] == nil then
    return nil
  end
  return string_param(params, key)
end

-- Item stacks as a sorted list of {name, count}, qualities added together.
local function item_list(contents)
  local counts = {}
  for _, entry in pairs(contents) do
    counts[entry.name] = (counts[entry.name] or 0) + entry.count
  end
  local list = {}
  for name, count in pairs(counts) do
    list[#list + 1] = { name = name, count = count }
  end
  table.sort(list, function(a, b)
    return a.name < b.name
  end)
  return list
end

local function inventories_of(entity)
  local list = {}
  for index = 1, entity.get_max_inventory_index() do
    local inventory = entity.get_inventory(index --[[@as defines.inventory]])
    if inventory and #inventory > 0 then
      list[#list + 1] = {
        name = entity.get_inventory_name(index --[[@as defines.inventory]]),
        slots = #inventory,
        items = item_list(inventory.get_contents()),
      }
    end
  end
  return list
end

-- Which end of a pair an underground belt is (`input` where items go under,
-- `output` where they come up) and the other end it is joined to, if any.
local function underground_ends(entity)
  local partner = entity.underground_belt_neighbour
  return entity.belt_to_ground_type,
    partner and { name = partner.name, position = point(partner.position) } or nil
end

-- Buildings an output can go onto without an inventory.
local BELTS = {
  ["transport-belt"] = true,
  ["underground-belt"] = true,
  splitter = true,
  loader = true,
  ["loader-1x1"] = true,
  ["linked-belt"] = true,
}

-- Buildings that carry items on lanes a player sees: what lies on them
-- shows in `inspect` and `observe`, and `take` picks it up.
local LANED = {
  ["transport-belt"] = true,
  ["underground-belt"] = true,
  splitter = true,
}

-- One tile along each direction a belt can face.
local STEPS = {
  [defines.direction.north] = { x = 0, y = -1 },
  [defines.direction.east] = { x = 1, y = 0 },
  [defines.direction.south] = { x = 0, y = 1 },
  [defines.direction.west] = { x = -1, y = 0 },
}

-- The transport lines on the left lane, facing the way items travel; the
-- others are on the right. An underground belt has its belt lines and the
-- lines going under; a splitter has a pair for each of its two belts, in
-- and out.
local LEFT_LINES = {}
for _, index in ipairs({
  defines.transport_line.left_line,
  defines.transport_line.left_underground_line,
  defines.transport_line.left_split_line,
  defines.transport_line.secondary_left_line,
  defines.transport_line.secondary_left_split_line,
}) do
  LEFT_LINES[index] = true
end

-- What lies on a belt, underground belt or splitter, per lane, as item
-- stacks: what a player sees on it, and what mining it would pick up.
local function lane_contents(entity)
  local left, right = {}, {}
  for index = 1, entity.get_max_transport_line_index() do
    local side = LEFT_LINES[index] and left or right
    local line = entity.get_transport_line(index --[[@as defines.transport_line]])
    for _, entry in pairs(line.get_contents()) do
      side[#side + 1] = entry
    end
  end
  return left, right
end

-- What lies on a belt, underground belt or splitter, per lane as sorted
-- {name, count} lists, or nil when it carries nothing: what `observe`
-- shows of it.
local function belt_lanes(entity)
  local left, right = lane_contents(entity)
  if #left == 0 and #right == 0 then
    return nil
  end
  return { left = item_list(left), right = item_list(right) }
end

-- Whether an entity has an inventory that takes items, module slots aside:
-- a drill's or beacon's modules take no ore, so one facing it drops on the
-- ground. `get_max_inventory_index` is 8 for an electric pole, which has
-- none (probed on 2.1.24).
local function has_inventory(entity)
  local modules = entity.get_module_inventory()
  local module_index = modules and modules.index
  for index = 1, entity.get_max_inventory_index() do
    local inventory = entity.get_inventory(index --[[@as defines.inventory]])
    if inventory and #inventory > 0 and inventory.index ~= module_index then
      return true
    end
  end
  return false
end

-- A belt, a crafter (whose slots appear only once it has a recipe), or a
-- building with an inventory, of the entity's force whose selection box
-- holds a point, other than the entity itself.
local function building_at(entity, at)
  for _, other in pairs(entity.surface.find_entities_filtered({ position = at, radius = 2 })) do
    local box = other.selection_box
    if
      other ~= entity
      and other.force == entity.force
      and other.type ~= "character"
      and (BELTS[other.type] or CRAFTERS[other.type] or has_inventory(other))
      and at.x >= box.left_top.x
      and at.x <= box.right_bottom.x
      and at.y >= box.left_top.y
      and at.y <= box.right_bottom.y
    then
      return other
    end
  end
  return nil
end

-- Where a drill or inserter puts its output: the building its drop point
-- is on, or nil when there is none to take it (see `drop_blocker`). The
-- engine only sets `drop_target` once the machine runs (probed on 2.1.24:
-- nil for an unpowered or unfuelled one), and then it is the building
-- whose selection box holds the drop point, so this looks for that.
local function drop_target(entity)
  return entity.drop_target or building_at(entity, entity.drop_position)
end

-- Where an inserter takes from: the building its pickup point is on, or nil
-- when there is none. Like `drop_target`, the engine leaves `pickup_target`
-- nil until the inserter runs (probed on 2.1.24).
local function pickup_source(entity)
  return entity.pickup_target or building_at(entity, entity.pickup_position)
end

-- What keeps a drill's or inserter's output off the ground at a drop point
-- no building takes it from: a building whose collision box overlaps
-- where the item would lie, or nil when the ground there is clear. With
-- one there the engine drops nothing: a powered drill mines once and stops
-- at `waiting_for_space_in_destination`, and an inserter picks nothing up
-- (probed on 2.1.24 with a small and a medium pole, a drill, a pipe, a
-- wall, an inserter and a lamp; on clear ground one item lands, then the
-- drill or inserter stops with the next).
local function drop_blocker(entity)
  local at = entity.drop_position
  local box = prototypes.entity["item-on-ground"].collision_box
  for _, other in
    pairs(entity.surface.find_entities_filtered({
      area = {
        { at.x + box.left_top.x, at.y + box.left_top.y },
        { at.x + box.right_bottom.x, at.y + box.right_bottom.y },
      },
      collision_mask = "item",
    }))
  do
    if other ~= entity and other.type ~= "item-entity" then
      return other
    end
  end
  return nil
end

-- Lanes -------------------------------------------------------------------------
--
-- A belt has two lanes, `left` and `right` facing the way items travel.
-- Where drills and inserters put items and where inserters take them was
-- probed on 2.1.24 for every orientation of a burner and an electric
-- drill and a burner inserter against a straight belt, a curve, both ends
-- of an underground belt and both halves of a splitter (decision 73).

-- The side of a belt facing `direction`, through `centre`, that a point
-- lies on, or nil on its centre line.
local function side_of(direction, centre, at)
  local step = STEPS[direction]
  local cross = step.x * (at.y - centre.y) - step.y * (at.x - centre.x)
  if math.abs(cross) < 0.01 then
    return nil
  end
  return cross > 0 and "right" or "left"
end

-- Centre of the tile a point lies on. Distinct from `tile_centre(i, j)`,
-- which takes a tile's integer indices.
local function centre_of_tile(at)
  return { x = math.floor(at.x) + 0.5, y = math.floor(at.y) + 0.5 }
end

local function other_lane(lane)
  return lane == "left" and "right" or "left"
end

-- The inner lane of a curved transport belt (the side it turns to), or nil
-- for a straight one or any other building.
local function curve_inner(belt)
  if belt.type == "transport-belt" and belt.belt_shape ~= "straight" then
    return belt.belt_shape
  end
  return nil
end

-- Whether a machine beside a curve stands at one of its ends: the end it
-- leads out of (the curve points at it) or the end it comes in from (on
-- the inner side, where only a long-handed inserter reaching over the
-- feeding belt can stand), rather than beside one of its outer sides.
local function at_curve_end(belt, machine)
  local step = STEPS[belt.direction]
  local dx = machine.position.x - belt.position.x
  local dy = machine.position.y - belt.position.y
  local along = dx * step.x + dy * step.y
  -- Positive on the belt's right, as in side_of.
  local across = step.x * dy - step.y * dx
  local inward = belt.belt_shape == "right" and across or -across
  return along > 0.5 or inward > 0.5
end

-- The lane a drill's or inserter's output lands on. On a straight belt,
-- an underground belt or a splitter it is the lane on the side of the
-- belt's centre line that the drop point is on, the right lane when the
-- point is on the line: an inserter's drop point lies 0.2 tiles past the
-- tile's centre, so it fills the far lane, or the right lane of a belt
-- running along its arm; an electric drill's lies 0.15 tiles short of it,
-- so it fills the near lane, or the right lane; a burner drill's lies 0.2
-- tiles short and 0.15 tiles to the right of its facing. On a curve an
-- inserter fills the lane farther from it (the inner lane from an outer
-- side, the outer lane from either end of the curve); a drill beside an
-- outer side fills the outer lane, and at the end the curve leads to, the
-- lane on the drop point's side, the inner lane when it is on the centre
-- line.
local function drop_lane(machine, target)
  local at = machine.drop_position
  local inner = curve_inner(target)
  if not inner then
    return side_of(target.direction, centre_of_tile(at), at) or "right"
  end
  local at_end = at_curve_end(target, machine)
  if machine.type == "inserter" then
    return at_end and other_lane(inner) or inner
  end
  if not at_end then
    return other_lane(inner)
  end
  return side_of(target.direction, centre_of_tile(at), at) or inner
end

-- The lane an inserter takes from first; it takes from the other one when
-- this one has nothing its target accepts. The near lane of a straight
-- belt, underground belt or splitter, and the left lane of one running
-- along its arm; on a curve the outer lane from an outer side, the inner
-- lane from either end of the curve.
local function pickup_lane(inserter, source)
  local inner = curve_inner(source)
  if inner then
    return at_curve_end(source, inserter) and inner or other_lane(inner)
  end
  return side_of(source.direction, centre_of_tile(inserter.pickup_position), inserter.position)
    or "left"
end

-- What a transport belt or an underground belt's exit does to the belt it
-- points into: `continues` one facing the same way (each lane stays on its
-- side), `curves` a transport belt that has nothing behind it, which turns
-- to carry both lanes on around the corner, or `sideloads` onto one side
-- of it, where both lanes go onto the `lane` on that side. Sideloading an
-- underground belt passes only the lane over the half of its tile that is
-- belt; the lane over the tunnel half is `blocked_lane` (probed on 2.1.24).
local function belt_link(entity)
  if entity.type == "underground-belt" and entity.belt_to_ground_type ~= "output" then
    return nil
  end
  local target = entity.belt_neighbours.outputs[1]
  if not target or not LANED[target.type] then
    return nil
  end
  local where = { name = target.name, position = point(target.position) }
  if target.direction == entity.direction then
    return { continues = where }
  end
  if curve_inner(target) then
    return { curves = where }
  end
  where.lane = side_of(target.direction, target.position, entity.position)
  if target.type == "underground-belt" then
    local step = STEPS[target.direction]
    local sign = target.belt_to_ground_type == "input" and 1 or -1
    local tunnel = { x = entity.position.x + sign * step.x, y = entity.position.y + sign * step.y }
    where.blocked_lane = side_of(entity.direction, entity.position, tunnel)
  end
  return { sideloads = where }
end

-- Whether items go from one belt onto the next with each lane on its side:
-- end on, or around a curve the first one feeds. A sideload merges lanes
-- and a splitter shares them out, so neither counts, whichever way the
-- walk meets the splitter.
local function keeps_lanes(from, to)
  return LANED[to.type]
    and from.type ~= "splitter"
    and to.type ~= "splitter"
    and (to.direction == from.direction or curve_inner(to) ~= nil)
end

-- The belts joined to a belt with its lanes kept, up and down from it,
-- through underground belts: one lane the length of the belt, as far as a
-- player at `here` sees it. Each way stops at the first belt farther than
-- OBSERVE_MAX_RADIUS from there, the most `inspect` and `observe` see
-- (decision 36).
local BELT_WALK_MAX = 200
local function lane_belts(belt, here)
  local found, seen = { belt }, { [belt.unit_number] = true }
  local function walk(from, downstream)
    for _ = 1, BELT_WALK_MAX do
      local nextb
      local pair = from.type == "underground-belt" and from.underground_belt_neighbour
      if pair and (from.belt_to_ground_type == "input") == downstream then
        nextb = pair
      elseif downstream then
        local out = from.belt_neighbours.outputs[1]
        nextb = out and keeps_lanes(from, out) and out or nil
      else
        for _, input in pairs(from.belt_neighbours.inputs) do
          if keeps_lanes(input, from) then
            nextb = input
          end
        end
      end
      if
        not nextb
        or seen[nextb.unit_number]
        or distance(here, nextb.position) > OBSERVE_MAX_RADIUS
      then
        return
      end
      seen[nextb.unit_number] = true
      found[#found + 1] = nextb
      from = nextb
    end
  end
  if belt.type ~= "splitter" then
    walk(belt, true)
    walk(belt, false)
  end
  return found
end

-- What the electric network an entity is on does, as hovering one of its
-- poles shows: what its machines ask for and what its generators can give,
-- in kW, and the share of the demand met (left out when nothing asks).
-- From the engine's last electric update, which counts energy per tick.
local function network_power(entity)
  local network = entity.electric_network
  if not network then
    return nil
  end
  local flow = network.parent_network.flow_last_tick
  local demand = flow.maximum_consumption * 60 / 1000
  return {
    demand_kw = round(demand),
    capacity_kw = round(flow.maximum_production * 60 / 1000),
    satisfaction = demand > 0 and round(flow.consumption_satisfaction) or nil,
  }
end

-- The recipe a crafting machine works to, as its window shows it: the one
-- set, or for an idle furnace the one it last smelted; nil without one.
---@return LuaRecipePrototype?
local function recipe_of(entity)
  local recipe = entity.get_recipe()
  if recipe then
    return recipe.prototype
  end
  local previous = entity.type == "furnace" and entity.previous_recipe
  if previous then
    return prototypes.recipe[type(previous.name) == "string" and previous.name or previous.name.name]
  end
  return nil
end

-- The items a drill or inserter will drop, where a player can tell before
-- it runs: a drill's from the resources in its mining area, an inserter's
-- from the products of the crafter it takes from or what lies in the chest
-- it takes from. Nil when that can't be told.
local function output_items(entity, source)
  local names = {}
  if entity.type == "mining-drill" then
    local resources = entity.surface.find_entities_filtered({
      area = entity.mining_area,
      type = "resource",
    })
    for _, resource in pairs(resources) do
      for _, product in pairs(resource.prototype.mineable_properties.products or {}) do
        if product.type == "item" then
          names[product.name] = true
        end
      end
    end
  elseif source and CRAFTERS[source.type] then
    local recipe = recipe_of(source)
    for _, product in pairs(recipe and recipe.products or {}) do
      if product.type == "item" then
        names[product.name] = true
      end
    end
  elseif source and (source.type == "container" or source.type == "logistic-container") then
    local chest = source.get_inventory(defines.inventory.chest)
    for _, entry in pairs(chest and chest.get_contents() or {}) do
      names[entry.name] = true
    end
  end
  local list = {}
  for name in pairs(names) do
    list[#list + 1] = name
  end
  table.sort(list)
  return #list > 0 and list or nil
end

-- Statuses of a crafting machine held up for want of an ingredient. An
-- assembler that has none of several shows item_ingredient_shortage
-- (probed on 2.1.24), so the status alone doesn't say what is short.
local SHORT = {
  no_ingredients = true,
  item_ingredient_shortage = true,
  fluid_ingredient_shortage = true,
}

-- For a crafting machine held up for ingredients, the ones it has less of
-- than one craft takes, as the empty slots in its window show: `{name,
-- have, need}`. Nil for any other machine or status.
local function missing_ingredients_of(entity, status)
  if not (SHORT[status] and CRAFTERS[entity.type]) then
    return nil
  end
  local recipe = recipe_of(entity)
  if not recipe then
    return nil
  end
  local input = entity.get_inventory(defines.inventory.crafter_input)
  local missing = {}
  for _, ingredient in pairs(recipe.ingredients) do
    local have
    if ingredient.type == "fluid" then
      have = entity.get_fluid_count(ingredient.name)
    else
      have = input and input.get_item_count(ingredient.name) or 0
    end
    if have < ingredient.amount then
      missing[#missing + 1] =
        { name = ingredient.name, have = round(have), need = ingredient.amount }
    end
  end
  return #missing > 0 and missing or nil
end

-- Rates to 4 significant digits: a stone furnace makes 0.3125 plates a
-- second, an assembling machine 2 0.03125 chemical science pack crafts.
local function per_s(value)
  if value == 0 then
    return 0
  end
  local scale = 10 ^ (4 - math.ceil(math.log(math.abs(value), 10)))
  return math.floor(value * scale + 0.5) / scale
end

-- What one craft or mining cycle yields of a product on average, with the
-- machine's productivity bonus added to the part productivity applies to.
local function yield(product, productivity)
  local amount = product.amount or (product.amount_min + product.amount_max) / 2
  local shared = product.shared_probability
  local chance = (product.independent_probability or 1)
    * (shared and (shared.max - shared.min) or 1)
  local boosted = math.max(amount - (product.ignored_by_productivity or 0), 0)
  return (amount + boosted * productivity) * chance
end

-- What a crafting machine goes through at its crafting speed (modules and
-- beacons included) while it works at full power.
local function crafter_rates(entity, recipe)
  local crafts = entity.crafting_speed / recipe.energy
  local ingredients, products = {}, {}
  for _, ingredient in pairs(recipe.ingredients) do
    ingredients[#ingredients + 1] =
      { name = ingredient.name, per_s = per_s(ingredient.amount * crafts) }
  end
  for _, product in pairs(recipe.products) do
    products[#products + 1] =
      { name = product.name, per_s = per_s(yield(product, entity.productivity_bonus) * crafts) }
  end
  return { crafts_per_s = per_s(crafts), ingredients = ingredients, products = products }
end

-- What a mining drill yields while it works at full power: its prototype's
-- mining speed with the entity's speed bonus (modules, beacons) over the
-- resource's mining time, times its productivity bonus (research
-- included). The resource is the one it mines, or before it has run, the
-- first under it that it can mine. Nil for a fluid such as crude oil,
-- whose yield depends on the field.
local function drill_rates(entity)
  local resource = entity.mining_target
  if not resource then
    local categories = entity.prototype.resource_categories or {}
    for _, found in
      pairs(entity.surface.find_entities_filtered({ area = entity.mining_area, type = "resource" }))
    do
      if categories[found.prototype.resource_category] then
        resource = found
        break
      end
    end
  end
  if not resource then
    return nil
  end
  local mineable = resource.prototype.mineable_properties
  local cycles = entity.prototype.mining_speed * (1 + entity.speed_bonus) / mineable.mining_time
  local products = {}
  for _, product in pairs(mineable.products or {}) do
    if product.type ~= "item" then
      return nil
    end
    products[#products + 1] =
      { name = product.name, per_s = per_s(yield(product, entity.productivity_bonus) * cycles) }
  end
  return { products = products }
end

-- Items a lane holds per tile of its length: 4, a quarter tile apart, on
-- every belt (probed on 2.1.24 by feeding belts until they stopped: 4 per
-- lane of a straight belt, 5 and 2 on the outer and inner lane of a
-- curve, whose lanes are 1.15 and 0.41 tiles long).
local ITEMS_PER_LANE_TILE = 4

-- Items a belt moves per second at most: both lanes full at its speed.
local function belt_capacity_per_s(prototype)
  return per_s(prototype.belt_speed * 60 * ITEMS_PER_LANE_TILE * 2)
end

-- How many items a transport belt holds when both lanes are full.
local function belt_room(entity)
  local room = 0
  for index = 1, entity.get_max_transport_line_index() do
    local line = entity.get_transport_line(index --[[@as defines.transport_line]])
    room = room + math.ceil(line.line_length * ITEMS_PER_LANE_TILE - 1e-6)
  end
  return room
end

-- Whether a drill that hasn't run is short of the fluid its ore needs:
-- `true` when every resource under it that it can mine needs more of a
-- fluid (sulfuric acid for uranium ore) than the drill holds for one
-- mining cycle, `nil` when some do and some don't, since which one it
-- mines first isn't known before it runs (probed on 2.1.24: one iron tile
-- among uranium mined uranium, one uranium tile among iron mined iron),
-- and `false` when none does. A drill joined to a pipe holds what the
-- pipe's fluid segment shares with it from the tick it is placed.
local function drill_short_of_fluid(entity)
  local categories = entity.prototype.resource_categories or {}
  local short, fed = false, false
  for _, found in
    pairs(entity.surface.find_entities_filtered({ area = entity.mining_area, type = "resource" }))
  do
    if categories[found.prototype.resource_category] then
      local mineable = found.prototype.mineable_properties
      local fluid = mineable.required_fluid
      if fluid and entity.get_fluid_count(fluid) < mineable.fluid_amount then
        short = true
      else
        fed = true
      end
    end
  end
  if short and fed then
    return nil
  end
  return short
end

-- The status a building just placed shows once its network's next electric
-- update has filled its energy buffer. Until then the engine says
-- `no_power` (probed on 2.1.24: a drill placed beside a 6.3 MW grid
-- showed it, and `working` one tick later). When the network's generators
-- offered no energy in its last update (boilers out of fuel, solar at
-- night, no generator), the `no_power` is real and stays. Otherwise the
-- engine's own status is read with the buffer filled to the share of
-- demand the network last met, then the buffer is put back, in the same
-- tick (probed: equal to the status one tick later for assemblers,
-- furnaces, labs and inserters). A drill that hasn't run has no mining
-- target and reads `waiting_for_space_in_destination` that way, but
-- always starts mining (probed, even into a full chest), so it is
-- `working`, or `low_power` on a network short of power, unless its ore
-- needs a fluid it holds too little of: then it is
-- `missing_required_fluid` (probed: a drill on uranium ore with less than
-- 10 sulfuric acid showed it one tick later, one with 10 `working`).
local function settled_status(entity)
  local status = status_name(entity)
  local network = entity.electric_network
  if status ~= "no_power" or not network then
    return status
  end
  local flow = network.parent_network.flow_last_tick
  if flow.maximum_production <= 0 and flow.accumulator_energy <= 0 then
    return status
  end
  local share = flow.maximum_consumption > 0 and math.min(flow.consumption_satisfaction, 1) or 1
  if entity.type == "mining-drill" then
    local short = drill_short_of_fluid(entity)
    if short == nil then
      return status
    end
    if short then
      return "missing_required_fluid"
    end
    return share < 1 and "low_power" or "working"
  end
  local before = entity.energy
  entity.energy = entity.electric_buffer_size * share
  status = status_name(entity)
  entity.energy = before
  return status
end

-- What carries one fluid and has no sides of its own.
local PIPING = { pipe = true, ["pipe-to-ground"] = true, ["storage-tank"] = true, pump = true }

-- Where a machine's pipes go, as the arrows and fluid icons on it show in
-- alt mode (decision 80): for each pipe connection, whether fluid goes
-- `input`, `output` or both ways there (`input-output`: it passes through),
-- the fluid the recipe puts on it, the tile its pipe goes on, and what is
-- joined there now. Only for machines whose pipes have sides that turn with
-- them; nil for pipes, tanks and the rest.
local function fluid_ports(entity)
  local type = entity.type
  if
    not (
      type == "assembling-machine"
      or type == "mining-drill"
      or type == "boiler"
      or type == "generator"
    )
  then
    return nil
  end
  -- A pumpjack's box has no filter and is empty until it pumps: the fluid is
  -- what the well under it gives.
  local mined
  if type == "mining-drill" then
    local well = entity.mining_target
    for _, product in pairs(well and well.prototype.mineable_properties.products or {}) do
      if product.type == "fluid" then
        mined = product.name
      end
    end
  end
  local ports = {}
  for index = 1, entity.fluids_count do
    local filter = entity.get_fluid_filter(index)
    local held = entity.get_fluid(index)
    local fluid = filter and filter.name or held and held.name or mined
    for _, connection in pairs(entity.get_fluid_box_pipe_connections(index) or {}) do
      local target = connection.target
      local joined, problem
      if target then
        -- What the pipe there holds, when it is a pipe, tank or pump: one
        -- fluid, which the port takes or it doesn't.
        local holds = PIPING[target.type] and next(target.get_fluid_contents()) or nil
        joined = { name = target.name, position = point(target.position), fluid = holds }
        if holds and fluid and holds ~= fluid then
          problem = string.format(
            "the %s there holds %s, and this port is for %s",
            target.name,
            holds,
            fluid
          )
        end
      end
      ports[#ports + 1] = {
        flow = connection.flow_direction,
        fluid = fluid,
        pipe_at = point(connection.target_position),
        joined_to = joined,
        problem = problem,
      }
    end
  end
  return ports
end

-- The other end of a pipe-to-ground's underground run, or nil when no
-- partner faces it within range.
local function pipe_partner(entity)
  for _, connection in pairs(entity.get_fluid_box_pipe_connections(1) or {}) do
    if connection.connection_type == "underground" and connection.target then
      return point(connection.target.position)
    end
  end
  return nil
end

-- What an entity looks like up close: what it holds, what it is doing, what
-- it goes through, and where its output goes. `status` stands in for the
-- entity's own when given.
local function entity_view(entity, status)
  status = status or status_name(entity)
  local view = {
    name = entity.name,
    type = entity.type,
    position = point(entity.position),
    direction = entity.supports_direction and DIRECTION_NAMES[entity.direction] or nil,
    status = status,
    inventories = inventories_of(entity),
  }
  if CRAFTERS[entity.type] then
    local recipe = recipe_of(entity)
    view.recipe = recipe and recipe.name or nil
    view.progress = round(entity.crafting_progress)
    view.missing = missing_ingredients_of(entity, status)
    view.rates = recipe and crafter_rates(entity, recipe) or nil
  end
  if entity.type == "rocket-silo" then
    -- `parts` counts toward the rocket being built; it is back at 0 once the
    -- rocket stands in the silo.
    local payload = entity.get_inventory(defines.inventory.rocket_silo_rocket)
    view.rocket = {
      status = SILO_STATUS_NAMES[entity.rocket_silo_status],
      parts = entity.rocket_parts,
      parts_required = entity.prototype.rocket_parts_required,
      payload = payload and item_list(payload.get_contents()) or {},
    }
  end
  if entity.type == "underground-belt" then
    view.underground, view.paired_with = underground_ends(entity)
  end
  if LANED[entity.type] then
    local left, right = lane_contents(entity)
    view.lanes = { left = item_list(left), right = item_list(right) }
    view.capacity_per_s = belt_capacity_per_s(entity.prototype)
    -- A belt something points into from one side, with nothing behind it,
    -- is a curve, as its sprite shows.
    view.turns = curve_inner(entity)
  end
  if entity.burner then
    -- The burning item, with its prototype under `name` (probed on 2.1).
    local burning = entity.burner.currently_burning
    view.burning = burning and burning.name.name or nil
  end
  if entity.type == "mining-drill" then
    view.mining = entity.mining_target and entity.mining_target.name or nil
    view.rates = drill_rates(entity)
  end
  if entity.type == "electric-pole" or entity.prototype.electric_energy_source_prototype then
    view.power = network_power(entity)
  end
  -- A pumpjack mines `basic-fluid` (crude oil) and its output leaves
  -- through its pipes; its `vector_to_place_result` is {0, 0} (probed).
  local fluid_drill = entity.type == "mining-drill"
    and entity.prototype.resource_categories["basic-fluid"]
  if entity.type == "inserter" or (entity.type == "mining-drill" and not fluid_drill) then
    local target = drop_target(entity)
    if target then
      view.drops_into = {
        name = target.name,
        position = point(target.position),
        lane = LANED[target.type] and drop_lane(entity, target) or nil,
      }
    else
      view.drops_at = point(entity.drop_position)
    end
  end
  if entity.type == "inserter" then
    local source = pickup_source(entity)
    if source then
      view.picks_from = {
        name = source.name,
        position = point(source.position),
        lane = LANED[source.type] and pickup_lane(entity, source) or nil,
      }
    else
      view.picks_at = point(entity.pickup_position)
    end
  end
  if entity.fluids_count > 0 then
    local fluids = {}
    for name, amount in pairs(entity.get_fluid_contents()) do
      fluids[#fluids + 1] = { name = name, amount = round(amount) }
    end
    table.sort(fluids, function(a, b)
      return a.name < b.name
    end)
    view.fluids = fluids
    -- What its pipe connections are joined to, so the agent can check a
    -- pump, boiler and engine are hooked up.
    local joined = {}
    for _, group in pairs(entity.fluidbox_neighbours) do
      for _, neighbour in pairs(group) do
        joined[#joined + 1] = { name = neighbour.name, position = point(neighbour.position) }
      end
    end
    view.pipes_to = joined
    view.ports = fluid_ports(entity)
    if entity.type == "pipe-to-ground" then
      view.paired_with = pipe_partner(entity)
    end
  end
  return view
end

-- One of the agent's own entities within interaction reach, as `insert`,
-- `take` and `rotate` need.
local function reachable_entity(character, params)
  local target = position_param(params)
  check_point_reach(character, target)
  local entity = entity_at(character, target)
  if not entity or entity.type == "item-entity" or entity.type == FISH or NATURAL[entity.type] then
    reject(string.format("no building at %.2f, %.2f", target.x, target.y))
  end
  ---@cast entity LuaEntity
  if not is_own(character, entity) then
    reject(entity.name .. " is not yours")
  end
  if not character.can_reach_entity(entity) then
    reject_out_of_reach(character, entity, character.reach_distance, "you can reach")
  end
  return entity
end

-- Where the cursor puts a building: on the tile grid, centred on a tile for
-- odd sizes and on a tile corner for even ones.
local function snap(size, value)
  if size % 2 == 1 then
    return math.floor(value) + 0.5
  end
  return math.floor(value + 0.5)
end

-- The collision box of a building about to be placed, on the map.
local function placed_box(prototype, position, direction)
  local box = prototype.collision_box
  local turns = direction / defines.direction.east -- quarter turns clockwise
  local left, top, right, bottom = math.huge, math.huge, -math.huge, -math.huge
  for _, corner in pairs({
    { box.left_top.x, box.left_top.y },
    { box.right_bottom.x, box.right_bottom.y },
  }) do
    local x, y = corner[1], corner[2]
    for _ = 1, turns do
      x, y = -y, x
    end
    left, right = math.min(left, x), math.max(right, x)
    top, bottom = math.min(top, y), math.max(bottom, y)
  end
  return {
    left_top = { x = position.x + left, y = position.y + top },
    right_bottom = { x = position.x + right, y = position.y + bottom },
  }
end

local function distance_to_area(position, box)
  local dx = math.max(box.left_top.x - position.x, 0, position.x - box.right_bottom.x)
  local dy = math.max(box.left_top.y - position.y, 0, position.y - box.right_bottom.y)
  return math.sqrt(dx * dx + dy * dy)
end

-- Where an offshore pump fits near a point: the nearest tile and direction
-- within 4 tiles that passes the build check and is in build reach. A player
-- sees the shore and the pump's ghost turn green; the agent gets this.
local function nearest_pump_spot(character, prototype, around)
  local surface = character.surface
  local best, best_away
  for dx = -4, 4 do
    for dy = -4, 4 do
      local position = { x = math.floor(around.x) + dx + 0.5, y = math.floor(around.y) + dy + 0.5 }
      local away = distance(around, position)
      if not best_away or away < best_away then
        for name, direction in pairs(DIRECTIONS) do
          local reachable = distance_to_area(
            character.position,
            placed_box(prototype, position, direction)
          ) <= character.build_distance
          if
            reachable
            and surface.can_place_entity({
              name = prototype.name,
              position = position,
              direction = direction,
              force = character.force,
              build_check_type = defines.build_check_type.manual,
            })
          then
            best, best_away = { position = position, direction = name }, away
            break
          end
        end
      end
    end
  end
  return best
end

local STANDING = "you are standing there"

-- Why the game won't let a building go somewhere, as near as the mod can tell.
local function placement_problem(character, prototype, box, position)
  local surface = character.surface
  -- Only entities the building would collide with; corpses and the like don't block.
  local layers = {}
  for layer in pairs(prototype.collision_mask.layers) do
    layers[#layers + 1] = layer
  end
  for _, other in pairs(surface.find_entities_filtered({ area = box, collision_mask = layers })) do
    if other == character then
      return STANDING
    end
    if other.type ~= "resource" and other.type ~= "item-entity" then
      return string.format(
        "blocked by %s at %s, %s",
        other.name,
        round(other.position.x),
        round(other.position.y)
      )
    end
  end
  if prototype.type == "offshore-pump" then
    local spot = nearest_pump_spot(character, prototype, position)
    local hint = spot
        and string.format(
          "; the nearest place it fits is %s, %s facing %s",
          spot.position.x,
          spot.position.y,
          spot.direction
        )
      or "; it fits nowhere within 4 tiles of there that you can reach"
    return "an offshore pump goes on the shore, with its direction pointing at the water" .. hint
  end
  if surface.count_tiles_filtered({ area = box, collision_mask = "water_tile" }) > 0 then
    return "there is water there"
  end
  if prototype.type == "mining-drill" then
    return "a mining drill needs something it can mine under it"
  end
  return "the game doesn't allow it there"
end

-- Where the cursor puts a building facing `direction` when pointed at `target`.
local function snapped(prototype, direction, target)
  local quarter = direction == DIRECTIONS.east or direction == DIRECTIONS.west
  local width = quarter and prototype.tile_height or prototype.tile_width
  local height = quarter and prototype.tile_width or prototype.tile_height
  return { x = snap(width, target.x), y = snap(height, target.y) }
end

-- Put one building from the inventory at a snapped position in build reach,
-- as a click does. Returns the entity and whether it already stood there,
-- or nil, why not, and "standing" when the agent is in the way or "none"
-- when it carries none of the item; last, the name of a building it took
-- the place of.
---@return LuaEntity?, boolean?, string?, string?, string?
local function build(character, item_name, prototype, position, direction, belt_type, box)
  local surface = character.surface
  -- The same building already standing there, as a player sees when the
  -- cursor's ghost lines up with it: nothing to do and nothing used up, so
  -- a chain of commands can run again. Facing another way, it needs
  -- turning or replacing, not placing. One merely overlapping the spot
  -- (find_entity matches any point in its box) blocks the placement below.
  local existing = surface.find_entity(prototype.name, position)
  if
    existing
    and existing.position.x == position.x
    and existing.position.y == position.y
    and is_own(character, existing)
  then
    local underground = prototype.type == "underground-belt"
    local same_end = not underground or existing.belt_to_ground_type == (belt_type or "input")
    if same_end and (not existing.supports_direction or existing.direction == direction) then
      return existing, true
    end
    return nil,
      nil,
      string.format(
        "%s already stands at %s, %s%s facing %s; %s",
        item_name,
        position.x,
        position.y,
        underground and (" as an " .. existing.belt_to_ground_type) or "",
        DIRECTION_NAMES[existing.direction],
        underground and "mine it and place it again to change it"
          or string.format(
            "turn it with `fac rotate %s,%s` (a quarter turn clockwise each time)",
            position.x,
            position.y
          )
      )
  end
  if character.get_item_count(item_name) == 0 then
    return nil, nil, "you have no " .. item_name, "none"
  end
  local spec = {
    name = prototype.name,
    position = position,
    direction = direction,
    force = character.force,
  }
  spec.build_check_type = defines.build_check_type.manual
  if not surface.can_place_entity(spec) then
    local problem = placement_problem(character, prototype, box, position)
    return nil,
      nil,
      string.format("can't place %s at %s, %s: %s", item_name, position.x, position.y, problem),
      problem == STANDING and "standing" or nil
  end
  spec.build_check_type = nil
  spec.raise_built = true
  spec.type = belt_type
  -- A building of the same kind and size standing there is swapped for this
  -- one, as a player's click does (an assembler for a faster one, a stone
  -- furnace for a steel one): it keeps its recipe and contents, and the old
  -- building goes to the inventory. Without this the new one would be
  -- created on top of it.
  local replaced
  local group = prototype.fast_replaceable_group
  for _, old in pairs(group and surface.find_entities_filtered({ position = position }) or {}) do
    if old.prototype.fast_replaceable_group == group and old.name ~= prototype.name then
      replaced = old.name
    end
  end
  spec.fast_replace = true
  spec.character = character
  local entity = surface.create_entity(spec)
  if not entity then
    return nil, nil, string.format("can't place %s at %s, %s", item_name, position.x, position.y)
  end
  character.remove_item({ name = item_name, count = 1 })
  return entity, false, nil, nil, replaced
end

-- The item named by `item` and the building it places.
---@return string, LuaEntityPrototype
local function building_param(params)
  local item_name = string_param(params, "item")
  local item = prototypes.item[item_name]
  if not item then
    reject_unless_item(item_name)
  end
  local prototype = item.place_result
  if not prototype then
    reject(item_name .. " is not a building; only buildings can be placed")
  end
  ---@cast prototype LuaEntityPrototype
  return item_name, prototype
end

-- The `direction` param, or `default` when it is left out.
local function direction_param(params, default)
  local direction_name = optional_string_param(params, "direction") or default
  local direction = DIRECTIONS[direction_name]
  if not direction then
    bad_params("direction must be north, east, south or west")
  end
  return direction, direction_name
end

-- Build reach is measured like interaction reach: from the character to
-- the nearest point of the building's box.
local function check_build_reach(character, item_name, position, box)
  local away = distance_to_area(character.position, box)
  local reach = character.build_distance
  if away > reach then
    reject(
      string.format(
        "%s at %s, %s would be %.2f tiles away; you can build %.1f tiles away",
        item_name,
        position.x,
        position.y,
        away,
        reach
      ) .. reach_hint(character, nearest_in_box(character.position, box), reach)
    )
  end
end

-- A belt's view with what it does to the belt it points into (`belt_link`),
-- as a player sees from the arrows where the two meet.
local function with_belt_link(view, entity)
  if entity.type == "transport-belt" or entity.type == "underground-belt" then
    local link = belt_link(entity)
    if link then
      view.continues, view.curves, view.sideloads = link.continues, link.curves, link.sideloads
    end
  end
  return view
end

-- Why a drill's or inserter's output would share a belt lane with other
-- items, where what it drops is known before it runs: a drill over two
-- resources drops both, and a lane that already carries something else,
-- anywhere along it within sight of `character`, mixes. A lane moves in
-- single file, so an item no machine along it takes stops at its end and
-- holds up the rest.
local function mixed_lane_warning(entity, view, character)
  local lane = view.drops_into and view.drops_into.lane
  if not lane then
    return nil
  end
  local target = drop_target(entity)
  ---@cast target LuaEntity
  local drops = output_items(entity, entity.type == "inserter" and pickup_source(entity) or nil)
  if not drops then
    return nil
  end
  local at = view.drops_into.position
  local where = string.format("the %s lane of the %s at %s, %s", lane, target.name, at.x, at.y)
  local single_file = "a lane moves in single file, so an item that no machine along it takes "
    .. "stops at the belt's end and holds up the lane behind it"
  if #drops > 1 and entity.type == "mining-drill" then
    return string.format(
      "it mines %s here and drops them all onto %s: %s",
      table.concat(drops, " and "),
      where,
      single_file
    )
  end
  local dropped, others = {}, {}
  for _, name in ipairs(drops) do
    dropped[name] = true
  end
  for _, belt in ipairs(lane_belts(target, character.position)) do
    local left, right = lane_contents(belt)
    for _, entry in ipairs(lane == "left" and left or right) do
      if not dropped[entry.name] then
        dropped[entry.name] = true
        others[#others + 1] = entry.name
      end
    end
  end
  if #others == 0 then
    return nil
  end
  table.sort(others)
  return string.format(
    "it drops %s onto %s, which already carries %s: %s",
    table.concat(drops, " and "),
    where,
    table.concat(others, " and "),
    single_file
  )
end

local function place(params)
  local character = body()
  local item_name, prototype = building_param(params)
  local direction = direction_param(params, "north")
  -- An underground belt is an entrance or an exit; both face the way items
  -- travel. create_entity makes an entrance unless told otherwise.
  local belt_type = optional_string_param(params, "belt_type")
  if belt_type and prototype.type ~= "underground-belt" then
    bad_params("belt_type is only for underground belts")
  end
  if belt_type and belt_type ~= "input" and belt_type ~= "output" then
    bad_params("belt_type must be input or output")
  end
  local position = snapped(prototype, direction, position_param(params))
  local box = placed_box(prototype, position, direction)
  check_build_reach(character, item_name, position, box)
  local entity, already, problem, _, replaced =
    build(character, item_name, prototype, position, direction, belt_type, box)
  if not entity then
    reject(problem)
  end
  ---@cast entity LuaEntity
  local view = with_belt_link(entity_view(entity, settled_status(entity)), entity)
  view.already_there = already or nil
  view.replaced = replaced
  if not already then
    view.enclosed = enclosed_by(character, entity)
  end
  -- What a player sees at once from the arrows of the building's ghost: an
  -- output that lands on the ground or has nowhere to go, an inserter with
  -- nothing to take from, items that would share a belt lane with others.
  local warnings = { mixed_lane_warning(entity, view, character) }
  if view.drops_at then
    local blocker = drop_blocker(entity)
    if blocker then
      warnings[#warnings + 1] = string.format(
        "its output has nowhere to go at %s, %s: the %s there takes no items and leaves no room "
          .. "on the ground, so it stops without dropping any",
        view.drops_at.x,
        view.drops_at.y,
        blocker.name
      )
    else
      warnings[#warnings + 1] = string.format(
        "its output lands on the ground at %s, %s: no belt or building is there to take it",
        view.drops_at.x,
        view.drops_at.y
      )
    end
  end
  if view.picks_at then
    warnings[#warnings + 1] = string.format(
      "it has nothing to take from at %s, %s: no belt or building is there",
      view.picks_at.x,
      view.picks_at.y
    )
  end
  -- An engine shows `no_input_fluid` until steam reaches it, whether a pole
  -- reaches it or not; the game draws its plug icon only once it has steam.
  if entity.type == "generator" and not entity.is_connected_to_electric_network() then
    warnings[#warnings + 1] =
      "no electric pole reaches it yet: until one does, the power it makes goes nowhere"
  end
  if entity.type == "pipe-to-ground" and not view.paired_with then
    warnings[#warnings + 1] = string.format(
      "its underground end joins nothing yet: its partner goes in a straight line behind it "
        .. "(the side opposite to its direction), at most %d tiles away, facing the opposite way",
      entity.prototype.max_underground_distance
    )
  end
  view.warnings = #warnings > 0 and warnings or nil
  return view
end

-- Placing a line ---------------------------------------------------------------

-- A player drags a building along a straight line while running beside it,
-- and each one goes down as the cursor passes its tile in build reach. The
-- body walks a lane this far beside the line's buildings, so it never
-- stands where a pipe or pole has to go.
local LINE_LANE = 1.5
local LINE_MAX_SPACING = 64

-- Place the line's next buildings, in order, while each is in build reach.
-- Returns false once the job has failed.
local function build_along(character, job)
  local prototype = prototypes.entity[job.entity_name]
  while job.next_index <= job.tiles do
    local position = line_tile(job, job.next_index)
    local box = placed_box(prototype, position, job.facing)
    if distance_to_area(character.position, box) > character.build_distance then
      return true
    end
    local entity, already, problem, why =
      build(character, job.item, prototype, position, job.facing, nil, box)
    if not entity then
      if why == "standing" then
        return true -- the body is walking off that tile
      end
      stop_body(character)
      local text = why == "none" and ("you ran out of " .. job.item) or problem
      finish(job, "failed", { error = string.format("%s; %s", text, line_progress(job)) })
      return false
    end
    if already then
      job.already_there = job.already_there + 1
    else
      job.placed = job.placed + 1
    end
    job.next_index = job.next_index + 1
  end
  return true
end

-- The body walks on beside the line after the last building is down, so the
-- job ends at the far end, where the next line or building usually goes.
local function step_line(character, job)
  if not build_along(character, job) then
    return
  end
  local outcome = steer(character, job)
  if outcome == "arrived" and not build_along(character, job) then
    return
  end
  if outcome then
    end_line(character, job, outcome)
  end
end

local function place_line(params)
  local character = body()
  local item_name, prototype = building_param(params)
  if prototype.type == "underground-belt" then
    reject("underground belts go one end at a time: place the entrance and the exit")
  end
  if prototype.type == "pipe-to-ground" then
    reject(
      string.format(
        "a pipe-to-ground goes one end at a time: place one, then its partner up to %d tiles "
          .. "behind it facing the opposite way, and read `paired_with` in the answer",
        prototype.max_underground_distance
      )
    )
  end
  local from = position_param(params)
  local to = {
    x = number_param(params, "to_x", nil, -1e6, 1e6),
    y = number_param(params, "to_y", nil, -1e6, 1e6),
  }
  -- By default the buildings face the way the line runs, as a dragged belt does.
  local dx, dy = to.x - from.x, to.y - from.y
  local runs = "north"
  if math.abs(dx) >= math.abs(dy) and dx ~= 0 then
    runs = dx > 0 and "east" or "west"
  elseif dy ~= 0 then
    runs = dy > 0 and "south" or "north"
  end
  local facing, facing_name = direction_param(params, runs)
  from = snapped(prototype, facing, from)
  to = snapped(prototype, facing, to)
  if from.x ~= to.x and from.y ~= to.y then
    bad_params(
      string.format(
        "a line runs straight: the ends snap to %s, %s and %s, %s; give both the same x or the same y",
        from.x,
        from.y,
        to.x,
        to.y
      )
    )
  end
  local length = math.abs(to.x - from.x) + math.abs(to.y - from.y)
  if length > WALK_MAX_DISTANCE then
    reject(
      string.format("that line is %.0f tiles long; one goes at most %d", length, WALK_MAX_DISTANCE)
    )
  end
  local box = placed_box(prototype, from, facing)
  local size = { x = box.right_bottom.x - box.left_top.x, y = box.right_bottom.y - box.left_top.y }
  local along_x = from.y == to.y
  -- Next to each other by default: one building's length along the line.
  -- With a spacing that doesn't divide the length, the last gap is shorter,
  -- so the line ends at `to`; when that gap is shorter than a building the
  -- last one would overlap the one before, so the line ends a step early.
  local length_along = math.max(1, math.ceil(along_x and size.x or size.y))
  local spacing = math.floor(number_param(params, "spacing", length_along, 1, LINE_MAX_SPACING))
  local tiles = math.floor(length / spacing) + 1
  local rest = length - (tiles - 1) * spacing
  if rest > 0 and rest >= length_along then
    tiles = tiles + 1
  end
  local backwards = (along_x and to.x < from.x) or (not along_x and to.y < from.y)
  local sign = backwards and -1 or 1
  local step = along_x and { x = sign * spacing, y = 0 } or { x = 0, y = sign * spacing }
  check_build_reach(character, item_name, from, box)
  if character.get_item_count(item_name) == 0 then
    reject("you have no " .. item_name)
  end

  local cut = release_body(character, "replaced by placing a line")
  local job = new_job("place_line", {
    item = item_name,
    entity_name = prototype.name,
    from = from,
    to = to,
    step = step,
    tiles = tiles,
    facing = facing,
    facing_name = facing_name,
    next_index = 1,
    placed = 0,
    already_there = 0,
    walked = 0,
    within = 1,
  })
  job.cut_short = cut
  state().body_job = job.id
  if build_along(character, job) then
    -- Walk the lane on the side the body is on, to beside the last one.
    local here = character.position
    local last = line_tile(job, tiles)
    local away = along_x and (here.y - from.y) or (here.x - from.x)
    local side = away < 0 and -1 or 1
    local offset = side * ((along_x and size.y or size.x) / 2 + LINE_LANE)
    job.target = along_x and { x = last.x, y = last.y + offset }
      or { x = last.x + offset, y = last.y }
    request_route(character, job)
  end
  return describe(job)
end

-- Where `insert` takes the agent's items from. The gun and armor slots are
-- left out: what the agent wields and wears stays on it.
local HELD = {
  defines.inventory.character_main,
  defines.inventory.character_ammo,
  defines.inventory.character_trash,
}

-- The agent's stacks of an item that `insert` can hand over.
local function held_stacks(character, item)
  local stacks = {}
  for _, index in ipairs(HELD) do
    local inventory = character.get_inventory(index)
    for slot = 1, inventory and #inventory or 0 do
      local stack = inventory[slot]
      if stack.valid_for_read and stack.name == item then
        stacks[#stacks + 1] = stack
      end
    end
  end
  return stacks
end

-- Move up to `count` items out of `stack` into `target` as a hand would:
-- they keep their quality, health, ammo, durability and equipment, which
-- inserting by name would reset. Returns how many moved.
local function move_items(stack, target, count)
  local hand = game.create_inventory(1)
  local held = hand[1]
  held.transfer_stack(stack, count)
  local moved = target.insert(held)
  if moved < held.count then
    held.count = held.count - moved
    stack.transfer_stack(held)
  end
  hand.destroy()
  return moved
end

-- Inventories that hold any item, modules included: a full one is all that
-- stops an insert.
local STORAGE = { chest = true, car_trunk = true, cargo_wagon = true, spider_trunk = true }

local function has_storage(entity)
  for index = 1, entity.get_max_inventory_index() do
    local inventory = index --[[@as defines.inventory]]
    if entity.get_inventory(inventory) and STORAGE[entity.get_inventory_name(inventory)] then
      return true
    end
  end
  return false
end

-- Why a building won't take an item, as near as the mod can tell. The game
-- does the routing and the refusing (probed: it puts modules in module slots
-- only where the machine and its recipe allow every effect they have, and a
-- rocket silo's payload into the rocket even while the rocket is built).
local function insert_problem(entity, item)
  local refused = string.format("%s doesn't take %s, or has no room for it", entity.name, item)
  local prototype = prototypes.item[item]
  if prototype.type == "module" then
    local slots = entity.get_module_inventory()
    if not slots or #slots == 0 then
      if has_storage(entity) then
        return refused
      end
      return string.format("%s has no module slots", entity.name)
    end
    local allowed = entity.prototype.allowed_effects or {}
    local recipe = CRAFTERS[entity.type] and entity.get_recipe()
    local by_recipe = recipe and recipe.prototype.allowed_effects or {}
    local effects = {}
    for effect, value in pairs(prototype.module_effects or {}) do
      if value ~= 0 and not (allowed[effect] and (not recipe or by_recipe[effect])) then
        effects[#effects + 1] = effect
      end
    end
    table.sort(effects)
    if #effects > 0 then
      return string.format(
        "%s%s doesn't allow %s, which %s has",
        entity.name,
        recipe and (" making " .. recipe.name) or "",
        table.concat(effects, " or "),
        item
      )
    end
    if not slots.find_empty_stack() then
      return string.format("all %d module slots of %s are full", #slots, entity.name)
    end
  end
  if entity.type == "rocket-silo" then
    local payload = entity.get_inventory(defines.inventory.rocket_silo_rocket)
    if payload and not payload.is_empty() then
      local held = item_list(payload.get_contents())[1]
      return string.format("%s; the rocket already carries %d %s", refused, held.count, held.name)
    end
  end
  return refused
end

local function insert(params)
  local character = body()
  local entity = reachable_entity(character, params)
  local item = string_param(params, "item")
  if not prototypes.item[item] then
    reject_unless_item(item)
  end
  local stacks = held_stacks(character, item)
  local have = 0
  for _, stack in ipairs(stacks) do
    have = have + stack.count
  end
  if have == 0 then
    reject(
      character.get_item_count(item) > 0 and string.format("your %s is equipped", item)
        or ("you have no " .. item)
    )
  end
  -- Asking for more than you carry hands over what you have, as a
  -- ctrl-click does; `short` says how many were missing.
  local asked = math.floor(number_param(params, "count", have, 1, TRANSFER_MAX_COUNT))
  local count = math.min(asked, have)
  if not entity.can_insert({ name = item, count = 1 }) then
    reject(insert_problem(entity, item))
  end
  local inserted = 0
  local full = false
  for _, stack in ipairs(stacks) do
    if not full and inserted < count then
      local wanted = math.min(stack.count, count - inserted)
      local moved = move_items(stack, entity, wanted)
      inserted = inserted + moved
      full = moved < wanted
    end
  end
  return {
    inserted = inserted,
    short = asked > have and asked - have or nil,
    entity = entity_view(entity),
  }
end

-- What a machine is doing, as its status icon and progress bar show: for a
-- `take` that finds nothing, what it is making and when the next one is
-- done, or the status that holds it up and which ingredients it lacks.
local function activity(entity)
  local status = status_name(entity)
  if not status then
    return ""
  end
  local recipe = CRAFTERS[entity.type] and entity.get_recipe()
  if recipe and status == "working" then
    local product = recipe.products[1]
    local ticks = (1 - entity.crafting_progress) * recipe.energy * 60 / entity.crafting_speed
    return string.format(
      "; it is making %s, the next one in about %d ticks",
      product and product.name or recipe.name,
      math.ceil(ticks)
    )
  end
  local missing = missing_ingredients_of(entity, status)
  if missing then
    local parts = {}
    for _, short in ipairs(missing) do
      parts[#parts + 1] =
        string.format("%s (has %s, one craft takes %s)", short.name, short.have, short.need)
    end
    return string.format("; its status is %s: it is short of %s", status, table.concat(parts, ", "))
  end
  return "; its status is " .. status
end

local function take(params)
  local character = body()
  local entity = reachable_entity(character, params)
  local item = optional_string_param(params, "item")
  if item and not prototypes.item[item] then
    reject_unless_item(item)
  end
  local wanted =
    math.floor(number_param(params, "count", TRANSFER_MAX_COUNT, 1, TRANSFER_MAX_COUNT))
  local taken = {}
  local full = false
  local laned = LANED[entity.type]
  -- Move what is still wanted of one stack into the inventory. Without Space
  -- Age an item on a belt is a stack of one, so it moves whole once the
  -- inventory has room for it, and nothing is ever put back on the belt.
  local function take_stack(stack)
    if wanted > 0 and stack.valid_for_read and (not item or stack.name == item) then
      if laned and not character.can_insert(stack) then
        full = true
        return
      end
      local stack_name = stack.name
      local count = math.min(stack.count, wanted)
      local moved = move_items(stack, character, count)
      if moved > 0 then
        taken[stack_name] = (taken[stack_name] or 0) + moved
        wanted = wanted - moved
      end
      full = full or moved < count
    end
  end
  if laned then
    -- What lies on every lane of the entity (a splitter's two belts, an
    -- underground belt's lanes below ground), as a player picks it up by
    -- hand. Last first, so taking an item leaves the slots still to look at
    -- in place.
    for index = 1, entity.get_max_transport_line_index() do
      local line = entity.get_transport_line(index --[[@as defines.transport_line]])
      for slot = #line, 1, -1 do
        take_stack(line[slot])
      end
    end
  else
    for index = 1, entity.get_max_inventory_index() do
      local inventory = entity.get_inventory(index --[[@as defines.inventory]])
      local name = inventory and entity.get_inventory_name(index --[[@as defines.inventory]])
      if inventory and (item or OUTPUTS[name]) then
        for slot = 1, #inventory do
          take_stack(inventory[slot])
        end
      end
    end
  end
  local list = {}
  for name, count in pairs(taken) do
    list[#list + 1] = { name = name, count = count }
  end
  table.sort(list, function(a, b)
    return a.name < b.name
  end)
  if #list == 0 then
    if full then
      reject("your inventory is full")
    end
    if laned then
      reject(
        item and string.format("%s has no %s on it", entity.name, item)
          or (entity.name .. " has nothing on it")
      )
    end
    reject(
      (
        item and string.format("%s has no %s", entity.name, item)
        or (entity.name .. " has nothing in its output")
      ) .. activity(entity)
    )
  end
  return { taken = list, inventory_full = full, entity = entity_view(entity) }
end

local function rotate(params)
  local character = body()
  local entity = reachable_entity(character, params)
  if not entity.supports_direction or not entity.rotate({}) then
    reject(entity.name .. " can't be rotated")
  end
  return with_belt_link(entity_view(entity), entity)
end

-- Silo states between a finished rocket and one ready to launch: the doors
-- open and the rocket rises (it needs power to).
local RISING = {}
for _, name in ipairs({
  "create_rocket",
  "lights_blinking_open",
  "doors_opening",
  "doors_opened",
  "rocket_rising",
  "arms_advance",
}) do
  RISING[defines.rocket_silo_status[name]] = true
end

-- Launch the rocket standing in one of the agent's silos, as the Launch
-- button in the silo's window does. The game's button refuses an empty
-- rocket, but LuaEntity.launch_rocket launches one (probed), so the mod
-- checks for a payload itself. The game counts the launch (and the rocket
-- milestone) when the rocket reaches space, about 19 seconds later.
local function launch(params)
  local character = body()
  local silo = reachable_entity(character, params)
  if silo.type ~= "rocket-silo" then
    reject(silo.name .. " is not a rocket silo; rockets launch from a rocket-silo")
  end
  local status = silo.rocket_silo_status
  if status == defines.rocket_silo_status.building_rocket then
    reject(
      string.format(
        "the rocket is not built yet: %d/%d rocket parts",
        silo.rocket_parts,
        silo.prototype.rocket_parts_required
      )
    )
  elseif RISING[status] then
    reject(
      string.format(
        "the rocket is still rising into launch position (%s); it is ready in a few seconds if the silo has power",
        SILO_STATUS_NAMES[status]
      )
    )
  elseif status ~= defines.rocket_silo_status.rocket_ready then
    reject(
      string.format("a launch from this silo is already under way (%s)", SILO_STATUS_NAMES[status])
    )
  end
  local payload = silo.get_inventory(defines.inventory.rocket_silo_rocket)
  if not payload or payload.is_empty() then
    reject(
      "the rocket has no payload and the game won't launch an empty rocket; insert one into the silo first, such as raw-fish or a satellite"
    )
  end
  ---@cast payload LuaInventory
  local launched = item_list(payload.get_contents())
  if not silo.launch_rocket() then
    reject("the game would not launch the rocket")
  end
  return { launched = launched, entity = entity_view(silo) }
end

-- Look at one entity up close, anywhere the agent can see.
local function inspect(params)
  local character = body()
  local target = position_param(params)
  local away = distance(character.position, target)
  if away > OBSERVE_MAX_RADIUS then
    reject(
      string.format("that point is %.2f tiles away; you can see %d tiles", away, OBSERVE_MAX_RADIUS)
    )
  end
  local entity = entity_at(character, target)
  if not entity then
    reject(string.format("nothing at %.2f, %.2f", target.x, target.y))
  end
  ---@cast entity LuaEntity
  local view = entity_view(entity)
  view.distance = round(distance_to_box(character.position, entity))
  if entity.type == "resource" then
    view.amount = entity.amount
  elseif entity.type == "item-entity" then
    view.item = entity.stack.name
  end
  return view
end

-- The drills that extract a resource the character can't mine by hand
-- (crude-oil: pumpjack), or nil when a player mines it by hand.
local function extracting_drills(resource_name)
  local resource = prototypes.entity[resource_name]
  if not resource or resource.type ~= "resource" then
    return nil
  end
  local category = resource.resource_category
  local fluid = resource.mineable_properties.required_fluid
  local hand = prototypes.entity["character"].resource_categories or {}
  if hand[category] and not fluid then
    return nil
  end
  local drills = {}
  for name, drill in
    pairs(prototypes.get_entity_filtered({ { filter = "type", type = "mining-drill" } }))
  do
    if drill.resource_categories[category] and (not fluid or #drill.fluidbox_prototypes > 0) then
      drills[#drills + 1] = name
    end
  end
  table.sort(drills)
  return drills
end

-- The crafting categories of the recipes that make an item, or nil when the
-- character can hand-craft one of them. A craft-item trigger counts every
-- item the force produces, so an item only a machine makes (copper-plate in a
-- furnace) is made, not crafted with `fac craft`.
local function machine_categories(item_name)
  local hand = prototypes.entity["character"].crafting_categories or {}
  local seen, categories = {}, {}
  for _, recipe in pairs(prototypes.recipe) do
    local makes = false
    for _, product in pairs(recipe.products or {}) do
      makes = makes or (product.type == "item" and product.name == item_name)
    end
    if makes and not recipe.hidden then
      for _, category in pairs(recipe.categories) do
        if hand[category] and not recipe.hidden_from_player_crafting then
          return nil
        end
        if not seen[category] then
          seen[category] = true
          categories[#categories + 1] = category
        end
      end
    end
  end
  if #categories == 0 then
    return nil
  end
  table.sort(categories)
  return categories
end

-- What unlocks a technology that labs don't research, in words. A resource
-- the character can't mine by hand names the drill instead (decision 66:
-- oil-processing fires when a pumpjack extracts crude), and an item the
-- character can't hand-craft names the machine's crafting category.
local function trigger_text(trigger)
  if trigger.type == "craft-item" then
    local item = trigger.item
    local name = type(item) == "table" and item.name or item
    local count = trigger.count or 1
    local categories = machine_categories(name)
    if categories then
      return string.format(
        "make %d %s in a machine (%s)",
        count,
        name,
        table.concat(categories, ", ")
      )
    end
    return string.format("craft %d %s", count, name)
  elseif trigger.type == "mine-entity" then
    local actions = {}
    for _, entity in ipairs(trigger.entities or {}) do
      local drills = extracting_drills(entity)
      if drills and #drills > 0 then
        local named = {}
        for i, drill in ipairs(drills) do
          named[i] = (drill:match("^[aeiou]") and "an " or "a ") .. drill
        end
        actions[#actions + 1] = "extract " .. entity .. " with " .. table.concat(named, " or ")
      else
        actions[#actions + 1] = "mine " .. entity
      end
    end
    return table.concat(actions, " or ")
  end
  return trigger.type
end

-- Technologies whose effects unlock each recipe, from prototypes. Built once:
-- prototypes don't change during a game.
local recipe_technologies
-- The technologies that unlock a recipe for a force. Enabled ones only, read
-- from the force each call, so a technology the scenario turns off at runtime
-- is not named (decision 66).
local function technologies_unlocking(force, recipe_name)
  if not recipe_technologies then
    recipe_technologies = {}
    for _, tech in pairs(prototypes.technology) do
      for _, effect in pairs(tech.effects) do
        if effect.type == "unlock-recipe" and effect.recipe then
          local list = recipe_technologies[effect.recipe]
          if not list then
            list = {}
            recipe_technologies[effect.recipe] = list
          end
          list[#list + 1] = tech.name
        end
      end
    end
    for _, list in pairs(recipe_technologies) do
      table.sort(list)
    end
  end
  local enabled = {}
  for _, name in ipairs(recipe_technologies[recipe_name] or {}) do
    if force.technologies[name].enabled then
      enabled[#enabled + 1] = name
    end
  end
  return enabled
end

-- A locked recipe names the technology a player would see on it, and a
-- trigger technology's action (oil-processing when a pumpjack extracts crude).
local function locked_recipe_message(force, recipe_name)
  local techs = technologies_unlocking(force, recipe_name)
  if #techs == 0 then
    return recipe_name .. " is not unlocked yet"
  end
  local parts = {}
  local labs = {}
  for _, name in ipairs(techs) do
    local trigger = prototypes.technology[name].research_trigger
    if trigger then
      parts[#parts + 1] = string.format("%s unlocks it when you %s", name, trigger_text(trigger))
    else
      labs[#labs + 1] = name
    end
  end
  if #labs > 0 then
    parts[#parts + 1] = "research " .. table.concat(labs, " or ")
  end
  return recipe_name .. " is not unlocked yet; " .. table.concat(parts, "; ")
end

-- Choose what an assembling machine makes, as a player does in its window.
-- A chemical plant and an oil refinery are assembling machines too
-- (chemistry and oil-processing). Ingredients it held that the new recipe
-- doesn't use come back to the inventory, spilled at the body's feet if it
-- is full.
local function set_recipe(params)
  local character = body()
  local entity = reachable_entity(character, params)
  if entity.type ~= "assembling-machine" then
    reject(
      entity.name
        .. " has no recipe to choose; only assembling machines do, including a chemical plant or an oil refinery"
    )
  end
  local name = string_param(params, "recipe")
  local prototype = prototypes.recipe[name]
  if not prototype then
    reject("no recipe called " .. name)
  end
  ---@cast prototype LuaRecipePrototype
  if not character.force.recipes[name].enabled then
    reject(locked_recipe_message(character.force, name))
  end
  -- The game takes a recipe the machine can't make without an error and
  -- leaves it with none (probed), so the mod checks the categories.
  local entity_categories = entity.prototype.crafting_categories or {}
  local fits = false
  for _, category in pairs(prototype.categories) do
    fits = fits or entity_categories[category] ~= nil
  end
  if not fits or prototype.hidden then
    reject(
      string.format(
        "%s can't make %s; it needs a machine for %s",
        entity.name,
        name,
        table.concat(prototype.categories, ", ")
      )
    )
  end
  local returned = {}
  for _, stack in pairs(entity.set_recipe(name)) do
    local moved =
      character.insert({ name = stack.name, count = stack.count, quality = stack.quality })
    if moved < stack.count then
      character.surface.spill_item_stack({
        position = character.position,
        stack = { name = stack.name, count = stack.count - moved, quality = stack.quality },
      })
    end
    returned[#returned + 1] = { name = stack.name, count = stack.count }
  end
  return { returned = item_list(returned), entity = entity_view(entity) }
end

-- Research ---------------------------------------------------------------------

-- These helpers exist only for `research`. Scoping them here drops their
-- locals before the later commands, which keeps the chunk within the 200
-- local limit.
local research
do
  local function queued_names(force)
    local queued = {}
    for _, tech in pairs(force.research_queue or {}) do
      queued[tech.name] = true
    end
    return queued
  end

  -- Prerequisites neither researched nor in the queue. The engine queues a
  -- technology behind its queued prerequisites (probed), as a player can.
  local function missing_prerequisites(tech, queued)
    local missing = {}
    for name, prerequisite in pairs(tech.prerequisites) do
      if not prerequisite.researched and not queued[name] then
        missing[#missing + 1] = name
      end
    end
    table.sort(missing)
    return missing
  end

  -- Technologies that have this one as a prerequisite: where it leads, as
  -- the tech tree screen shows.
  local function leads_to(tech)
    local names = {}
    for name, successor in pairs(tech.successors) do
      if successor.enabled then
        names[#names + 1] = name
      end
    end
    table.sort(names)
    return names
  end

  local function tech_view(tech)
    local prototype = tech.prototype
    local unlocks = {}
    for _, effect in pairs(prototype.effects) do
      if effect.type == "unlock-recipe" then
        unlocks[#unlocks + 1] = effect.recipe
      end
    end
    local view = { name = tech.name, unlocks = unlocks, leads_to = leads_to(tech) }
    if prototype.research_trigger then
      view.trigger = trigger_text(prototype.research_trigger)
    else
      -- Science packs per unit by name: every base-game technology takes one
      -- of each (checked on 2.1.24), so a count shows only when it isn't 1.
      local packs = {}
      for _, ingredient in pairs(tech.research_unit_ingredients) do
        packs[#packs + 1] = ingredient.amount == 1 and ingredient.name
          or string.format("%d %s", ingredient.amount, ingredient.name)
      end
      view.cost = {
        units = tech.research_unit_count,
        packs = packs,
        seconds_per_unit = round(tech.research_unit_energy / 60),
      }
    end
    return view
  end

  -- What is being researched and what is queued behind it.
  local function queue_view(force)
    local queue = {}
    for _, tech in pairs(force.research_queue or {}) do
      queue[#queue + 1] = tech.name
    end
    local current = force.current_research
    return {
      current = current and { name = current.name, progress = round(force.research_progress) }
        or nil,
      queue = queue,
    }
  end

  -- The queue, what can be researched next, and how many technologies are
  -- researched; their names only when asked for.
  local function research_status(force, list_researched)
    local available, researched = {}, {}
    local queued = queued_names(force)
    for _, tech in pairs(force.technologies) do
      if tech.researched then
        researched[#researched + 1] = tech.name
      elseif tech.enabled and #missing_prerequisites(tech, queued) == 0 then
        available[#available + 1] = tech_view(tech)
      end
    end
    table.sort(researched)
    table.sort(available, function(a, b)
      return a.name < b.name
    end)
    local view = queue_view(force)
    view.available = available
    view.researched = #researched
    if list_researched then
      view.researched_names = researched
    end
    return view
  end

  -- Prerequisites, all the way back, that are neither researched nor queued,
  -- each after its own prerequisites: the order to queue them in. It can
  -- include trigger technologies, which unlock by an action, not by queueing.
  local function still_needed(tech, queued)
    local order, seen = {}, {}
    local function visit(current)
      local names = {}
      for name in pairs(current.prerequisites) do
        names[#names + 1] = name
      end
      table.sort(names)
      for _, name in ipairs(names) do
        local prerequisite = current.prerequisites[name]
        if not seen[name] and not prerequisite.researched and not queued[name] then
          seen[name] = true
          visit(prerequisite)
          order[#order + 1] = name
        end
      end
    end
    visit(tech)
    return order
  end

  -- One technology as the tech tree screen shows it, without queueing it:
  -- whether it is researched, queued, available or locked, its cost, what it
  -- unlocks, its prerequisites, what is still needed before it and where it
  -- leads.
  local function show_tech(force, tech)
    local queued = queued_names(force)
    local view = tech_view(tech)
    local current = force.current_research
    if tech.researched then
      view.state = "researched"
    elseif current and current.name == tech.name then
      view.state = "current"
    elseif queued[tech.name] then
      view.state = "queued"
    elseif #missing_prerequisites(tech, queued) == 0 then
      view.state = "available"
    else
      view.state = "locked"
    end
    local prerequisites = {}
    for name in pairs(tech.prerequisites) do
      prerequisites[#prerequisites + 1] = name
    end
    table.sort(prerequisites)
    view.prerequisites = prerequisites
    view.needs = still_needed(tech, queued)
    return view
  end

  -- The engine's research queue holds at most this many technologies, the
  -- current one included (probed on 2.1.24: add_research refuses an eighth).
  local RESEARCH_QUEUE_MAX = 7

  -- With no technology named, what is being researched and what can be.
  -- Naming one adds it to the end of the research queue, as clicking it does,
  -- behind any prerequisites not yet researched or queued;
  -- `cancel` takes it out of the queue, and the engine drops with it the
  -- technologies queued behind it (probed); `show` describes it without
  -- touching the queue. Changing the queue returns the queue alone.
  function research(params)
    local force = body().force
    local name = optional_string_param(params, "tech")
    if not name then
      return research_status(force, params.researched == true)
    end
    local tech = force.technologies[name]
    if not tech then
      reject("no technology called " .. name)
    end
    ---@cast tech LuaTechnology
    if params.show then
      return show_tech(force, tech)
    end
    if params.cancel then
      local queue, found = {}, false
      for _, queued in pairs(force.research_queue or {}) do
        if queued.name == name then
          found = true
        else
          queue[#queue + 1] = queued.name
        end
      end
      if not found then
        reject(name .. " is not in the research queue")
      end
      force.research_queue = queue
      return queue_view(force)
    end
    if tech.researched then
      reject(name .. " is already researched")
    end
    local queued = queued_names(force)
    if queued[name] then
      reject(name .. " is already in the research queue")
    end
    local trigger = tech.prototype.research_trigger
    if trigger then
      reject(
        string.format(
          "%s is not researched in labs; it unlocks when you %s",
          name,
          trigger_text(trigger)
        )
      )
    end
    -- Like the tech screen, queue the missing prerequisites first, each after
    -- its own, then the technology; all of them or none.
    local order = still_needed(tech, queued)
    for _, needed in ipairs(order) do
      local needed_trigger = force.technologies[needed].prototype.research_trigger
      if needed_trigger then
        reject(
          string.format(
            "%s needs %s, which is not researched in labs; it unlocks when you %s",
            name,
            needed,
            trigger_text(needed_trigger)
          )
        )
      end
    end
    order[#order + 1] = name
    local free = RESEARCH_QUEUE_MAX - #(force.research_queue or {})
    if #order > free then
      reject(
        string.format(
          "queueing %s takes %d slot%s (%s) but the research queue holds at most %d technologies and has %d free; nothing was queued",
          name,
          #order,
          #order == 1 and "" or "s",
          table.concat(order, ", "),
          RESEARCH_QUEUE_MAX,
          free
        )
      )
    end
    -- The engine can still refuse one, a disabled technology for one; put the
    -- queue back as it was so a refusal queues nothing.
    local before = {}
    for _, queued_tech in pairs(force.research_queue or {}) do
      before[#before + 1] = queued_tech.name
    end
    for _, needed in ipairs(order) do
      if not force.add_research(needed) then
        force.research_queue = before
        reject("the research queue would not take " .. needed .. "; nothing was queued")
      end
    end
    return queue_view(force)
  end
end

-- Crafting -------------------------------------------------------------------

-- The engine counts a player's hand-crafts in the force's production
-- statistics, and craft-item research triggers (craft a lab) fire from
-- them, but it counts nothing a playerless character crafts (probed). So
-- the mod adds the products of each finished craft itself; `on_flow` fires
-- the triggers as a player's craft would (probed). Milestones count the
-- science packs among them as hand-made.
local function credit_crafts(character, recipe_name, crafts)
  local statistics = character.force.get_item_production_statistics(character.surface)
  for _, product in pairs(prototypes.recipe[recipe_name].products) do
    if product.type == "item" then
      local amount = product.amount or product.amount_min
      statistics.on_flow(product.name, amount * crafts)
      milestones.hand_crafted(product.name, amount * crafts)
    end
  end
end

-- The hand-craft queue is first in first out, so the crafts finished since
-- the last look are the first ones in the queue as it was then, and a craft
-- job is done once every craft queued up to and including its own has
-- completed.
local function count_completed_crafts(character)
  local crafts = state().crafts
  local queue = queue_snapshot(character)
  local finished = total_crafts(crafts.queue) - total_crafts(queue)
  if finished > 0 then
    crafts.completed = crafts.completed + finished
    for _, entry in ipairs(crafts.queue) do
      if finished == 0 then
        break
      end
      local done = math.min(entry.count, finished)
      credit_crafts(character, entry.recipe, done)
      finished = finished - done
    end
  end
  crafts.queue = queue
end

-- A save from 0.2.0 kept only the number of crafts queued at the last look,
-- and on_tick counts before the tick's crafting runs, so a craft that
-- finished since is in that number but not in the queue. Count it as
-- finished, crediting the queue's head recipe (0.2.0 didn't store which one
-- it was), then keep the queue itself from here on. With the body gone its
-- crafts were never made; ensure_body ends their jobs.
function M.migrate_crafts()
  local s = storage.agent
  local crafts = s.crafts
  local character = s.character
  if character and character.valid then
    local queue = queue_snapshot(character)
    local finished = (crafts.queued or 0) - total_crafts(queue)
    if finished > 0 then
      crafts.completed = crafts.completed + finished
      if queue[1] then
        credit_crafts(character, queue[1].recipe, finished)
      end
    end
    crafts.queue = queue
  else
    crafts.queue = {}
  end
  crafts.queued = nil
end

local function missing_ingredients(character, recipe)
  local parts = {}
  for _, ingredient in pairs(recipe.ingredients) do
    parts[#parts + 1] = string.format(
      "%s %d (have %d)",
      ingredient.name,
      ingredient.amount,
      character.get_item_count(ingredient.name)
    )
  end
  return table.concat(parts, ", ")
end

-- What left an inventory between two looks at its contents, as a sorted
-- list of {name, count}.
local function items_gone(before, after)
  local left = {}
  for _, entry in ipairs(item_list(after)) do
    left[entry.name] = entry.count
  end
  local gone = {}
  for _, entry in ipairs(item_list(before)) do
    local fewer = entry.count - (left[entry.name] or 0)
    if fewer > 0 then
      gone[#gone + 1] = { name = entry.name, count = fewer }
    end
  end
  return gone
end

local function craft(params)
  local character = body()
  if type(params.recipe) ~= "string" then
    bad_params("recipe is required")
  end
  local count = math.floor(number_param(params, "count", 1, 1, CRAFT_MAX_COUNT))
  local prototype = prototypes.recipe[params.recipe]
  if not prototype then
    reject("no recipe called " .. params.recipe)
  end
  ---@cast prototype LuaRecipePrototype
  local recipe = character.force.recipes[params.recipe]
  if not recipe.enabled then
    reject(locked_recipe_message(character.force, params.recipe))
  end
  local by_hand = false
  for _, category in pairs(prototype.categories) do
    by_hand = by_hand or character.prototype.crafting_categories[category] ~= nil
  end
  if not by_hand or prototype.hidden_from_player_crafting then
    reject(
      params.recipe
        .. " can't be crafted by hand; it needs a machine ("
        .. table.concat(prototype.categories, ", ")
        .. ")"
    )
  end
  local craftable = character.get_craftable_count(params.recipe)
  if craftable < count then
    reject(
      string.format(
        "can hand-craft %d %s right now, not %d; one craft needs %s",
        craftable,
        params.recipe,
        count,
        missing_ingredients(character, prototype)
      )
    )
  end

  count_completed_crafts(character)
  -- The engine takes the ingredients at once, intermediates the agent
  -- carries before it queues crafts of more, so the job says what it took.
  local inventory = character.get_main_inventory()
  ---@cast inventory LuaInventory
  local before = inventory.get_contents()
  local started = character.begin_crafting({ recipe = params.recipe, count = count })
  if started == 0 then
    reject(string.format("the game would not start crafting %s", params.recipe))
  end
  local s = state()
  s.crafts.queue = queue_snapshot(character)
  local job = new_job("craft", {
    recipe = params.recipe,
    count = started,
    used = items_gone(before, inventory.get_contents()),
    done_at = s.crafts.completed + total_crafts(s.crafts.queue),
  })
  s.craft_jobs[#s.craft_jobs + 1] = job.id
  return describe(job)
end

-- Craft jobs finish in the order they were queued.
local function step_crafts()
  local s = state()
  local pending = s.craft_jobs
  while pending[1] do
    local job = s.jobs[pending[1]]
    if job and job.state == "running" then
      if s.crafts.completed < job.done_at then
        return
      end
      finish(job, "done")
    end
    table.remove(pending, 1)
  end
end

-- Observation ----------------------------------------------------------------

local function inventory_list(character)
  local items = {}
  for _, stack in pairs(character.get_main_inventory().get_contents()) do
    items[#items + 1] = { name = stack.name, count = stack.count }
  end
  table.sort(items, function(a, b)
    return a.name < b.name
  end)
  return items
end

-- What the agent carries, all of it or just the named items (0 for one it
-- has none of).
local function inventory(params)
  local character = body()
  local names = params.items
  if names == nil then
    return { inventory = inventory_list(character) }
  end
  if type(names) ~= "table" then
    bad_params("items must be a list of item names")
  end
  local main = character.get_main_inventory() --[[@as LuaInventory]]
  local items = {}
  for _, name in ipairs(names) do
    if type(name) ~= "string" then
      bad_params("items must be a list of item names")
    end
    if not prototypes.item[name] then
      reject_unless_item(name)
    end
    items[#items + 1] = { name = name, count = main.get_item_count(name) }
  end
  return { inventory = items }
end

-- Production statistics --------------------------------------------------------

-- What the force made and used of an item or fluid on a surface, as the
-- production window (P) shows it: per minute averaged over the last minute
-- and the last 10 minutes (a world younger than a window counts nothing
-- before it began), and in all since the map began. Hand-crafted products
-- count as made (decision 39), and the engine counts what hand-crafting
-- uses up (probed on 2.1.24).
local function flow_entry(statistics, name, fluid)
  local function per_minute(category, precision)
    return round(
      statistics.get_flow_count({ name = name, category = category, precision_index = precision })
    )
  end
  local one, ten = defines.flow_precision_index.one_minute, defines.flow_precision_index.ten_minutes
  return {
    name = name,
    fluid = fluid or nil,
    made_1m = per_minute("input", one),
    used_1m = per_minute("output", one),
    made_10m = per_minute("input", ten),
    used_10m = per_minute("output", ten),
    made = round(statistics.get_input_count(name)),
    used = round(statistics.get_output_count(name)),
  }
end

-- The production window: every item and fluid made or used in the last 10
-- minutes, busiest in the last minute first, and the names of the others
-- ever made or used; or just the named ones, in the order given.
local function stats(params)
  local character = body()
  local items = character.force.get_item_production_statistics(character.surface)
  local fluids = character.force.get_fluid_production_statistics(character.surface)
  local names = params.items
  if names ~= nil then
    if type(names) ~= "table" then
      bad_params("items must be a list of item or fluid names")
    end
    local list = {}
    for _, name in ipairs(names) do
      if type(name) ~= "string" then
        bad_params("items must be a list of item or fluid names")
      end
      if prototypes.item[name] then
        list[#list + 1] = flow_entry(items, name, false)
      elseif prototypes.fluid[name] then
        list[#list + 1] = flow_entry(fluids, name, true)
      else
        reject("there is no item or fluid called " .. name)
      end
    end
    return { items = list }
  end
  local active, idle = {}, {}
  for _, statistics in ipairs({ items, fluids }) do
    local seen = {}
    for _, counts in ipairs({ statistics.input_counts, statistics.output_counts }) do
      for name in pairs(counts) do
        if not seen[name] then
          seen[name] = true
          local entry = flow_entry(statistics, name, statistics == fluids)
          if entry.made_10m > 0 or entry.used_10m > 0 then
            active[#active + 1] = entry
          else
            idle[#idle + 1] = name
          end
        end
      end
    end
  end
  table.sort(active, function(a, b)
    local a1, b1 = a.made_1m + a.used_1m, b.made_1m + b.used_1m
    if a1 ~= b1 then
      return a1 > b1
    end
    local a10, b10 = a.made_10m + a.used_10m, b.made_10m + b.used_10m
    if a10 ~= b10 then
      return a10 > b10
    end
    return a.name < b.name
  end)
  table.sort(idle)
  return { items = active, idle = idle }
end

local function running_jobs()
  local list = {}
  for _, job in pairs(state().jobs) do
    if job.state == "running" then
      list[#list + 1] = describe(job)
    end
  end
  table.sort(list, function(a, b)
    return a.id < b.id
  end)
  return list
end

-- `observe` folds belts into runs and lists stalled machines. Its helpers
-- are scoped here so their locals are gone before `map` and the job
-- commands, which keeps the chunk within the 200 local limit.
local observe, icons_in_view
do
  -- Left out of `observe`: what is left of trees and buildings (stumps,
  -- remnants) is scenery and blocks nothing.
  local SCENERY = { corpse = true, ["rail-remnants"] = true }
  -- Machines whose status a player sees as an icon over them (no fuel, no
  -- power, output full); `observe` shows it for these.
  local MACHINES = {
    ["assembling-machine"] = true,
    furnace = true,
    ["rocket-silo"] = true,
    ["mining-drill"] = true,
    inserter = true,
    lab = true,
    boiler = true,
    generator = true,
    ["burner-generator"] = true,
    ["offshore-pump"] = true,
    pump = true,
    radar = true,
    beacon = true,
    reactor = true,
  }

  -- Straight belt runs as one entry each: belts of one name facing one way,
  -- each feeding the next tile along that way. A single belt stays an
  -- ordinary entry; a run of two or more gives its first and last tile in
  -- the direction items travel, and how many tiles it has. `lanes` adds up
  -- what lies on the run's tiles per lane (left out when there is nothing),
  -- and `fill` is their count over the most the run's tiles hold, 1 for a
  -- belt packed full.
  local function belt_runs(belts, here)
    local at = {}
    for _, belt in ipairs(belts) do
      at[belt.position.x .. "," .. belt.position.y] = belt
    end
    local function next_of(belt, sign)
      local step = STEPS[belt.direction]
      local other = step
        and at[(belt.position.x + sign * step.x) .. "," .. (belt.position.y + sign * step.y)]
      if other and other.name == belt.name and other.direction == belt.direction then
        return other
      end
    end
    local entries, used = {}, {}
    local function run_from(first)
      local run, belt = {}, first
      while belt and not used[belt] do
        used[belt] = true
        run[#run + 1] = belt
        belt = next_of(belt, 1)
      end
      local nearest, left, right, count, room = math.huge, {}, {}, 0, 0
      for _, tile in ipairs(run) do
        nearest = math.min(nearest, distance(here, tile.position))
        room = room + tile.room
        for _, pair in ipairs({ { tile.left, left }, { tile.right, right } }) do
          for _, entry in ipairs(pair[1]) do
            pair[2][#pair[2] + 1] = entry
            count = count + entry.count
          end
        end
      end
      local entry = {
        name = first.name,
        type = first.type,
        direction = DIRECTION_NAMES[first.direction],
        distance = nearest,
        lanes = count > 0 and { left = item_list(left), right = item_list(right) } or nil,
        fill = round(count / room),
      }
      if #run == 1 then
        entry.position = point(first.position)
      else
        entry.from = point(first.position)
        entry.to = point(run[#run].position)
        entry.tiles = #run
      end
      entries[#entries + 1] = entry
    end
    -- Runs start at a belt nothing of the run feeds; what is left over is a loop.
    for _, belt in ipairs(belts) do
      if not next_of(belt, -1) then
        run_from(belt)
      end
    end
    for _, belt in ipairs(belts) do
      if not used[belt] then
        run_from(belt)
      end
    end
    return entries
  end

  local MACHINE_TYPES = {}
  for name in pairs(MACHINES) do
    MACHINE_TYPES[#MACHINE_TYPES + 1] = name
  end
  table.sort(MACHINE_TYPES)

  local function own_machines(character, radius)
    return character.surface.find_entities_filtered({
      position = character.position,
      radius = radius,
      type = MACHINE_TYPES,
      force = character.force,
    })
  end

  -- The fields `observe` and `fac observe --problems` share for one machine.
  local function machine_summary(entity, here, status)
    return {
      name = entity.name,
      type = entity.type,
      position = point(entity.position),
      direction = entity.supports_direction and DIRECTION_NAMES[entity.direction] or nil,
      status = status,
      missing = missing_ingredients_of(entity, status),
      distance = distance(here, entity.position),
    }
  end

  -- Statuses of a machine doing what it is there for. An inserter also
  -- waits between swings in a block that works, for the machine it takes
  -- from to finish or the one it feeds to use up what it holds; when the
  -- block is held up, that machine shows it. A drill waits the same way
  -- when its belt or furnace is full, and a boiler says `full_output` when
  -- its engines need no more steam: a full buffer, not a fault.
  local FINE = { working = true, normal = true }
  local WAITING = {
    inserter = { waiting_for_source_items = true, waiting_for_space_in_destination = true },
    ["mining-drill"] = { waiting_for_space_in_destination = true },
    boiler = { full_output = true },
  }

  -- Only the agent's machines within the radius that aren't working, nearest
  -- first, so stalled machines in a big block aren't cut off behind the
  -- working ones nearer the agent, as walking along it and looking for the
  -- icons over them shows a player.
  local function problems(character, radius)
    local here = character.position
    local found = own_machines(character, radius)
    local stalled = {}
    for _, entity in pairs(found) do
      local status = status_name(entity)
      local waiting = WAITING[entity.type]
      if not FINE[status] and not (waiting and waiting[status]) then
        stalled[#stalled + 1] = machine_summary(entity, here, status)
      end
    end
    table.sort(stalled, function(a, b)
      return a.distance < b.distance
    end)
    local shown = {}
    for i = 1, math.min(#stalled, OBSERVE_MAX_ENTITIES) do
      shown[i] = stalled[i]
      shown[i].distance = nil
    end
    return {
      position = point(here),
      radius = radius,
      machines = #found,
      entities = shown,
      entities_not_shown = #stalled - #shown,
    }
  end

  -- Statuses the game draws a warning icon for over the machine, whatever
  -- the player is doing: the yellow plug, the fuel icon and the red
  -- mined-out triangle. `no_power` is the network's, which the HUD names
  -- from its poles.
  local ICON_STATUSES = { "not_plugged_in_electric_network", "no_fuel", "no_minable_resources" }

  -- One sentence counting the agent's machines within the radius that
  -- show such an icon, with the nearest of each kind, and a key naming the
  -- kinds shown, so the HUD repeats it for a new kind but not a new count;
  -- nil when none does.
  function icons_in_view(character, radius)
    local here = character.position
    local found = own_machines(character, radius)
    local groups = {}
    for _, entity in pairs(found) do
      local status = status_name(entity)
      local group = groups[status]
      if not group then
        group = { count = 0, nearest = math.huge }
        groups[status] = group
      end
      group.count = group.count + 1
      local away = distance(here, entity.position)
      if away < group.nearest then
        group.nearest = away
        group.entity = entity
      end
    end
    local parts, kinds = {}, {}
    for _, status in ipairs(ICON_STATUSES) do
      local group = groups[status]
      if group then
        kinds[#kinds + 1] = status
        parts[#parts + 1] = string.format(
          "%d %s (nearest: %s at %s, %s)",
          group.count,
          status,
          group.entity.name,
          group.entity.position.x,
          group.entity.position.y
        )
      end
    end
    if #parts == 0 then
      return nil
    end
    return "machines in view show a warning icon: "
      .. table.concat(parts, "; ")
      .. "; `fac observe --problems` lists them",
      "icons " .. table.concat(kinds, " ")
  end

  function observe(params)
    local character = body()
    if params.problems ~= nil and type(params.problems) ~= "boolean" then
      bad_params("problems must be true or false")
    end
    if params.problems then
      return problems(
        character,
        number_param(params, "radius", OBSERVE_MAX_RADIUS, 1, OBSERVE_MAX_RADIUS)
      )
    end
    local radius = number_param(params, "radius", OBSERVE_RADIUS, 1, OBSERVE_MAX_RADIUS)
    local here = character.position
    local surface = character.surface

    local entities, belts = {}, {}
    local found = surface.find_entities_filtered({ position = here, radius = radius })
    local resources = {}
    for _, entity in pairs(found) do
      if entity.type == "resource" then
        local summary = resources[entity.name]
        if not summary then
          summary = { name = entity.name, tiles = 0, amount = 0 }
          resources[entity.name] = summary
        end
        summary.tiles = summary.tiles + 1
        summary.amount = summary.amount + entity.amount
        local away = distance(here, entity.position)
        if not summary.distance or away < summary.distance then
          summary.distance = away
          summary.nearest = point(entity.position)
        end
      elseif entity.type == "transport-belt" then
        belts[#belts + 1] = {
          name = entity.name,
          type = entity.type,
          position = entity.position,
          direction = entity.direction,
          room = belt_room(entity),
        }
        belts[#belts].left, belts[#belts].right = lane_contents(entity)
      elseif entity ~= character and not SCENERY[entity.type] then
        local status = MACHINES[entity.type] and status_name(entity) or nil
        local entry = machine_summary(entity, here, status)
        -- An item on the ground is an `item-on-ground`; this says which item.
        entry.item = entity.type == "item-entity" and entity.stack.name or nil
        if entity.type == "underground-belt" then
          entry.underground, entry.paired_with = underground_ends(entity)
        end
        if LANED[entity.type] then
          entry.lanes = belt_lanes(entity)
        end
        entities[#entities + 1] = entry
      end
    end
    for _, run in ipairs(belt_runs(belts, here)) do
      entities[#entities + 1] = run
    end
    table.sort(entities, function(a, b)
      return a.distance < b.distance
    end)
    local shown = {}
    for i = 1, math.min(#entities, OBSERVE_MAX_ENTITIES) do
      local entity = entities[i]
      entity.distance = nil -- the list is nearest first
      shown[i] = entity
    end
    local resource_list = {}
    for _, summary in pairs(resources) do
      summary.distance = round(summary.distance)
      resource_list[#resource_list + 1] = summary
    end
    -- Water is where an offshore pump goes, so it is listed with the resources.
    local water = surface.find_tiles_filtered({
      position = here,
      radius = radius,
      collision_mask = "water_tile",
    })
    if #water > 0 then
      local nearest, nearest_away
      for _, tile in pairs(water) do
        local centre = { x = tile.position.x + 0.5, y = tile.position.y + 0.5 }
        local away = distance(here, centre)
        if not nearest_away or away < nearest_away then
          nearest, nearest_away = centre, away
        end
      end
      resource_list[#resource_list + 1] =
        { name = "water", tiles = #water, nearest = point(nearest), distance = round(nearest_away) }
    end
    table.sort(resource_list, function(a, b)
      return a.distance < b.distance
    end)

    local crafting = {}
    for _, entry in pairs(character.crafting_queue or {}) do
      crafting[#crafting + 1] =
        { recipe = entry.recipe, count = entry.count, prerequisite = entry.prerequisite }
    end

    return {
      position = point(here),
      reach = {
        build = character.build_distance,
        interact = character.reach_distance,
        mine = character.resource_reach_distance,
      },
      inventory = inventory_list(character),
      crafting = crafting,
      jobs = running_jobs(),
      radius = radius,
      entities = shown,
      entities_not_shown = #entities - #shown,
      resources = resource_list,
    }
  end
end

-- A patch's tiles as the map view draws them: for each row its y and the
-- runs of neighbouring tiles, {from x, to x}, top row first.
local function patch_rows(tiles)
  local by_y = {}
  for _, p in ipairs(tiles) do
    local row = by_y[p.y]
    if not row then
      row = {}
      by_y[p.y] = row
    end
    row[#row + 1] = p.x
  end
  local rows = {}
  for y, xs in pairs(by_y) do
    table.sort(xs)
    local runs = { { xs[1], xs[1] } }
    for i = 2, #xs do
      local run = runs[#runs]
      if xs[i] - run[2] <= 1 then
        run[2] = xs[i]
      else
        runs[#runs + 1] = { xs[i], xs[i] }
      end
    end
    rows[#rows + 1] = { y = y, x = runs }
  end
  table.sort(rows, function(a, b)
    return a.y < b.y
  end)
  return rows
end

-- Resource patches and water in explored chunks, grouped by touching chunks,
-- nearest first. This is what a player sees of them in the map view. With
-- `resource`, only that one's patches, the nearest with its shape as `rows`.
local function map(params)
  local wanted = params.resource
  if wanted ~= nil and type(wanted) ~= "string" then
    bad_params("resource must be a name")
  end
  local character = body()
  local surface = character.surface
  local here = character.position
  local cells = {} -- name -> "x,y" -> cell
  local wanted_tiles = {} -- chunk key -> positions of the wanted resource

  -- Shared counters for one chunk cell and for the patch those cells merge into.
  local function fresh_extent(amount)
    return {
      tiles = 0,
      amount = amount and 0 or nil,
      sum_x = 0,
      sum_y = 0,
      min_x = math.huge,
      min_y = math.huge,
      max_x = -math.huge,
      max_y = -math.huge,
    }
  end

  -- Count one tile (a resource entity, or a water tile's centre) in its chunk.
  local function add(name, key, chunk, p, amount)
    -- The area also catches tiles touching its edge; count each tile in its own chunk only.
    if math.floor(p.x / CHUNK) ~= chunk.x or math.floor(p.y / CHUNK) ~= chunk.y then
      return
    end
    local by_name = cells[name]
    if not by_name then
      by_name = {}
      cells[name] = by_name
    end
    local cell = by_name[key]
    if not cell then
      cell = fresh_extent(amount)
      cell.x, cell.y = chunk.x, chunk.y
      by_name[key] = cell
    end
    if name == wanted then
      local list = wanted_tiles[key]
      if not list then
        list = {}
        wanted_tiles[key] = list
      end
      list[#list + 1] = p
    end
    cell.tiles = cell.tiles + 1
    if amount then
      cell.amount = cell.amount + amount
    end
    cell.sum_x, cell.sum_y = cell.sum_x + p.x, cell.sum_y + p.y
    cell.min_x, cell.min_y = math.min(cell.min_x, p.x), math.min(cell.min_y, p.y)
    cell.max_x, cell.max_y = math.max(cell.max_x, p.x), math.max(cell.max_y, p.y)
    local away = distance(here, p)
    if not cell.distance or away < cell.distance then
      cell.distance, cell.nearest = away, p
    end
  end

  for key, chunk in pairs(state().explored) do
    if surface.is_chunk_generated(chunk) then
      local area =
        { { chunk.x * CHUNK, chunk.y * CHUNK }, { (chunk.x + 1) * CHUNK, (chunk.y + 1) * CHUNK } }
      for _, entity in pairs(surface.find_entities_filtered({ area = area, type = "resource" })) do
        add(entity.name, key, chunk, entity.position, entity.amount)
      end
      for _, tile in
        pairs(surface.find_tiles_filtered({ area = area, collision_mask = "water_tile" }))
      do
        local centre = { x = tile.position.x + 0.5, y = tile.position.y + 0.5 }
        add("water", key, chunk, centre, nil)
      end
    end
  end

  local patches = {}
  for name, by_name in pairs(cells) do
    local seen = {}
    for key, start in pairs(by_name) do
      if not seen[key] then
        seen[key] = true
        local patch = fresh_extent(start.amount) -- water has no amount
        patch.name = name
        local keys = {}
        local stack = { start }
        while #stack > 0 do
          local cell = table.remove(stack)
          keys[#keys + 1] = cell.x .. "," .. cell.y
          patch.tiles = patch.tiles + cell.tiles
          if cell.amount then
            patch.amount = patch.amount + cell.amount
          end
          patch.sum_x, patch.sum_y = patch.sum_x + cell.sum_x, patch.sum_y + cell.sum_y
          patch.min_x, patch.min_y =
            math.min(patch.min_x, cell.min_x), math.min(patch.min_y, cell.min_y)
          patch.max_x, patch.max_y =
            math.max(patch.max_x, cell.max_x), math.max(patch.max_y, cell.max_y)
          if not patch.distance or cell.distance < patch.distance then
            patch.distance, patch.nearest = cell.distance, cell.nearest
          end
          for dx = -1, 1 do
            for dy = -1, 1 do
              local next_key = (cell.x + dx) .. "," .. (cell.y + dy)
              if by_name[next_key] and not seen[next_key] then
                seen[next_key] = true
                stack[#stack + 1] = by_name[next_key]
              end
            end
          end
        end
        patches[#patches + 1] = {
          name = name,
          tiles = patch.tiles,
          amount = patch.amount,
          nearest = point(patch.nearest),
          distance = round(patch.distance),
          center = point({ x = patch.sum_x / patch.tiles, y = patch.sum_y / patch.tiles }),
          area = {
            left_top = point({ x = patch.min_x, y = patch.min_y }),
            right_bottom = point({ x = patch.max_x, y = patch.max_y }),
          },
          keys = name == wanted and keys or nil,
        }
      end
    end
  end
  table.sort(patches, function(a, b)
    return a.distance < b.distance
  end)
  if wanted then
    local found = {}
    for _, patch in ipairs(patches) do
      if patch.name == wanted then
        found[#found + 1] = patch
      end
    end
    if #found == 0 then
      reject(
        "no " .. wanted .. " on the explored map; `fac map` lists what is, and walking reveals more"
      )
    end
    local tiles = {}
    for _, key in ipairs(found[1].keys) do
      for _, p in ipairs(wanted_tiles[key]) do
        tiles[#tiles + 1] = p
      end
    end
    found[1].rows = patch_rows(tiles)
    for _, patch in ipairs(found) do
      patch.keys = nil
    end
    patches = found
  end
  return { position = point(here), patches = patches }
end

-- Job queries ----------------------------------------------------------------

local function find_job(params)
  local id = number_param(params, "id", nil, 1, math.huge)
  local job = state().jobs[id]
  if not job then
    reject("no job " .. id)
  end
  return job
end

local function job(params)
  return describe(find_job(params))
end

local function jobs()
  return { running = running_jobs() }
end

local function cancel(params)
  local character = body()
  local found = find_job(params)
  if found.state ~= "running" then
    reject(string.format("job %d is already %s", found.id, found.state))
  end
  if found.kind == "craft" then
    reject("crafts can't be cancelled")
  end
  release_body(character, "cancelled by the agent")
  return describe(found)
end

-- HUD ------------------------------------------------------------------------

-- Remember the tick research last moved: a new technology or more progress.
local function watch_research(s, force)
  local current = force.current_research
  local name = current and current.name or nil
  local progress = current and force.research_progress or 0
  local seen = s.research_seen
  if not seen or seen.name ~= name or seen.progress ~= progress then
    s.research_seen = { name = name, progress = progress, tick = game.tick }
  end
end -- The rest of the HUD lives in its own function, whose locals do not count -- against the chunk's limit of 200.
(function()
  -- How long research may stand still, or the agent stay silent, before the
  -- HUD says so, and how few free inventory slots it warns at.
  local RESEARCH_STALL_TICKS = 2 * 60 * 60
  local REPEAT_TICKS = 20 * 60 -- a warning that still holds is repeated this often
  local SILENCE_TICKS = 3 * 60 * 60
  local FEW_FREE_SLOTS = 8
  local HUD_RADIUS = 32 -- how far the HUD looks for poles and warning icons

  -- Electric networks with poles in view that get less power than they ask
  -- for, each as { key, text }: the key names the network and how it is
  -- short, so a demand that moves does not make the warning new.
  local function short_networks(character)
    local short = {}
    local seen = {}
    local poles = character.surface.find_entities_filtered({
      type = "electric-pole",
      force = character.force,
      position = character.position,
      radius = HUD_RADIUS,
    })
    for _, pole in ipairs(poles) do
      local id = pole.electric_network_id
      if id and not seen[id] then
        seen[id] = true
        local power = network_power(pole)
        if power and power.satisfaction and power.capacity_kw <= 0 then
          short[#short + 1] = {
            "no power " .. id,
            string.format(
              "no power on the network of the pole at %s, %s: its machines ask for %d kW and no "
                .. "generator on it runs (its poles don't join your generators, or the boilers "
                .. "have no fuel or water)",
              pole.position.x,
              pole.position.y,
              power.demand_kw
            ),
          }
        elseif power and power.satisfaction and power.satisfaction < 0.995 then
          short[#short + 1] = {
            "low power " .. id,
            string.format(
              "low power on the network of the pole at %s, %s: its machines ask for %d kW and its "
                .. "generators give %d kW, so everything on it runs at %d%%",
              pole.position.x,
              pole.position.y,
              power.demand_kw,
              power.capacity_kw,
              math.floor(power.satisfaction * 100)
            ),
          }
        end
      end
    end
    return short
  end

  -- What a player's screen always shows, sent with every answer to an agent
  -- method (decision 75): the game clock, free inventory slots and the research
  -- bar, plus `warnings` for what a player could not miss: game time that
  -- passed since the last command, an inventory about to fill, research standing
  -- still, too little power on a network in view, and the warning icons over
  -- machines in view.
  --
  -- With `defer` (the start of `fac ... --wait`, whose answer is not printed)
  -- nothing is said yet: the warnings this call would give wait in
  -- `hud_pending`, and the next HUD, the one `--wait` prints, says them first.
  -- The silence warning lives on that way, since this call resets its clock.
  function M.hud(defer)
    local s = storage.agent
    local character = s and s.character
    if not (character and character.valid) then
      return nil
    end
    local tick = game.tick
    -- Each warning is { key, text }. The key names the condition, not its
    -- numbers, so a warning whose count or minutes change is still the one
    -- already said (decision 82).
    local warnings = {}

    local silent = s.last_call_tick and tick - s.last_call_tick or 0
    s.last_call_tick = tick
    if silent >= SILENCE_TICKS then
      warnings[#warnings + 1] = {
        "silence",
        string.format(
          "%d minutes of game time passed since your last command: the factory ran on its own, "
            .. "so check research, power and fuel before you carry on",
          math.floor(silent / 3600)
        ),
      }
    end

    local inventory = character.get_main_inventory()
    local free = inventory.count_empty_stacks()
    if free <= FEW_FREE_SLOTS then
      warnings[#warnings + 1] = {
        "free slots",
        string.format(
          "only %d of %d inventory slots are free: a take that does not fit fails, so put what "
            .. "you do not need into a chest",
          free,
          #inventory
        ),
      }
    end

    local belt = character.surface.find_entities_filtered({
      position = character.position,
      type = { "transport-belt", "underground-belt", "splitter" },
      limit = 1,
    })[1]
    if belt then
      warnings[#warnings + 1] = {
        "on a belt",
        string.format(
          "you are standing on a %s: it carries you along, so step off before you build or reach "
            .. "for anything",
          belt.name
        ),
      }
    end

    local force = character.force
    local current = force.current_research
    local has_lab = character.surface.count_entities_filtered({
      type = "lab",
      force = force,
      limit = 1,
    }) > 0
    local research = "none"
    if current then
      research = string.format("%s %d%%", current.name, math.floor(force.research_progress * 100))
      local seen = s.research_seen
      local still = seen and seen.name == current.name and tick - seen.tick or 0
      if has_lab and still >= RESEARCH_STALL_TICKS then
        warnings[#warnings + 1] = {
          "research stalled",
          string.format(
            "research has not moved for %d minutes: the labs lack science packs or power",
            math.floor(still / 3600)
          ),
        }
      end
    elseif has_lab then
      warnings[#warnings + 1] = { "research idle", "no research is queued: the labs are idle" }
    end

    for _, warning in ipairs(short_networks(character)) do
      warnings[#warnings + 1] = warning
    end
    local icons, icon_key = icons_in_view(character, HUD_RADIUS)
    if icons then
      warnings[#warnings + 1] = { icon_key, icons }
    end

    -- A warning given in the last REPEAT_TICKS is not said again while it
    -- still holds, so a script of fifty commands reads it once, not fifty
    -- times; `warnings_still_true` counts the ones held back.
    local shown = s.hud_shown or {}
    local pending = s.hud_pending or {}
    local owed = {}
    for _, warning in ipairs(pending) do
      owed[warning[1]] = true
    end
    if defer then
      for _, warning in ipairs(warnings) do
        local last = shown[warning[1]]
        if not owed[warning[1]] and not (last and tick - last < REPEAT_TICKS) then
          pending[#pending + 1] = warning
        end
      end
      s.hud_pending = pending
      return nil
    end
    s.hud_pending = nil
    local now_shown, fresh, held_back = {}, {}, 0
    for _, warning in ipairs(pending) do
      fresh[#fresh + 1] = warning[2]
    end
    for _, warning in ipairs(warnings) do
      local key, text = warning[1], warning[2]
      local last = shown[key]
      if owed[key] then
        now_shown[key] = tick -- said above, as the deferred call found it
      elseif last and tick - last < REPEAT_TICKS then
        now_shown[key] = last
        held_back = held_back + 1
      else
        now_shown[key] = tick
        fresh[#fresh + 1] = text
      end
    end
    s.hud_shown = now_shown

    local seconds = math.floor(tick / 60)
    return {
      time = string.format(
        "%d:%02d:%02d",
        math.floor(seconds / 3600),
        math.floor(seconds / 60) % 60,
        seconds % 60
      ),
      free_slots = free,
      research = research,
      warnings = #fresh > 0 and fresh or nil,
      warnings_still_true = held_back > 0 and held_back or nil,
    }
  end
end)()

-- Every tick: steer the walk, watch the mining, count finished crafts, and
-- chart around the body. Every second: note whether research moved.
function M.on_tick()
  local s = storage.agent
  local character = s and s.character
  if not (character and character.valid) then
    return
  end
  local current = s.body_job and s.jobs[s.body_job]
  if current and current.state == "running" then
    if current.kind == "walk" then
      step_walk(character, current)
    elseif current.kind == "place_line" then
      step_line(character, current)
    else
      step_mine(character, current)
    end
  end
  count_completed_crafts(character)
  step_crafts()
  chart_around(character)
  if game.tick % 60 == 0 then
    watch_research(s, character.force)
  end
end

-- Agent methods, called with the params table (empty when the call had none).
M.methods = {
  observe = observe,
  inventory = inventory,
  stats = stats,
  map = map,
  walk = walk,
  mine = mine,
  craft = craft,
  job = job,
  jobs = jobs,
  cancel = cancel,
  place = place,
  place_line = place_line,
  insert = insert,
  take = take,
  rotate = rotate,
  inspect = inspect,
  set_recipe = set_recipe,
  research = research,
  launch = launch,
}

return M

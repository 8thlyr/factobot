-- Science milestones the harness scores from (decision 18), observed in the
-- game rather than reported by the agent.
--
-- A tier's clock stops when labs first research with that tier's pack made
-- by a machine. Packs carry no record of where they were made, so the mod
-- counts the packs the agent hand-crafts (agent.lua credits each finished
-- craft), takes machine-made packs as the force's production statistics
-- minus those, and stops the clock on the first tick labs have used up more
-- packs than were ever hand-crafted: one of the packs used was then
-- machine-made. Hand-crafted packs alone can never stop it, however many
-- labs use. It also keeps, per game minute, how many packs machines had made
-- so far, so the harness can check sustained throughput afterwards.

local M = {}

local TICKS_PER_MINUTE = 3600

-- The science packs, in the order the base game's lab lists them.
---@return string[]
local function packs()
  local names, seen = {}, {}
  for _, lab in pairs(prototypes.get_entity_filtered({ { filter = "type", type = "lab" } })) do
    for _, name in ipairs(lab.lab_inputs or {}) do
      if not seen[name] then
        seen[name] = true
        names[#names + 1] = name
      end
    end
  end
  return names
end

local function statistics()
  return game.forces["player"].get_item_production_statistics(game.surfaces[1])
end

-- `hand` counts packs made by hand per pack, `first_automated` holds the
-- tick per pack, and `by_minute` the cumulative machine-made count per pack
-- at the end of each game minute. `rocket_launched` is the tick of the
-- first rocket launch; saves from before 0.5.0 don't have it, which is
-- right, since no agent could launch a rocket before then.
local function fresh(hand)
  local by_minute = {}
  for _, name in ipairs(packs()) do
    by_minute[name] = {}
  end
  return { hand = hand or {}, first_automated = {}, by_minute = by_minute }
end

local function state()
  storage.milestones = storage.milestones or fresh()
  return storage.milestones
end

-- Called when a map is created.
function M.init()
  storage.milestones = fresh()
end

-- A save from before 0.4.0 kept no count of hand-crafted packs, so every
-- pack it had made counts as made by hand: only packs machines make from
-- now on can stop the clock, and machines count as having made none in the
-- minutes already played.
function M.migrate()
  if storage.milestones then
    return
  end
  local made = statistics()
  local hand = {}
  for _, name in ipairs(packs()) do
    hand[name] = made.get_input_count(name)
  end
  storage.milestones = fresh(hand)
  -- Between ticks game.tick names the next tick, so the minutes on_tick has
  -- already closed are those ending before it.
  for _, series in pairs(storage.milestones.by_minute) do
    for minute = 1, math.floor((game.tick - 1) / TICKS_PER_MINUTE) do
      series[minute] = 0
    end
  end
end

-- agent.lua calls this for every item a finished hand-craft makes.
function M.hand_crafted(name, count)
  local s = state()
  if s.by_minute[name] then
    s.hand[name] = (s.hand[name] or 0) + count
  end
end

-- Runs at the start of each tick, before agent.lua credits the crafts that
-- finished on the tick before. The statistics then show everything made and
-- used up to the end of the previous tick, and `hand` counts the hand-crafts
-- credited to them. A `craft` call between ticks credits finished crafts at
-- once, before the statistics show them; that can only make `hand` run
-- ahead, which delays the clock rather than stopping it early, and leaves a
-- minute's machine-made count low by those packs until the next minute.
function M.on_tick(event)
  local s = state()
  local made = statistics()
  local previous = event.tick - 1
  for name, series in pairs(s.by_minute) do
    if not s.first_automated[name] and made.get_output_count(name) > (s.hand[name] or 0) then
      s.first_automated[name] = previous
    end
    if event.tick % TICKS_PER_MINUTE == 0 and event.tick > 0 then
      series[#series + 1] = made.get_input_count(name) - (s.hand[name] or 0)
    end
  end
end

-- The game counts a rocket as launched when it reaches space, about 19 s
-- after the launch order, which is when on_rocket_launched fires (probed).
-- Only the first one counts.
function M.on_rocket_launched(event)
  local s = state()
  s.rocket_launched = s.rocket_launched or event.tick
end

-- For the harness (dev socket only): per pack, how many were made by hand
-- and by machines, how many labs used, the tick labs first researched with
-- a machine-made one, and machine-made packs so far at the end of each game
-- minute; and the tick of the first rocket launch.
function M.report()
  local s = state()
  local made = statistics()
  local result = {}
  for _, name in ipairs(packs()) do
    local hand = s.hand[name] or 0
    result[#result + 1] = {
      name = name,
      made_by_hand = hand,
      made_by_machine = made.get_input_count(name) - hand,
      used_by_labs = made.get_output_count(name),
      first_automated_research = s.first_automated[name],
      machine_made_by_minute = s.by_minute[name] or {},
    }
  end
  -- Lua can't write a JSON null; the daemon adds rocket_launched_tick: null
  -- while there is none.
  return { tick = game.tick, packs = result, rocket_launched_tick = s.rocket_launched }
end

return M

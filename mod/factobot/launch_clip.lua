-- Films the first rocket launch for the timelapse (decision 95). The 30 s
-- timelapse frames miss the flight: the rocket stands in the silo for about
-- 14 s after the launch order and is out of sight by 17 s, while the game
-- counts the launch (on_rocket_launched) at about 19 s. So from the launch
-- order until the rocket has left the picture, the camera client renders the
-- silo every few ticks, on the mod's own ticks so the spacing is exact.
--
-- The runner arms it by setting `storage.launch_clip` (timelapse.py's
-- LAUNCH_ARM_LUA says what it holds) and reads back `shots`: per shot the
-- tick and, while the silo holds one, the rocket's y. Taking a screenshot
-- changes nothing in the world. Any error stops the filming and is kept in
-- `error`, so the clip can never stop the game.

local M = {}

-- How far below its position the rocket's flame reaches, in tiles, so the
-- filming goes on until the flame has left the picture too.
local FLAME_TILES = 8

local function shoot(clip, tick)
  local silo = clip.silo
  if not silo.valid then
    clip.done = true
    return
  end
  local rocket = silo.rocket
  local rocket_y = rocket and rocket.valid and rocket.position.y or nil
  local top = clip.center.y - clip.height / (2 * 32 * clip.zoom)
  local rising = rocket_y ~= nil and rocket_y < clip.silo_position.y
  clip.rose = clip.rose or rising
  if (clip.rose and rocket_y == nil) or (rocket_y and rocket_y + FLAME_TILES < top) then
    clip.done = true
    return
  end
  local camera = game.get_player(clip.player)
  -- A camera that has gone misses shots; the runner keeps what it has.
  if camera and camera.connected then
    local shot = { tick = tick, rocket_y = rocket_y }
    clip.shots[#clip.shots + 1] = shot
    game.take_screenshot({
      player = camera,
      by_player = camera,
      surface = silo.surface,
      position = clip.center,
      resolution = { clip.width, clip.height },
      zoom = clip.zoom,
      path = string.format("%sshot-%05d.jpg", clip.path, #clip.shots),
      quality = clip.quality,
      show_gui = false,
      show_entity_info = true,
      daytime = 0,
      -- Renders every shot, however far behind the camera falls.
      force_render = true,
    })
  end
  clip.next = tick + (rising and clip.flying_every or clip.every)
end

local function step(clip, tick)
  if tick - clip.started > clip.limit then
    clip.done = true
    return
  end
  local ok, err = pcall(shoot, clip, tick)
  if not ok then
    clip.done = true
    clip.error = tostring(err)
  end
end

-- The first launch order after arming starts the filming.
function M.on_launch_ordered(event)
  local clip = storage.launch_clip
  if not clip or clip.started or not (event.rocket_silo and event.rocket_silo.valid) then
    return
  end
  local position = event.rocket_silo.position
  clip.silo = event.rocket_silo
  clip.silo_position = { x = position.x, y = position.y }
  clip.center = { x = position.x, y = position.y - clip.lift }
  clip.started = event.tick
  step(clip, event.tick)
end

function M.on_tick(event)
  local clip = storage.launch_clip
  if clip and clip.started and not clip.done and event.tick >= clip.next then
    step(clip, event.tick)
  end
end

return M

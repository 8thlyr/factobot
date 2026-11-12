-- Red science is unlocked and the agent carries a steam power setup, a lab,
-- fuel and science packs, so the playtest covers power and research only.
local force = game.forces.player
for _, name in pairs({ "electronics", "steam-power", "automation-science-pack" }) do
  force.technologies[name].researched = true
end
local character = storage.agent.character
for name, count in pairs({
  ["offshore-pump"] = 1,
  boiler = 1,
  ["steam-engine"] = 1,
  ["small-electric-pole"] = 10,
  lab = 1,
  coal = 50,
  ["automation-science-pack"] = 10,
}) do
  character.insert({ name = name, count = count })
end

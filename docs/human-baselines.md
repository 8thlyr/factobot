# factobot: human reference times per science tier

Research date: 2026-11-01. All sources were fetched on that date unless a row says otherwise. Hours are in-game or played hours on one save, counted from a fresh start. `[INFERENCE]` marks anything I derived or judged that no source states directly.

## TL;DR: recommended reference values ("average human" = score 1.00)

| Tier milestone (first automated production feeding labs) | Fraction of rocket time | **Cumulative h** | **Gap from previous tier, h** | Confidence |
|---|---|---|---|---|
| Red / automation | 0.10 | **5** | 5 (from fresh start) | low–medium |
| Green / logistic | 0.24 | **12** | 7 | low |
| Blue / chemical | 0.50 | **25** | 13 | medium |
| Purple / production | 0.80 | **40** | 15 | low–medium |
| Yellow / utility | 0.84 | **42** | 2 | low |
| Rocket launch | 1.00 | **50** | 8 | medium |

**Method.** Total = HowLongToBeat (HLTB) Factorio "Main Story" **median, 50h** (n=286). Each tier's fraction is the **median over 7 timed runs** listed in §3: 5 speedrun LiveSplit splits from runs on default map settings plus 2 blind first playthroughs. A tier's hours are the fraction × 50h `[INFERENCE: method]`. The fractions stay quite stable across skill levels. Experts and blind first-timers both reach blue at about 50% of their own rocket time and purple/yellow at about 80–85%. That stability is the main reason to scale a reliable total by a skill-independent profile.

**Military / grey:** this tier is **not on the rocket path**. I computed the prerequisite closure of `rocket-silo` from the 2.1.24 base data, and it contains no military packs (§3c, §4). Wube noted in 0.17 planning that players obtain military science first "except in peaceful mode" ([FFF #275](https://factorio.com/blog/post/fff-275), fetched). In a peaceful benchmark it doesn't matter, so leave it out of scoring.

**Purple and yellow are parallel tiers, not sequential.** In the tech tree, `utility-science-pack` does not require production packs (§3c: its closure has no production packs). Speedrunners build both in one "mixed" or "Yellow & Purple" step. The 2h purple→yellow gap is therefore fragile. I recommend one staged-ladder stage, "blue automated → purple + yellow automated", with a 17h gap (25h→42h) `[INFERENCE]`.

**What a score means at these anchors:** the 2.x Default Settings world record of 1:59:01 would score 50/1.98 ≈ **25** on the full run `[INFERENCE: arithmetic]`. The HLTB "Rushed" main-story time of 30h42m would score ≈ 1.6.

---

## 1. Total time to first rocket

### 1a. HowLongToBeat
Real game page: https://howlongtobeat.com/game/17455. I found the id via a [Hacker News thread](https://news.ycombinator.com/item?id=22342501) (search summary). My first guess, `/game/31954`, turned out to be an unrelated entry called "f u". Page fetched 2026-11-01; it showed "Updated: 1.5 Hours Ago". Release date on the page: 2020-08-14, which is the 1.0 date.

| Single-player | Polled | Average | Median | Rushed | Leisure |
|---|---|---|---|---|---|
| Main Story | **286** | **56h 49m** | **50h** | **30h 42m** | **128h 30m** |
| Main + Sides | 118 | 102h 1m | 82h 24m | 61h 6m | 281h 41m |
| Completionist | 47 | 249h 52m | 204h 30m | 157h 5m | 462h 20m |
| All PlayStyles | 451 | 88h 46m | 62h 2m | 41h 42m | 386h 27m |

- Headline numbers: Main Story 53½h, Main+Sides 92h, Completionist 227h. The page also shows 1.8K "Beat" and 8.4% "Retired".
- PC only: Main 56h 45m (n=444 across all categories). Switch: Main 60h 14m (n=6).
- Speedruns (Any%): n=11, average 9h 10m, median 6h 2m, fastest 1h 45m 56s.
- Co-op: n=36, average 90h, median 62h.
- Space Age (DLC row on the same page): n=42, Main 138h. This is a different victory condition, so it is not used here.
- **Version caveat:** HLTB doesn't split by game version, so this pool mixes 1.x and 2.x submissions. A 2018 forum post cites HLTB at "42 hour 29 mins average time for the main story", which is the 0.16 era ([forums t=62732](https://forums.factorio.com/viewtopic.php?t=62732)). The average has risen since then, either because of game changes or because the submitting population changed `[INFERENCE]`.
- **Meaning of "Main Story":** the game has no story, and players treat the first rocket launch, i.e. the victory screen, as "beating" it. One forum reply says 42h "definetly looks like 'average time to first rocket launched', because that's when you get the 'Victory [continue?]' dialog" ([same thread](https://forums.factorio.com/viewtopic.php?t=62732)).
- **Selection bias:** HLTB submitters are engaged loggers. People who quit before the rocket are excluded, which matches the task's definition ("not first-time-quitter").

### 1b. Steam global achievements (official API)
Sources: API https://api.steampowered.com/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/?gameid=427520 for percentages. API-name → display-name mapping comes from the JSON embedded in https://steamcommunity.com/stats/427520/achievements?l=english. The community page lists 88 achievements: 59 base game, 29 DLC. Percentages are of Steam owners. Steam provides no playtime-at-unlock data.

| API name | Display name / condition | % |
|---|---|---|
| `smoke-me-a-kipper-i-will-be-back-for-breakfast` | Launch a rocket to space | **24.1** |
| `no-time-for-chitchat` | Launch a rocket within 15 hours | **5.0** |
| `there-is-no-spoon` | Launch a rocket within 8 hours | **3.2** |
| `lazy-bastard` | Launch a rocket while hand-crafting ≤111 items | 3.8 |
| `steam-power` | Produce power by steam engine | 43.4 (page: 43.5) |
| `research-with-automation` | Research using red packs | **42.1** (page 42.2) |
| `research-with-logistics` | ... green | **36.0** (page 36.1) |
| `research-with-chemicals` | ... blue | **25.0** |
| `research-with-military` | ... grey | 25.6 |
| `research-with-production` | ... purple | **17.3** |
| `research-with-utility` | ... yellow | **15.8** |
| `research-with-space` | ... white | 11.8 |
| `eco-unfriendly` | Research oil processing | 60.2 |
| `reach-for-the-stars` (Space Age) | Create a space platform | 44.3 |
| `second-star-to-the-right-and-straight-on-till-morning` (SA) | Finish the game (SA) | 9.0 |
| `work-around-the-clock` (SA) | Finish within 100 hours | 2.8 |
| `express-delivery` (SA) | Finish within 40 hours | 1.9 |

How to read it:
- The `research-with-*` and `steam-power` achievements were **added in 2.0.7**: "2.0.7 : Added new achievements" ([wiki Achievements history](https://wiki.factorio.com/Achievements)). Their percentages only count players active since October 2024. That explains why `research-with-automation` (42.1%) is lower than the older `eco-unfriendly` (60.2%). `smoke-me-a-kipper` dates from 1.x and so mixes eras.
- **2.x tier funnel** (relative to red = 100%): green 86%, blue 59%, purple 41%, yellow 38%, space 28% `[INFERENCE: ratios of the API values]`. The biggest drop-off comes at blue, which fits the forum observation that "somewhere between oil and bots 50% of players drop out" ([forums t=48062](https://forums.factorio.com/viewtopic.php?t=48062), 2017).
- In 2018 Wube said "only about 11% of players on Steam have ever launched a rocket" ([FFF #245](https://www.factorio.com/blog/post/fff-245)). The figure is now 24.1%.
- 5.0/24.1 ≈ 21% of rocket achievers have, on some save, launched within 15h, and 3.2/24.1 ≈ 13% within 8h `[INFERENCE]`. These are mostly repeat runs by experienced players. They show the right tail of skill, not first-run times.
- The DLC achievement percentages appear to use DLC owners as the denominator. `reach-for-the-stars` (44.3%) is higher than `research-with-automation` (42.1%), which would be impossible over the same population `[INFERENCE]`.
- **Peaceful caveat:** setting enemies below default disables the speed achievements (There is no spoon, No time for chitchat, Work around the clock, Express delivery, ...) ([wiki](https://wiki.factorio.com/Achievements)). Those percentages therefore come from **non-peaceful** runs only.

### 1c. Achievement trackers (playtime at unlock)
None of the trackers I could reach expose playtime at unlock for the rocket achievement.
- **TrueSteamAchievements** https://truesteamachievements.com/game/Factorio/achievements fetched OK. It shows 14,333 TSA gamers and an estimate of "200+h" to unlock all base achievements. The rocket achievement page https://truesteamachievements.com/a155763/smoke-me-a-kipper-ill-be-back-for-breakfast-achievement has no time-to-unlock data. Its achievement IDs separate 1.x (a1557xx) from 2.0 additions (a2976xxx).
- **Steamhunters**: the HTML page returned 403 (Cloudflare). The JSON API https://steamhunters.com/api/apps/427520 and `/achievements` fetched OK. They give `playersStartedCount` 20,045, `medianCompletionTime` 53,061 (100% completion; unit not documented, so not used) and per-achievement `steamPercentage`/`localPercentage`, but **no time-to-unlock per achievement**.
- **completionist.me**: 403 (Cloudflare) through the reader, through curl with a browser UA, and through headless Chromium, where it stuck on the "Performing security verification" page. The relay browser was unavailable (extension not connected) and a headed browser failed to launch.
- **astats**: `astats.astats.nl` ECONNREFUSED; `astats.nl` and `www.astats.nl` returned 404.

### 1d. First-run anecdotes (primary posts, small n, self-reported)
From [Steam "average game length" thread, Jul 2022](https://steamcommunity.com/app/427520/discussions/0/3473981814933977822/): "The first time I launched a rocket it was around 45 hours ... about 44 hours" on the next run. Others report "First Rocket took my over 100h", "my first was 450 hours or so", and "it took 40 hours, but it was not my first playthrough". One estimate: "60 to 120 hours to launch the first rocket for a complete beginner". From [forums t=62732, 2018](https://forums.factorio.com/viewtopic.php?t=62732): "My first factory ... took 142 hours to launch the first rocket", and "40+ hours to launch your first rocket ... seems reasonable to me".

---

## 2. Candidate reference times (all sources)

Cumulative hours from a fresh start. For a single-run source, the gap is computed against that same run's previous milestone.

| # | Source (URL) | n | Date | Red | Green | Blue | Purple | Yellow | Rocket | Confidence |
|---|---|---|---|---|---|---|---|---|---|---|
| A | HLTB Main Story **median** https://howlongtobeat.com/game/17455 | 286 | fetched 2026-11-01 | – | – | – | – | – | **50.0** | medium |
| B | HLTB Main Story **average** (same) | 286 | same | – | – | – | – | – | 56.8 | medium (pulled up by the right tail) |
| C | HLTB Main Story **rushed** (same) | 286 | same | – | – | – | – | – | 30.7 | medium (a faster-than-average player) |
| D | HLTB 2018 snapshot, quoted at https://forums.factorio.com/viewtopic.php?t=62732 | not stated | 2018-09 | – | – | – | – | – | 42.5 | low (0.16 era) |
| E | Thomas Edward, blind, 1.1 era `[INFERENCE: dated Nov 2023–Mar 2024]` https://www.youtube.com/playlist?list=PLplUucL_enWKvQ7FWeOEfkuBO-DCjlGAz | 1 | 2023-11→2024-03 | ≤6.1 | **6.1** | 34.2–37.3 | 52.3–54.7 | ≤68.2 | **68.2** | low (n=1) |
| F | ItFightsBack, blind, 1.1.5 https://www.youtube.com/playlist?list=PLJsyEXovA6jzr0JpJAr-3MDJdZvg-rBqE | 1 | 2022-01→02 | ~2.75 | 3.2–6.5 | 8.9–12.8 | 19.5–21.4 | 19.5–21.4 | **24.1** | low (n=1; coarse) |
| G | Ocktavo, blind, no commentary, 2.x https://www.youtube.com/playlist?list=PL6W9HgDHyYk9cKVl9X6r_r21ZZxJAZJ00 | 1 | 2025-09→2026-06 | – | – | – | – | – | **≈95.9** | low (rocket only) |
| H | Steam anecdotes (§1d) | ~6 | 2018–2022 | – | – | – | – | – | 40–142 (one at 450) | low |
| R | **Recommended** (§TL;DR) | – | – | **5** | **12** | **25** | **40** | **42** | **50** | see TL;DR |

Notes on the let's-play rows:
- **All values are video durations summed via `yt-dlp --flat-playlist`**, which stands in for played time. The longer episodes are full Twitch VODs, so pauses and chatting count too `[INFERENCE]`.
- **E (Thomas Edward):** the playlist starts with 6.22h of tutorial and campaign episodes before "Planetfall | EP 01". Hours shown are freeplay only.
  - Red+green milestone: "Automating Red and Green Science | EP 06" ends at 6.06h.
  - Blue: "Let's Automate Chemical Science | EP 30" spans 34.24–37.33h.
  - Purple: "Automating Production Science Packs | EP 38" spans 52.34–54.70h.
  - Yellow: no episode title names it.
  - Rocket: "Final Episode | Rocket Launch! | EP 43" ends at 68.16h. Chapters include "Rocket launch and finale" (https://www.youtube.com/watch?v=zATHNNrN46o).
  - Biters were on: EP 01 has a "Clearing the native nest" chapter.
- **F (ItFightsBack):** times come from YouTube chapter markers and episode descriptions.
  - Red: Ep 2 chapter "Red research" at 53 min, i.e. 2.75h (https://www.youtube.com/watch?v=Bn880tHdpug).
  - Green: Ep 3 says "I maximize my research production" and Ep 4 says "finally complete the next research production project". So green falls in 3.2–6.5h `[INFERENCE]`.
  - Blue: Ep 6 says "lay the groundwork for the next step of research production" (ends 8.92h), and Ep 9 has a "Preparing for purple science" chapter at 12.8h. So blue falls in 8.9–12.8h `[INFERENCE]`.
  - Purple + yellow: Ep 13 says "I complete the final research materials and begin researching the rocket silo" (19.45–21.4h).
  - Rocket: "Mission Accomplished ... Ep 14" ends at 24.05h.
  - Biters were on.
- **G (Ocktavo):** 37 episodes total 95.9h. I pulled the last frame of the "FINAL EPISODE" (https://www.youtube.com/watch?v=Rsy1Pwu8Wr0, t≈3900s). It shows the 2.x rocket-silo GUI with rocket progress full, so the rocket launches in that episode. Episode titles carry no tier information.
- **Rejected candidates:**
  - CarlPlayin42: Deathworld settings.
  - Duke_Euphoria: the playlist has duplicate entries.
  - DunkOrSlam: 84.3h with no rocket visible. The final frame shows "Logistic system" research.
  - CohhCarnage 2024: Space Age.
  - PolarBear0084: incomplete at 44.6h.
  - ECXL: Space Age, after 300+h of earlier play.
  - Michael Hendriks / Gentlemad: Space Age.

---

## 3. Per-tier proportion profile

### 3a. Expert splits (speedrun.com, Default Settings = random seed, default enemies, no imported blueprints)
Leaderboards from the API https://www.speedrun.com/api/v1/leaderboards/9d35xw1l/category/7dg85xp2 (var `p85yzj0l` = `14o74req` for 2.x, `lx5edm31` for 1.x). speedrun.com stores no splits (`splits: null` on every run). I read the LiveSplit overlays off frames extracted from each run's VOD with `yt-dlp --download-sections` and ffmpeg. Each fraction is relative to that run's own LiveSplit final time.

| Runner, version, official time | VOD frame(s) | Red | Green (mass labs) | Blue | Purple | Yellow | Silo researched | Final (LiveSplit) |
|---|---|---|---|---|---|---|---|---|
| **Zaspar**, 2.x, **1:59:01** WR, 2026-08-22 | https://www.youtube.com/watch?v=2PwyPjjoOJo&t=7225 | – | "Labs" 32:57 (0.272) | "Blue science" 1:01:35 (0.508) | "Mixed" 1:26:11 (0.711) = start of purple/yellow inputs | – | – | "Win" 2:01:17 |
| **Nefrums**, 1.1, 2:19:12 (1.x WR) | https://www.youtube.com/watch?v=RI4ocNajf_w&t=2400, &t=3500, &t=8360 | "Red science" 14:12 (0.102) | "Labs" 32:51 (0.236) | "Chemical science" 58:13 (0.418) | "Production science" 1:52:21 (0.807) | "Utility science" 1:54:54 (0.825) | 2:15:48 (0.976) | 2:19:12 |
| **JeHor**, 2.0, 2:46:36 | https://www.youtube.com/watch?v=IUK7OLl8TDc&t=2400, &t=4800, &t=7200, &t=10005; also https://www.speedrun.com/static/blob/xz0dm08e.png | – | "Red/Green Science" 48:18 (0.290) | "Blue Science (15)" 1:26:57 (0.522) | "Advanced science" 2:22:35 (0.856) `[INFERENCE: = purple+yellow]` | same | 2:44:01 (0.984) | 2:46:36 |
| **Krul87**, 2.0, 2:41:56 | https://www.youtube.com/watch?v=oaAw8nC3k5g&t=3000, &t=6000, &t=9940 | "Mini science" 16:09 (0.100) | "Mall + science" 39:31 (0.244) | (not split) | "Yellow & Purple science" 2:13:47 (0.826) | same | 2:35:37 (0.961) | 2:41:54 |
| **seb351**, 2.0, 2:33:22 | https://www.youtube.com/watch?v=6cu7Z1MfG4o&t=9210 | "red science" 13:51 (0.090) | "Lab" 38:24 (0.250) | (split blank) | – | – | – | ≈2:33:21 |

Why the LiveSplit times differ from the official times: Zaspar's overlay reads 2:01:17, but his official time is 1:59:01. The rules start the timer "when the seed is first generated in the preview screen" ([Zaspar's guide](https://docs.google.com/presentation/d/12dO2YmmOUK_R528-jCKo2nSdJUKNkp-vvXWqDHS3PKo/export/txt)). In Zaspar's 2.x plan, "Labs" means red and green science assemblers feeding 32 labs, and "Mixed build" then "Purple science" then "Yellow science" are the later steps (same guide).

Other current records from the speedrun.com API:
- 2.x Default Settings top 8, 1:59:01 → 3:28:00: Zaspar 7141s, seb351 9202s, Krul87 9716s, JeHor 9996s, bttttta 10091s, Califerbopbop 10161s, ness056 10478s, DerekMacIntyre 12480s.
- 2.x Any%: JeHor 1:42:41 (6161s, 2025-01-06).
- 1.x Any%: Zaspar 1:18:56 (4736s).
- The version variable already lists 2.1.11, 2.1.12 and 2.1.18 runs.

The guide's stated beginner target: "Any Factorio player should be able to follow this guide, and with a little practice beat the game on a randomly selected default settings map in under 4 hours."

### 3b. Pooled profile: fraction of own rocket time
| Tier | Expert values | First-playthrough values (midpoint of range) | Pooled median → **used** |
|---|---|---|---|
| Red | 0.102, 0.100, 0.090 | F 0.114; E ≤0.089 | 0.100 → **0.10** |
| Green | 0.272, 0.236, 0.290, 0.244, 0.250 | E 0.089; F 0.196–0.271 (0.234) | 0.244 → **0.24** |
| Blue | 0.508, 0.418, 0.522 | E 0.502–0.548 (0.525); F 0.371–0.532 (0.45) | 0.508 → **0.50** |
| Purple | 0.807; P+Y combined 0.826, 0.856 | E 0.768–0.803 (0.785); F P+Y 0.809–0.890 (0.85) | 0.826 combined; separate-purple values 0.785/0.807 → **0.80** |
| Yellow | 0.825; P+Y 0.826, 0.856 | F P+Y (0.85) | 0.838 → **0.84** |
| Rocket | 1.0 | 1.0 | **1.00** |

All fractions above are `[INFERENCE]`: they are ratios computed from the cited timestamps.

### 3c. Science-cost check (tech tree, base 2.1.24)
Source: https://raw.githubusercontent.com/wube/factorio-data/master/base/prototypes/technology.lua (`base/info.json` version 2.1.24, commit acf5a34 of 2026-10-27). I loaded it in Lua 5.4 and summed the prerequisite closure of each pack-unlock technology. "Lab-h" is count × time at one speed-1 lab.

| Gate tech | Techs in closure | Cumulative packs (r/g/b/p/y) | Pack-units | Lab-h | Incremental lab-h |
|---|---|---|---|---|---|
| `automation-science-pack` | 3 (all triggers: craft iron plate, copper plate, lab) | 0 | 0 | 0 | 0 |
| `logistic-science-pack` (75 red × 5s) | 4 | 75/0/0/0/0 | 75 | 0.10 | 0.10 |
| `chemical-science-pack` (75 r+g × 10s) | 15 | 1050/915/0/0/0 | 1,965 | 5.78 | 5.68 |
| `production-science-pack` (100 r+g+b × 30s) | 23 | 1920/1765/350/0/0 | 4,035 | 12.95 | 7.17 |
| `utility-science-pack` (100 r+g+b × 30s) | 24 | 2225/2090/950/0/0 | 5,265 | 16.83 | 3.88 vs purple gate; 10.42 vs union |
| `rocket-silo` (1000 × r+g+b+p+y × 60s) | 44 | 5960/5785/3350/1600/1000 | 17,695 | 62.34 | 45.51 |

- 1.1.110 for comparison (https://raw.githubusercontent.com/wube/factorio-data/1.1.110/base/prototypes/technology.lua): the rocket-silo closure is 17,865 pack-units and 61.83 lab-h. **The mandatory tech cost is essentially unchanged between 1.1 and 2.x** `[INFERENCE]`.
- The rocket needs 100 rocket parts in both versions. In 2.x a part is 10 processing units + 10 LDS + 10 rocket fuel; in 1.1 it was 10 rocket control units + 10 LDS + 10 rocket fuel (`base/prototypes/recipe.lua`; `rocket_parts_required = 100` in `entities.lua`, both versions).
- Pack counts alone don't predict human time. 64% of the mandatory lab-hours sit after the purple/yellow gate, yet experts and novices both spend only about 16–20% of their time there. Human time is dominated by building the production chains, not by research throughput `[INFERENCE]`. That is why the profile comes from observed timings, not from science cost.

---

## 4. Military / grey
- The `rocket-silo` closure above has **no military-science-pack** in any prerequisite.
- Steam: `research-with-military` is 25.6% vs `research-with-chemicals` 25.0%, so most players do research it, mostly for defense `[INFERENCE]`.
- **Recommendation:** with peaceful mode, keep military unscored. If agents spend time on it, that time counts toward the next scored tier.

---

## 5. Version differences (1.x vs 2.x)
- HLTB: one mixed pool, no version split. The 2018 average was 42h29m; it is now 56h49m.
- Steam: the per-tier research achievements exist only from 2.0.7 on. The rocket achievement mixes eras.
- Tech cost to the silo is ~equal (17,865 vs 17,695 pack-units).
- The expert record improved from 2:19:12 (1.1 Default Settings) to 1:59:01 (2.x) on speedrun.com, the 2.x record set 2026-08-22. Expert proportions look the same across versions (Nefrums 1.1 vs the 2.x runs in §3a).
- The let's-play evidence is mostly 1.1 (E, F). Only G (2.x) covers 2.x, and only for total time.

---

## 6. Precedents for setting human reference times (method citations)
| Benchmark | How the human reference was set | Source (fetched) | Lesson for factobot |
|---|---|---|---|
| Atari / DQN (Mnih et al., Nature 2015) | One "professional human games tester". "The human performance is the average reward achieved from around 20 episodes of each game lasting a maximum of 5 min each, following around 2 h of practice playing each game." Normalized as "100 × (DQN score − random play score)/(human score − random play score)". | https://storage.googleapis.com/deepmind-media/dqn/DQNNaturePaper.pdf | The classic "human = 100%" anchor. It came from a small, practiced, non-expert sample, much like "average player". |
| SABER (Toromanoff et al., 2019) | Argues the DQN tester "baseline is far from being representative of the best human player". Proposes human world records instead. Rescaled under those records, the old human-normalized scores have "a median of 4.4k%". | https://arxiv.org/abs/1908.04683 (PDF text) | Publish **two anchors**: average human (=1.00) and the speedrun world record (the 1:59:01 DS 2.x WR scores ≈25 on our scale). Don't let a "superhuman" claim rest on the average anchor alone. |
| METR time horizons (Kwa et al., 2025) | "Using skilled human baseliners"; task time = "geometric mean time of successful human baselines". 286 successful baselines out of ~460 attempts for HCAST. | https://arxiv.org/abs/2503.14499 (PDF text) | Count only **successful** human runs (matches "not first-time quitter") and use geometric or median aggregation (we use the HLTB median). |
| VPT / Minecraft (Baker et al., 2022) | Milestone timing: diamond tools "can take proficient humans upwards of 20 minutes (24,000 environment actions) of gameplay". | https://arxiv.org/abs/2206.11795 (PDF text) | Direct precedent for a **time-to-milestone** human reference in a crafting/tech-tree game. |
| Factorio Learning Environment (Hopkins et al., 2025) | No formal human baseline. "Whilst the authors were, in equivalent game time, able to outperform frontier agents, it is unclear if achieving end-game goals (e.g. escape the world or build rockets) is achievable to humans using only an API in a reasonable time-frame." | https://arxiv.org/abs/2503.09617 (PDF text) | factobot would be first to set Factorio human references. Note the interface caveat: human times assume mouse and keyboard play, not API play. |

---

## 7. Main uncertainties
1. **Peaceful vs default enemies.** Every human source is a default-enemies game (HLTB unspecified; E and F show biters). Peaceful removes defense work, so it should make humans faster. HLTB submitters, meanwhile, skew engaged and partly experienced, which also pulls times down. I assume these roughly offset and apply **no adjustment** `[INFERENCE]`. Sensitivity: −10% gives rocket 45h, blue 22.5h.
2. **HLTB definition and sample.** "Main Story" is self-defined as the first rocket. n=286 across 2016–2026 and versions. Mean (56.8h) vs median (50h) shows a heavy right tail. Rushed (30.7h) and leisure (128.5h) give a plausible 30–130h band for "a human".
3. **Per-tier fractions rest on n=7 runs and only 2 non-expert ones.** Green is the weakest. Thomas Edward automated red and green together at 9% of his run, while experts' "mass labs" splits sit at 24–29%. Green could plausibly be 0.10–0.27 (5–13.5h).
4. **Milestone definition mismatch.** Speedrun splits mark "science connected to labs". Let's-play titles and descriptions mark episodes, so the resolution is ±1 episode (≈1–3h). Steam achievements mark the *first research* with a pack, which happens earlier than automation. The benchmark should define the milestone precisely (e.g. "first lab research using pack X where X came from an assembler") and stick to it.
5. **Video time ≠ in-game time.** Streams include breaks and chat. Edited videos cut downtime.
6. **Ladder stages vs single-run gaps.** A staged save that "already automates the tier below" hands the agent a working base. A human continuing their own run carries spaghetti and debt. Single-run gaps may overstate or understate the staged gap `[INFERENCE]`.
7. **Purple/yellow ordering.** They're parallel in the tech tree and built together by experts, so the 2h gap is unreliable. Score them as one combined stage, or require both.

## 8. Fetch log (failures and workarounds)
- HLTB `/game/31954`: wrong game ("f u"). The real id 17455 came from the HN thread search result.
- completionist.me: 403 via the reader and via curl with a Chrome UA. Headless Chromium hit the Cloudflare "Performing security verification" page. The relay browser was unavailable (extension not connected) and the headed browser failed to launch.
- steamhunters.com HTML: 403 (Cloudflare). Its `/api/apps/427520[/achievements]` JSON worked but has no unlock-time data.
- astats: `astats.astats.nl` ECONNREFUSED; `astats.nl` and `www.astats.nl` returned 404.
- Reddit: `www.reddit.com` and `old.reddit.com` search JSON returned 403; pullpush.io returned 522. No Reddit numbers are used. Reddit content appeared only in search summaries, which I didn't cite.
- therun.gg: Cloudflare challenge. splits.io API: dead (SPA 404 shell).
- speedrun.com: no splits stored. I used VOD frames instead (§3a). The ardoric "Factorio_Beginner_Splits.zip" linked from Zaspar's guide is a 2020 Any% template with segment names only, no times.
- FFF #275 fetched: https://factorio.com/blog/post/fff-275. The only claim used from it is the quote about military science and peaceful mode. "Military is optional for the rocket" rests on my own tech-tree computation (§3c).

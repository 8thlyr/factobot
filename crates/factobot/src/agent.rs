//! The agent's `fac`: the commands an agent plays with, and nothing of the
//! harness. The `fac-agent` binary is this CLI alone; the harness's `fac`
//! adds `daemon`, `watch` and `dev` to it.

use std::path::{Path, PathBuf};
use std::process::ExitCode;

use anyhow::Context as _;
use base64::Engine as _;
use clap::{Parser, Subcommand};
use serde::Serialize;
use serde_json::{Value, json};

use crate::{client, protocol};

/// The first line of `fac --help` in both binaries.
pub const ABOUT: &str = "Play Factorio from the command line. Every command prints one JSON object on stdout: `{\"ok\": true, \"result\": ...}` or `{\"ok\": false, \"error\": ...}`.";

/// How play works, for the long `fac --help` in both binaries: the harness's
/// `fac` is what Inspect agents run, so it needs this as much as `fac-agent`.
pub const GUIDANCE: &str = "The game runs in real time and does not wait for you. Positions are map tiles as X,Y: x grows to the east, y grows to the south. `walk`, `mine`, `craft` and `place --to` start a job and return at once; follow it with `fac job ID`, or pass `--wait` to block until it ends (default 60 seconds, up to 600; if the time runs out the job is still `running` and keeps going). `place`, `insert`, `take`, `rotate`, `recipe`, `research` and `launch` happen at once. `fac` exits non-zero when a command is refused and when the job it shows ended `failed` (a walk with no path, a mine with a full inventory); its `error` says why.\n\nEvery answer also has `hud`, what your screen always shows: `time` (the game clock), `free_slots` in your inventory, `research` (the current technology and its progress) and, when something is wrong, `warnings`: game time that passed while you gave no command, an inventory about to fill, research standing still, no power or too little on a network near you, machines in view with a warning icon. A warning is said once and again every 20 seconds while it holds; in between, `warnings_still_true` counts the ones not repeated. Read them: they are how you notice a factory that has stopped. Don't throw answers away in scripts.";

#[derive(Parser)]
#[command(name = "fac", version, about = ABOUT, long_about = format!("{ABOUT}\n\n{GUIDANCE}"))]
pub struct Cli {
    /// Daemon socket.
    #[arg(long, env = "FACTOBOT_SOCKET", default_value_os_t = default_socket(), global = true)]
    pub socket: PathBuf,
    #[command(subcommand)]
    pub command: Command,
}

#[derive(Subcommand)]
pub enum Command {
    /// Show the daemon and game state: game tick, versions, connected players.
    #[command(after_help = "Examples:\n  fac status\n  fac status | jq .result.game.tick")]
    Status,
    /// What the agent sees around itself: position, reach, inventory,
    /// crafting queue, running jobs, the nearest 50 things (fish in the
    /// water among them), resources and water. Machines show the status
    /// their icon shows (working, no_fuel, no_power, no_ingredients,
    /// full_output, ...): not_plugged_in_electric_network means it is in no
    /// pole's supply area or its poles have no generator, and no_power that
    /// the generators can't run it. A machine short of ingredients shows
    /// `missing`: each ingredient it has less of than one craft takes.
    /// A straight belt run is one entry from its first tile to its last.
    /// Belts, underground belts and splitters carry `lanes`: what lies on
    /// each lane (left and right facing the way items travel), per item,
    /// left out when there is nothing; two items on one lane mix. A belt
    /// run's `fill` is the items on it over the most it holds: 1 is packed
    /// full, 0 empty.
    ///
    /// With --problems, only your machines that aren't working (stalled,
    /// unpowered, unplugged, short of ingredients, output full, no recipe,
    /// ...) within 32 tiles, nearest first, and how many machines it looked
    /// at: walk along a big block with it to find what holds it up. An
    /// inserter waiting for items or room doesn't count, nor a drill
    /// waiting for room on a full belt, nor a boiler whose engines need no
    /// more steam: the machine they wait on shows the problem.
    #[command(
        after_help = "Examples:\n  fac observe\n  fac observe --radius 24\n  fac observe --problems              # stalled machines within 32 tiles\n  fac observe --problems --radius 12\n\nFor just your items, `fac inventory` is shorter."
    )]
    Observe {
        /// How far to look, in tiles (1 to 32) [default: 10, or 32 with
        /// --problems].
        #[arg(long, value_parser = parse_finite)]
        radius: Option<f64>,
        /// Only machines that aren't working.
        #[arg(long)]
        problems: bool,
    },
    /// The production window: what your factory made and used, per item
    /// and fluid, per minute over the last minute (`made_1m`, `used_1m`)
    /// and the last 10 minutes (`made_10m`, `used_10m`), and in all since
    /// the map began (`made`, `used`). Busiest first; `idle` names what was
    /// made or used before but not in the last 10 minutes. Name items to
    /// see just those, 0 for one never made. Hand-crafted items count as
    /// made, and what hand-crafting uses up as used. Use it to see that a
    /// product line never started (made 0) or that something is used
    /// faster than it is made (used above made).
    #[command(
        after_help = "Examples:\n  fac stats\n  fac stats chemical-science-pack sulfur\n  fac stats petroleum-gas            # fluids too"
    )]
    Stats {
        /// Item or fluid names, e.g. iron-plate (default: everything).
        items: Vec<String>,
    },
    /// What you carry: every item with its count, or only the items you
    /// name (0 for one you have none of).
    #[command(
        after_help = "Examples:\n  fac inventory\n  fac inventory coal iron-plate copper-plate"
    )]
    Inventory {
        /// Item names, e.g. coal (default: everything).
        items: Vec<String>,
    },
    /// Resource patches and water on the explored map, nearest first: ore,
    /// stone, coal, crude oil, water. Walking reveals the area around the
    /// agent. Crude oil is not mined: a pumpjack on a well pumps it into a pipe.
    /// With a name, only that resource's patches, and the nearest one's shape
    /// as `rows`: for each row of tiles its `y` and the runs of tiles that
    /// hold it, `[from x, to x]`, as the map view draws the patch. Use it to
    /// line drills up along an edge instead of probing tiles.
    #[command(
        after_help = "Examples:\n  fac map\n  fac map iron-ore       # the nearest iron patch, row by row\n  fac map water"
    )]
    Map {
        /// A resource to show the shape of: iron-ore, copper-ore, coal,
        /// stone, crude-oil, uranium-ore or water.
        resource: Option<String>,
    },
    /// Walk to a position along a planned route, at running speed. One walk
    /// goes at most 500 tiles. The route goes through whole tiles: you can't
    /// be routed between two buildings standing side by side. When there is
    /// no route, the error says whether you or the target is closed in and
    /// what stands in the way. If something solid keeps you from getting
    /// --within of it, the walk ends as near as you get at the end of its
    /// route; 2 seconds without getting nearer the next point of its route
    /// fails it as `stuck`.
    #[command(
        after_help = "Examples:\n  fac walk 12,-30\n  fac walk 12,-30 --within 2 --wait\n\nA new walk, mine or line replaces the running one."
    )]
    Walk {
        /// Destination as X,Y.
        #[arg(value_parser = parse_pair, allow_hyphen_values = true)]
        to: (f64, f64),
        /// Stop once this close to the destination, in tiles (0 to 10).
        /// Use it to walk up to something solid, like a tree.
        #[arg(long, default_value_t = 1.0, value_parser = parse_finite)]
        within: f64,
        #[command(flatten)]
        wait: WaitArg,
    },
    /// Mine what is at a position: a resource, tree or rock, a fish in the
    /// water (5 raw-fish), one of your buildings (it comes back to your
    /// inventory with what it holds), or an item on the ground. It must be
    /// in reach: see `reach` in `fac observe`. Resources, trees and rocks
    /// need `mine` reach (2.7 tiles to their edge), so walk up to them with
    /// `--within 2` first; fish, buildings and items need `interact` reach.
    /// Crude oil (`crude-oil` on `fac map`) is not mined by hand. The error
    /// says to place a pumpjack on the well; the pumpjack pumps into a pipe.
    /// The pumpjack recipe stays locked until `oil-gathering` is researched,
    /// and the craft error names that technology.
    #[command(
        after_help = "Examples:\n  fac walk 11.3,-58.6 --within 2 --wait\n  fac mine 11.3,-58.6            # a tree: mines it down\n  fac mine -74.5,-6.5 --count 10 --wait\n  fac mine 58.1,1.8 --wait        # a fish from `fac observe`\n  fac mine 3,4 --wait             # pick up your stone furnace\n\nA new walk, mine or line replaces the running one."
    )]
    Mine {
        /// Position as X,Y.
        #[arg(value_parser = parse_pair, allow_hyphen_values = true)]
        at: (f64, f64),
        /// Units to take from a resource tile (trees, rocks and fish always
        /// come whole).
        #[arg(long, default_value_t = 1)]
        count: u32,
        #[command(flatten)]
        wait: WaitArg,
    },
    /// Hand-craft items. Ingredients leave the inventory at once. If you are
    /// short of an intermediate (gears, circuits) but have what it is made
    /// from, that intermediate is crafted first, and any you already carry
    /// are used before more are crafted: the job's `used` lists what it
    /// took. You need enough for the whole count now (1 to 1000), or the
    /// craft is refused. A recipe that needs a machine is refused too.
    /// The job's `eta_tick` says when it should be done. Crafting runs
    /// alongside walking and mining and can't be cancelled, so queue it
    /// and keep working. A locked recipe's error names the
    /// technology that unlocks it (`fac research TECH` queues it,
    /// `fac research TECH --show` looks it up). Refineries, chemical plants,
    /// plastic bars, sulfur, advanced circuits and chemical science packs
    /// stay locked until that technology is researched. `oil-processing`,
    /// which unlocks the refinery, the chemical plant and
    /// `basic-oil-processing`, is not researched in labs: it unlocks when a
    /// pumpjack extracts crude oil.
    #[command(
        after_help = "Examples:\n  fac craft iron-gear-wheel --count 4\n  fac craft electronic-circuit --count 20 --wait 180\n  fac craft pumpjack                         # locked until oil-gathering\n  fac craft advanced-circuit --count 2       # locked until advanced-circuit\n  fac craft chemical-science-pack --count 2  # needs oil products; the error names the technology\n\nFor a long craft, read `eta_tick` and check it with `fac job ID` while you walk and build."
    )]
    Craft {
        /// Recipe name, e.g. iron-gear-wheel.
        recipe: String,
        /// How many to queue (1 to 1000).
        #[arg(long, default_value_t = 1)]
        count: u32,
        #[command(flatten)]
        wait: WaitArg,
    },
    /// Show a job, or wait for it to end.
    #[command(after_help = "Examples:\n  fac job 3\n  fac job 3 --wait 30")]
    Job {
        id: u64,
        #[command(flatten)]
        wait: WaitArg,
    },
    /// List running jobs.
    #[command(after_help = "Examples:\n  fac jobs")]
    Jobs,
    /// Stop a running walk, mine or line job. A craft can't be cancelled.
    #[command(after_help = "Examples:\n  fac cancel 3")]
    Cancel { id: u64 },
    /// Place a building from your inventory, within build reach. It snaps to
    /// the tile grid; the result shows where it went. If the same building
    /// already stands there facing the same way, nothing is used up and the
    /// result says `already_there`; facing another way, rotate it instead.
    /// If the building leaves you no walkable way out, the result says
    /// `enclosed` and what to mine to get out. A machine on a powered
    /// network shows the status it has once power reaches it. A drill or
    /// inserter shows where its output goes (`drops_into`, with the belt
    /// `lane` it lands on, or `drops_at` on the ground) and an inserter
    /// where it takes from (`picks_from`, with the `lane` it takes from
    /// first, or `picks_at` with nothing there); `warnings` says so when
    /// its output would land on the ground, have nowhere to go (a pole or
    /// another building that takes no items stands where it drops), or land
    /// on a belt lane that already carries something else, or it has
    /// nothing to take from. A belt says what it does to the belt it points
    /// into: `continues` it end on, `sideloads` onto one `lane` of it, or
    /// `curves` it (see below). Placed on a slower building of the same
    /// kind and size (assembling-machine-2 on an assembling-machine-1, a
    /// steel furnace on a stone furnace, a faster belt on a belt), it takes
    /// its place and keeps its recipe and contents; the old one comes back
    /// to your inventory and the result names it in `replaced`.
    ///
    /// A pipe-to-ground comes up on the side --direction names and runs
    /// underground the other way, to a partner at most 10 tiles away that
    /// faces the opposite way. The result shows `paired_with` once the two
    /// join, and `warnings` says so while one has no partner. Place each
    /// end; --to does not lay them.
    ///
    /// With --to, drag a straight line of them (belts, pipes, walls, poles
    /// with --spacing) from X,Y to the --to end, as a player does while
    /// running: this starts a job. The first one must be in build reach. You
    /// walk beside the line at running speed and each one goes down when it
    /// comes into build reach, one item each; ones already there are kept.
    /// The job is done with you beside the far end; if something stops you
    /// getting there after the last one is down, `stopped_short` says how
    /// far from it you stand. The job fails where it stops, saying why (out
    /// of items, something in the way, the walk ending out of build reach of
    /// the next one) with how many it placed and where the next one goes.
    #[command(
        after_help = "Examples:\n  fac place stone-furnace 3,4\n  fac place burner-mining-drill -70,-6 --direction south\n  fac place transport-belt 5.5,0.5 --direction east\n  fac place underground-belt 6.5,0.5 --direction east                     # entrance\n  fac place underground-belt 10.5,0.5 --direction east --belt-type output # exit\n  fac place transport-belt 0.5,0.5 --to 30.5,0.5 --wait   # 31 belts moving east\n  fac place pipe 2.5,-3.5 --to 2.5,-20.5                   # a job; follow it with fac job\n  fac place small-electric-pole 0.5,2.5 --to 40.5,2.5 --spacing 7\n\nUnderground belts: give the entrance and the exit the same --direction, the\nway items travel (both east above, for items moving east), and put the exit\nfurther along that way with at most 4 tiles between them (underground-belt;\nfast and express go further). The result shows `underground` (input or\noutput) and, once the pair joins, `paired_with`: the other end. Don't rotate\nan end to make an exit: rotating turns it into the other kind facing the\nopposite way, which doesn't join the entrance.\n\nBelts, lanes and inserters: a belt has two lanes, `left` and `right` facing\nthe way items travel. Each lane holds 4 items a tile and a transport-belt\nmoves 7.5 items/s on each. Items on a lane move in single file: one that no\nmachine along the belt takes stops at its end, and the lane stops behind it\nuntil the item is taken off. So put one item on each lane, and two on one\nlane only on purpose.\n- An inserter drops onto the far lane of a belt crossing in front of it,\n  and onto the right lane of a belt running toward or away from it. It\n  takes from the near lane first (the left lane of a belt running toward\n  or away from it), then the other lane.\n- A mining drill drops onto the near lane of a belt crossing in front of\n  it, and onto the right lane of a belt running toward or away from it,\n  except that a burner drill drops onto the left lane of one running toward\n  it.\n- On a curve an inserter drops onto the lane farther from it, and a drill\n  beside the curve's outer side onto the outer lane.\n- A belt pointing into the side of another sideloads: both its lanes go onto\n  the near lane of the other belt. But when nothing feeds that tile from\n  behind, the tile turns into a curve instead (`curves`) and both lanes carry\n  on round it: add a belt behind that tile, or point the side belt at a tile\n  that has one.\n- Sideloading an underground belt's entrance or exit lets through only the\n  lane over the half of its tile that is belt (`blocked_lane` is the other):\n  a way to take one lane off a belt.\n- A belt pointing into another's back (`continues`) and a splitter keep each\n  lane on its side.\n`drops_into.lane` and `picks_from.lane` say which lane; `fac inspect` and\n`fac observe` show what is on each.\n\nA line's job shows `placed`, `already_there`, `tiles` (how many the line\nhas) and `next` (where the next one goes) as it runs. Starting a line stops a\nrunning walk or mine, and a new walk, mine or line stops it."
    )]
    Place {
        /// Item name, e.g. stone-furnace.
        item: String,
        /// Position as X,Y.
        #[arg(value_parser = parse_pair, allow_hyphen_values = true)]
        at: (f64, f64),
        /// Which way the building faces. A mining drill drops its output on
        /// that side; an inserter picks up from that side and drops on the
        /// opposite one; a belt, underground belts included, moves items
        /// that way [default: north, or for a line the way it runs].
        #[arg(long, value_parser = ["north", "east", "south", "west"])]
        direction: Option<String>,
        /// For an underground belt: `input` is the entrance where items go
        /// under, `output` the exit where they come up [default: input].
        #[arg(long, value_parser = ["input", "output"], conflicts_with = "to")]
        belt_type: Option<String>,
        /// Place a straight line from X,Y to this end, as X,Y: both ends
        /// share x or y. At most 500 tiles long.
        #[arg(long, value_parser = parse_pair, allow_hyphen_values = true)]
        to: Option<(f64, f64)>,
        /// With --to, tiles from one building to the next (1 to 64)
        /// [default: the building's length, so they touch].
        #[arg(long, requires = "to")]
        spacing: Option<u32>,
        /// With --to, block until the line is done, at most this many
        /// seconds of real time (default 60, up to 600). If the time runs
        /// out first, you get the job still `running` and it keeps going.
        #[arg(long, requires = "to", num_args = 0..=1, default_missing_value = "60", value_parser = parse_finite)]
        wait: Option<f64>,
    },
    /// Put items from your inventory into a building in reach: fuel,
    /// furnace ore, chest contents, assembler ingredients, modules (into
    /// module slots, where the machine and its recipe allow them), rocket
    /// parts' ingredients and a rocket's payload into a rocket silo. The
    /// building takes only what it can use. Asking for more than you carry
    /// puts in what you have and the result's `short` says how many were
    /// missing; carrying none is an error. Fluids such as crude-oil,
    /// petroleum-gas and water are not items. The error says to move them
    /// through pipes; `fac inspect` then shows `fluids` and `pipes_to`.
    #[command(
        after_help = "Examples:\n  fac insert 3,4 coal 5\n  fac insert 3,4 coal --count 5   # the same\n  fac insert 3,4 iron-ore         # all you carry\n  fac insert 3,4 coal 50          # carrying 20: inserted 20, short 30\n  fac insert 12.5,0.5 productivity-module 4\n  fac insert 12.5,0.5 raw-fish 1  # the rocket's payload"
    )]
    Insert {
        /// Position as X,Y.
        #[arg(value_parser = parse_pair, allow_hyphen_values = true)]
        at: (f64, f64),
        /// Item name, e.g. coal.
        item: String,
        /// How many (default: all you carry); the same as --count.
        #[arg(value_name = "COUNT", conflicts_with = "count")]
        how_many: Option<u32>,
        /// How many (default: all you carry).
        #[arg(long)]
        count: Option<u32>,
    },
    /// Take items out of a building in reach. With no item, takes what it
    /// made: a furnace's or assembler's output, a chest's contents, or a
    /// burnt fuel's leftovers. On a belt, underground belt or splitter,
    /// picks up the items lying on it, as by hand, from every lane: both
    /// belts of a splitter, and an underground belt's lanes below ground
    /// too. If there is nothing, the error says what a machine is doing
    /// (when its next item is done, or what it lacks, naming the
    /// ingredients it is short of), or that a belt has nothing on it.
    #[command(
        after_help = "Examples:\n  fac take 3,4                    # the plates a furnace made\n  fac take 3,4 coal 2             # any item, from any slot\n  fac take 3,4 coal --count 2     # the same\n  fac take 5.5,0.5 iron-plate 4   # plates off a belt tile"
    )]
    Take {
        /// Position as X,Y.
        #[arg(value_parser = parse_pair, allow_hyphen_values = true)]
        at: (f64, f64),
        /// Item name (default: everything in its output, or on a belt).
        item: Option<String>,
        /// At most this many; the same as --count. Needs an item before it.
        #[arg(value_name = "COUNT", conflicts_with = "count")]
        how_many: Option<u32>,
        /// At most this many.
        #[arg(long)]
        count: Option<u32>,
    },
    /// Turn a building in reach a quarter turn clockwise. An underground
    /// belt turns around instead: an entrance becomes an exit facing the
    /// opposite way, and an exit an entrance. One end of a joined pair
    /// turns the other with it, so the pair carries items the other way.
    /// A belt then says what it does to the belt it now points into, as
    /// `fac place` does (`continues`, `sideloads` or `curves`).
    #[command(after_help = "Examples:\n  fac rotate 5.5,0.5")]
    Rotate {
        /// Position as X,Y.
        #[arg(value_parser = parse_pair, allow_hyphen_values = true)]
        at: (f64, f64),
    },
    /// Look at one thing up close, within 32 tiles: what a building holds,
    /// whether it is working or what it lacks (fuel, power, ingredients),
    /// where its output goes, the fluids in it and what its pipes join;
    /// how much ore a tile has; a rocket silo's rocket parts, rocket status
    /// and payload; which end of an underground belt it is and its partner;
    /// the items on each lane of a belt, underground belt or splitter
    /// (`lanes`, left and right facing the way items travel), and `turns`
    /// (left or right) for a belt that is a curve.
    /// A pole, or a machine on electric power, shows its network's `power`:
    /// `demand_kw`, `capacity_kw` and `satisfaction` (below 1 is
    /// `low_power`: add generators). A drill or inserter shows `drops_into`
    /// the building its output goes into, with the `lane` of a belt it
    /// lands on, or `drops_at` when nothing is there and it would land on
    /// the ground; an inserter shows `picks_from` the building it takes
    /// from, with the `lane` of a belt it takes from first, or `picks_at`
    /// when nothing is there. `fac place --help` explains lanes. A machine
    /// short of ingredients shows `missing`: each ingredient it has less
    /// of than one craft takes (`have`, `need`).
    /// `rates` is what a machine goes through at full power, per second: a
    /// drill's ore, an assembler's or furnace's crafts, ingredients and
    /// products at its crafting speed. A belt shows `capacity_per_s`, the
    /// most items it moves per second (15 for a transport-belt).
    #[command(
        after_help = "Examples:\n  fac inspect 3,4\n  fac inspect 2.5,-4.5   # a pole: its network's power\n  fac inspect 5.5,0.5    # a belt: what is on each lane"
    )]
    Inspect {
        /// Position as X,Y.
        #[arg(value_parser = parse_pair, allow_hyphen_values = true)]
        at: (f64, f64),
    },
    /// Choose what a machine in reach makes. Assembling machines, chemical
    /// plants and oil refineries all count: a chemical plant and an oil
    /// refinery are assembling machines. Ingredients inside that the new recipe
    /// doesn't use come back to your inventory, or are dropped at your feet
    /// if it is full. A locked recipe's error names the technology, as
    /// `fac craft` does. If this machine can't make the recipe, the error
    /// names the crafting category (`chemistry` for plastic and sulfur,
    /// `oil-processing` for basic and advanced oil processing). The result
    /// shows the machine with its `ports`: for each pipe connection whether
    /// fluid goes `input` or `output` there, which `fluid` the recipe puts
    /// on it, the tile a pipe has to stand on (`pipe_at`) and what is
    /// `joined_to` it now, with the `fluid` that pipe holds; `problem` says
    /// so when the pipe holds another fluid than the port's. The ports turn
    /// with the machine and change with the recipe, so read them before you
    /// lay pipes, and again after `fac rotate`. Ports of the same fluid
    /// share one tank, so one joined port per fluid is enough.
    /// `fluid_ingredient_shortage` means no fluid reaches an input: none of
    /// its ports has `joined_to`, the pipe holds something else, or nothing
    /// flows through it. `fac inspect` shows the same.
    #[command(
        after_help = "Examples:\n  fac recipe 10.5,4.5 iron-gear-wheel\n  fac recipe 0.5,0.5 basic-oil-processing   # an oil refinery\n  fac recipe 4.5,-6.5 plastic-bar           # a chemical plant\n  fac recipe 8.5,4.5 advanced-circuit       # an assembling machine\n  fac recipe 8.5,6.5 chemical-science-pack"
    )]
    Recipe {
        /// Position as X,Y.
        #[arg(value_parser = parse_pair, allow_hyphen_values = true)]
        at: (f64, f64),
        /// Recipe name, e.g. iron-gear-wheel.
        recipe: String,
    },
    /// Research: with no technology, show the current research and its
    /// progress, the queue, what can be researched next with its cost and
    /// where each leads (`leads_to`), and how many technologies are
    /// researched. With one, queue every prerequisite not yet researched or
    /// queued, each after its own, then the technology, as the tech screen
    /// does, and show the queue. The queue holds at most 7 technologies, the
    /// current one included; if the technology and its missing prerequisites
    /// don't all fit, nothing is queued and the message gives the slots
    /// needed. Labs need power and science packs. Some early technologies
    /// instead unlock when you craft, make or mine something; if the
    /// technology is one, or a missing prerequisite is one, nothing is queued
    /// and the message names the action, such as `craft 1 lab`, `make 10
    /// copper-plate in a machine (smelting)` or `extract crude-oil with a
    /// pumpjack`. Chemical science
    /// (`chemical-science-pack`) needs `advanced-circuit` and
    /// `sulfur-processing`, which need oil. `oil-processing` unlocks when a
    /// pumpjack extracts crude oil, not in labs; until then queueing
    /// `plastics` or `chemical-science-pack` names that trigger and queues
    /// nothing.
    #[command(
        after_help = "Examples:\n  fac research\n  fac research automation\n  fac research automation --cancel\n  fac research chemical-science-pack --show   # look it up without queueing\n  fac research --researched                   # also list what is researched\n\n--show gives a technology's state (researched, current, queued, available or\nlocked), cost, unlocks, prerequisites, `needs` (every prerequisite still to\nresearch, each after its own prerequisites) and `leads_to`. `needs` can include\ntechnologies that unlock by an action rather than labs; --show on one gives its\n`trigger`."
    )]
    Research {
        /// Technology name, e.g. automation.
        tech: Option<String>,
        /// Take it out of the research queue instead.
        #[arg(long, requires = "tech", conflicts_with = "show")]
        cancel: bool,
        /// Look the technology up without queueing it.
        #[arg(long, requires = "tech")]
        show: bool,
        /// Also list the names of the researched technologies.
        #[arg(long, conflicts_with = "tech")]
        researched: bool,
    },
    /// Launch the rocket from a rocket silo in reach, as its Launch button
    /// does. The rocket must be built (all rocket parts made) and standing
    /// ready in the silo, with a payload in it: insert raw-fish or a
    /// satellite first. The game counts the launch about 19 s later, when
    /// the rocket reaches space.
    #[command(
        after_help = "Examples:\n  fac inspect 12.5,0.5                     # rocket.status rocket_ready?\n  fac insert 12.5,0.5 raw-fish --count 1\n  fac launch 12.5,0.5"
    )]
    Launch {
        /// Position of the silo as X,Y.
        #[arg(value_parser = parse_pair, allow_hyphen_values = true)]
        at: (f64, f64),
    },
    /// Take a screenshot of what your screen shows: the game view centred
    /// on you, 1920x1080 pixels, with alt-mode info on, lit as the game is
    /// at that moment (darker at night). Over a machine it shows the
    /// warning a player sees: a yellow plug when it is in no pole's supply
    /// area or its poles have no generator, a red lightning bolt when its
    /// network has too little power, a red fuel icon when it has no fuel;
    /// and in alt mode the recipe an assembler makes, the items on belts,
    /// and where pipes and belts end or fail to join. A thin grid of map
    /// coordinates lies over it: a line every 10 tiles (every 5 when zoomed
    /// in past 1.5), each crossing labelled `x,y`, so you can read off where
    /// a thing stands and pass that to `fac inspect`. Lines run along tile
    /// edges: a 1x1 building in the tile just right of and below the
    /// crossing `20,-30` is at 20.5,-29.5. It writes a PNG and prints its
    /// `path`; look at it with your own image viewer or file reading tool.
    /// The result also gives the `tick`, the `zoom`, the `center` (where you
    /// stand), the `area` of map tiles it covers (`left_top`,
    /// `right_bottom`) and `grid_tiles`, the tiles between grid lines. Needs
    /// a world started with a camera; without one it fails as `unavailable`.
    #[command(
        after_help = "Examples:\n  fac screenshot                     # screenshot-<tick>.png in this directory\n  fac screenshot -o base.png         # replaces base.png\n  fac screenshot --zoom 0.5          # zoomed out: 120x68 tiles\n  fac screenshot --zoom 2            # zoomed in: 30x17 tiles\n  fac screenshot --no-grid           # the plain picture\n\nZoom 1 shows 60x34 tiles around you. You can zoom from 0.5 (furthest) to 3\n(closest)."
    )]
    Screenshot {
        /// Where to write the PNG [default: a new screenshot-<tick>.png in the
        /// current directory].
        #[arg(short, long)]
        output: Option<PathBuf>,
        /// Zoom, from 0.5 (furthest out) to 3 (closest in); 1 is the game's
        /// default.
        #[arg(long, value_parser = parse_finite)]
        zoom: Option<f64>,
        /// Leave the coordinate grid out.
        #[arg(long)]
        no_grid: bool,
    },
}

#[derive(clap::Args)]
pub struct WaitArg {
    /// Block until the job ends, at most this many seconds of real time
    /// (default 60, up to 600). If the time runs out first, you get the job
    /// still `running` and it keeps going. The game keeps running while you
    /// wait.
    #[arg(long, num_args = 0..=1, default_missing_value = "60", value_parser = parse_finite)]
    pub wait: Option<f64>,
}

/// Run one agent command against the daemon at `cli.socket` and print its result.
pub async fn run(cli: Cli) -> ExitCode {
    match cli.command {
        Command::Status => agent_call(&cli.socket, "status", Value::Null).await,
        Command::Observe { radius, problems } => {
            let params = json!({ "radius": radius, "problems": problems });
            agent_call(&cli.socket, "observe", params).await
        }
        Command::Stats { items } => agent_call(&cli.socket, "stats", items_params(items)).await,
        Command::Inventory { items } => {
            agent_call(&cli.socket, "inventory", items_params(items)).await
        }
        Command::Map { resource } => {
            agent_call(&cli.socket, "map", json!({ "resource": resource })).await
        }
        Command::Walk {
            to: (x, y),
            within,
            wait,
        } => {
            let params = json!({ "x": x, "y": y, "within": within });
            job_call(&cli.socket, "walk", params, wait.wait).await
        }
        Command::Mine {
            at: (x, y),
            count,
            wait,
        } => {
            let params = json!({ "x": x, "y": y, "count": count });
            job_call(&cli.socket, "mine", params, wait.wait).await
        }
        Command::Craft {
            recipe,
            count,
            wait,
        } => {
            let params = json!({ "recipe": recipe, "count": count });
            job_call(&cli.socket, "craft", params, wait.wait).await
        }
        Command::Job { id, wait } => match wait.wait {
            Some(timeout) => {
                agent_call(&cli.socket, "wait", json!({ "id": id, "timeout": timeout })).await
            }
            None => agent_call(&cli.socket, "job", json!({ "id": id })).await,
        },
        Command::Jobs => agent_call(&cli.socket, "jobs", Value::Null).await,
        Command::Cancel { id } => agent_call(&cli.socket, "cancel", json!({ "id": id })).await,
        Command::Place {
            item,
            at: (x, y),
            direction,
            belt_type,
            to,
            spacing,
            wait,
        } => match to {
            Some((to_x, to_y)) => {
                let params = json!({
                    "item": item, "x": x, "y": y, "to_x": to_x, "to_y": to_y,
                    "direction": direction, "spacing": spacing,
                });
                job_call(&cli.socket, "place_line", params, wait).await
            }
            None => {
                let params = json!({
                    "item": item, "x": x, "y": y, "direction": direction, "belt_type": belt_type,
                });
                agent_call(&cli.socket, "place", params).await
            }
        },
        Command::Insert {
            at: (x, y),
            item,
            how_many,
            count,
        } => {
            agent_call(
                &cli.socket,
                "insert",
                transfer_params(x, y, item, count, how_many),
            )
            .await
        }
        Command::Take {
            at: (x, y),
            item,
            how_many,
            count,
        } => {
            agent_call(
                &cli.socket,
                "take",
                transfer_params(x, y, item, count, how_many),
            )
            .await
        }
        Command::Rotate { at: (x, y) } => {
            agent_call(&cli.socket, "rotate", json!({ "x": x, "y": y })).await
        }
        Command::Inspect { at: (x, y) } => {
            agent_call(&cli.socket, "inspect", json!({ "x": x, "y": y })).await
        }
        Command::Recipe { at: (x, y), recipe } => {
            let params = json!({ "x": x, "y": y, "recipe": recipe });
            agent_call(&cli.socket, "set_recipe", params).await
        }
        Command::Research {
            tech,
            cancel,
            show,
            researched,
        } => {
            let params = json!({
                "tech": tech, "cancel": cancel, "show": show, "researched": researched,
            });
            agent_call(&cli.socket, "research", params).await
        }
        Command::Launch { at: (x, y) } => {
            agent_call(&cli.socket, "launch", json!({ "x": x, "y": y })).await
        }
        Command::Screenshot {
            output,
            zoom,
            no_grid,
        } => screenshot(&cli.socket, output, zoom, !no_grid).await,
    }
}

/// `stats` and `inventory` take no params when no item names were given.
fn items_params(items: Vec<String>) -> Value {
    if items.is_empty() {
        Value::Null
    } else {
        json!({ "items": items })
    }
}

/// `insert` and `take` share a position, an item and a count (`--count` or the positional one).
fn transfer_params(
    x: f64,
    y: f64,
    item: impl Serialize,
    count: Option<u32>,
    how_many: Option<u32>,
) -> Value {
    json!({ "x": x, "y": y, "item": item, "count": count.or(how_many) })
}

pub fn parse_finite(text: &str) -> Result<f64, String> {
    match text.trim().parse::<f64>() {
        Ok(value) if value.is_finite() => Ok(value),
        _ => Err(format!("expected a finite number, got {text:?}")),
    }
}

pub fn parse_pair(text: &str) -> Result<(f64, f64), String> {
    let (a, b) = text.split_once(',').ok_or("expected X,Y")?;
    Ok((parse_finite(a)?, parse_finite(b)?))
}

/// Start a job, then with `--wait` block until it ends and print the job.
async fn job_call(socket: &Path, method: &str, mut params: Value, wait: Option<f64>) -> ExitCode {
    let Some(timeout) = wait else {
        return agent_call(socket, method, params).await;
    };
    // Refuse an out-of-range wait before the job starts: a craft takes its
    // ingredients the moment it is queued.
    if let Some(error) = protocol::wait_timeout_error(timeout) {
        return print_response(Ok(protocol::Response::err(1, error.code, error.message)));
    }
    // The start's answer is printed only when the job did not start, so the
    // mod keeps its HUD warnings for the wait's answer (protocol.md).
    params["hud"] = json!("defer");
    let started = client::call(socket, method, params).await;
    let id = match &started {
        Ok(response) if response.ok => response.result.as_ref().and_then(|job| job["id"].as_u64()),
        _ => None,
    };
    match id {
        Some(id) => agent_call(socket, "wait", json!({ "id": id, "timeout": timeout })).await,
        None => print_response(started),
    }
}

/// Ask the daemon for what the agent's screen shows and write the PNG it
/// sends back: to `output`, else to a new `screenshot-<tick>.png` in the
/// current directory. Prints the result with the file's `path` in place of
/// the image data.
async fn screenshot(
    socket: &Path,
    output: Option<PathBuf>,
    zoom: Option<f64>,
    grid: bool,
) -> ExitCode {
    let params = json!({ "zoom": zoom, "grid": grid });
    let response = match client::call(socket, "screen", params).await {
        Ok(response) => response,
        failed @ Err(_) => return print_response(failed),
    };
    let id = response.id;
    let mut result = match response.result {
        Some(Value::Object(result)) if response.ok => result,
        _ => return print_response(Ok(response)),
    };
    let failure =
        |code, message: String| print_response(Ok(protocol::Response::err(id, code, message)));
    let png = match result
        .remove(protocol::PNG_FIELD)
        .as_ref()
        .and_then(Value::as_str)
        .map(|data| base64::engine::general_purpose::STANDARD.decode(data))
    {
        Some(Ok(png)) => png,
        _ => {
            return failure(
                protocol::ErrorCode::GameError,
                "the daemon sent no PNG data".into(),
            );
        }
    };
    let tick = result.get("tick").and_then(Value::as_u64).unwrap_or(0);
    match write_png(output, tick, &png) {
        Ok(path) => {
            result.insert("path".into(), json!(path));
            print_response(Ok(protocol::Response::ok(id, Value::Object(result))))
        }
        Err(err) => failure(protocol::ErrorCode::BadRequest, format!("{err:#}")),
    }
}

/// Write `png` to `output`, replacing it, or to the first of
/// `screenshot-<tick>.png`, `screenshot-<tick>-2.png`, ... that doesn't
/// exist yet. Returns the absolute path.
fn write_png(output: Option<PathBuf>, tick: u64, png: &[u8]) -> anyhow::Result<PathBuf> {
    use std::io::Write as _;

    let path = match output {
        Some(path) => {
            std::fs::write(&path, png).with_context(|| format!("writing {}", path.display()))?;
            path
        }
        None => {
            let mut n = 1;
            loop {
                let path = PathBuf::from(if n == 1 {
                    format!("screenshot-{tick}.png")
                } else {
                    format!("screenshot-{tick}-{n}.png")
                });
                match std::fs::OpenOptions::new()
                    .write(true)
                    .create_new(true)
                    .open(&path)
                {
                    Ok(mut file) => {
                        file.write_all(png)
                            .with_context(|| format!("writing {}", path.display()))?;
                        break path;
                    }
                    Err(err) if err.kind() == std::io::ErrorKind::AlreadyExists => n += 1,
                    Err(err) => {
                        return Err(anyhow::Error::from(err)
                            .context(format!("creating {}", path.display())));
                    }
                }
            }
        }
    };
    Ok(std::path::absolute(&path).unwrap_or(path))
}

pub async fn agent_call(socket: &Path, method: &str, params: Value) -> ExitCode {
    print_response(client::call(socket, method, params).await)
}

/// Print the answer. The exit code is a failure when the daemon refused the
/// call, and also when the answer is a job that ended `failed` (a walk with
/// no path, a mine with a full inventory), so `fac walk X,Y --wait && ...`
/// stops there and a script that checks exit codes sees it.
fn print_response(response: anyhow::Result<protocol::Response>) -> ExitCode {
    let (body, ok) = match response {
        Ok(response) => {
            let failed_job = response
                .result
                .as_ref()
                .is_some_and(|result| result["kind"].is_string() && result["state"] == "failed");
            let ok = response.ok && !failed_job;
            (serde_json::to_value(&response), ok)
        }
        Err(err) => (
            Ok(json!({
                "ok": false,
                "error": {"code": "unavailable", "message": format!("{err:#}")},
            })),
            false,
        ),
    };
    match body.map(|body| println!("{body}")) {
        Ok(()) if ok => ExitCode::SUCCESS,
        _ => ExitCode::FAILURE,
    }
}

/// Default agent socket: `$XDG_RUNTIME_DIR/factobot/fac.sock`, or
/// `$TMPDIR/factobot-$USER/factobot/fac.sock` when that variable is unset.
///
/// An empty or relative `XDG_RUNTIME_DIR` is treated as unset. The XDG Base
/// Directory Specification 0.8 (8 May 2021) says every path in these variables
/// must be absolute, and that a relative path is invalid and ignored. An empty
/// value is not absolute, so it is ignored too.
/// <https://specifications.freedesktop.org/basedir-spec/latest/>
pub fn default_socket() -> PathBuf {
    let runtime_dir = std::env::var_os("XDG_RUNTIME_DIR");
    socket_from_runtime_dir(runtime_dir.as_deref().map(Path::new))
}

fn socket_from_runtime_dir(runtime_dir: Option<&Path>) -> PathBuf {
    let base = match runtime_dir {
        Some(dir) if dir.is_absolute() => dir.to_path_buf(),
        // Unset, empty, or relative.
        _ => std::env::temp_dir().join(format!("factobot-{}", whoami())),
    };
    base.join("factobot/fac.sock")
}

fn whoami() -> String {
    std::env::var("USER").unwrap_or_else(|_| "user".into())
}

#[cfg(test)]
mod tests {
    use std::path::{Path, PathBuf};

    use clap::CommandFactory;

    use super::{socket_from_runtime_dir, whoami, *};

    #[test]
    fn long_help_holds_the_guidance() {
        let long_about = Cli::command().get_long_about().unwrap().to_string();
        assert!(long_about.contains(GUIDANCE));
        assert!(long_about.contains("still `running`"));
    }

    #[test]
    fn oil_path_help_names_the_pumpjack_and_the_recipes() {
        let cmd = Cli::command();
        let about = |name: &str| {
            cmd.find_subcommand(name)
                .unwrap_or_else(|| panic!("no {name}"))
                .get_about()
                .unwrap_or_else(|| panic!("{name} has no about"))
                .to_string()
        };
        let after = |name: &str| {
            cmd.find_subcommand(name)
                .unwrap()
                .get_after_help()
                .unwrap_or_else(|| panic!("{name} has no after_help"))
                .to_string()
        };
        assert!(about("map").contains("pumpjack"), "{}", about("map"));
        assert!(about("mine").contains("pumpjack"), "{}", about("mine"));
        assert!(about("mine").contains("oil-gathering"), "{}", about("mine"));
        assert!(
            about("craft").contains("oil-processing"),
            "{}",
            about("craft")
        );
        assert!(
            about("craft").contains("chemical science"),
            "{}",
            about("craft")
        );
        assert!(
            about("recipe").contains("chemical plant"),
            "{}",
            about("recipe")
        );
        assert!(
            about("recipe").contains("oil refinery"),
            "{}",
            about("recipe")
        );
        assert!(
            about("recipe").contains("fluid_ingredient_shortage"),
            "{}",
            about("recipe")
        );
        assert!(
            after("craft").contains("chemical-science-pack"),
            "{}",
            after("craft")
        );
        assert!(
            after("craft").contains("advanced-circuit"),
            "{}",
            after("craft")
        );
        assert!(
            after("recipe").contains("basic-oil-processing"),
            "{}",
            after("recipe")
        );
        assert!(
            after("recipe").contains("plastic-bar"),
            "{}",
            after("recipe")
        );
        assert!(
            about("research").contains("oil-processing"),
            "{}",
            about("research")
        );
        assert!(
            about("research").contains("chemical-science-pack"),
            "{}",
            about("research")
        );
        assert!(
            about("insert").contains("petroleum-gas"),
            "{}",
            about("insert")
        );
    }

    fn temp_socket() -> PathBuf {
        std::env::temp_dir()
            .join(format!("factobot-{}", whoami()))
            .join("factobot/fac.sock")
    }

    #[test]
    fn empty_or_relative_runtime_dir_uses_the_temp_dir() {
        let fallback = temp_socket();
        for runtime_dir in [
            None,
            Some(Path::new("")),
            Some(Path::new("run")),
            Some(Path::new("./run")),
        ] {
            let socket = socket_from_runtime_dir(runtime_dir);
            assert_eq!(socket, fallback, "runtime dir {runtime_dir:?}");
            assert!(socket.is_absolute(), "{}", socket.display());
        }
    }
}
